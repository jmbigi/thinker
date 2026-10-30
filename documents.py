#!/usr/bin/env python3
"""Contenido completo y recuperación local con pasajes trazables.

Los documentos se convierten en pasajes pequeños con hash, procedencia y
localización. La recuperación combina BM25 y coseno vectorial léxico; no usa ni
afirma embeddings semánticos. PDF se carga con pypdf de forma perezosa.
"""

import csv
import hashlib
import io
import math
import re
import sys
import time
import zipfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import quote, urljoin, urlparse
from xml.etree import ElementTree as ET

import requests

from web_search import SearchAPI, _es_host_publico

MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_FETCH_BYTES = 3 * 1024 * 1024
PASSAGE_SIZE = 480
SUPPORTED_SUFFIXES = {
    ".txt", ".md", ".markdown", ".csv", ".html", ".htm", ".pdf",
    ".docx", ".pptx", ".xlsx",
}
USER_AGENT = "thinker-research-documents/1.0"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ahora() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _tokens(text: str) -> List[str]:
    return [word for word in re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE)
            if len(word) > 1]


def _fragmentos(text: str, size: int = PASSAGE_SIZE) -> Iterable[Tuple[str, int, int]]:
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            corte = text.rfind(" ", start + size // 2, end)
            if corte > start:
                end = corte
        fragment = text[start:end].strip()
        if fragment:
            yield fragment, start, end
        start = end


def _resultados_texto(titulo: str, url: str, texto: str, fuente: str,
                      sha256: str, ubicacion: str) -> List[Dict[str, Any]]:
    texto = re.sub(r"\s+", " ", texto).strip()
    resultados = []
    for fragmento, inicio, fin in _fragmentos(texto):
        resultados.append({
            "title": titulo,
            "url": url,
            "snippet": fragmento,
            "content": fragmento,
            "source": fuente,
            "sha256": sha256,
            "location": f"{ubicacion}; caracteres {inicio}-{fin}",
            "fetched_at": _ahora(),
        })
    return resultados


class _HTMLTexto(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: List[str] = []
        self._ignorar = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "template"):
            self._ignorar += 1
        elif tag in ("p", "div", "section", "article", "br", "li", "tr", "h1", "h2", "h3"):
            self.partes.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template") and self._ignorar:
            self._ignorar -= 1
        elif tag in ("p", "div", "section", "article", "li", "tr", "h1", "h2", "h3"):
            self.partes.append(" ")

    def handle_data(self, data):
        if not self._ignorar:
            self.partes.append(data)

    def texto(self) -> str:
        return re.sub(r"\s+", " ", "".join(self.partes)).strip()


def _texto_html(data: bytes, encoding: str = "utf-8") -> str:
    parser = _HTMLTexto()
    parser.feed(data.decode(encoding or "utf-8", errors="replace"))
    parser.close()
    return parser.texto()


def _texto_csv(data: bytes) -> str:
    texto = data.decode("utf-8-sig")
    filas = []
    for indice, fila in enumerate(csv.reader(io.StringIO(texto)), start=1):
        filas.append(f"Línea {indice}: " + " | ".join(fila))
    return "\n".join(filas)


def _xml(data: bytes) -> ET.Element:
    return ET.fromstring(data)


def _docx_texto(archivo: zipfile.ZipFile) -> List[Tuple[str, str]]:
    raiz = _xml(archivo.read("word/document.xml"))
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    partes = []
    for indice, parrafo in enumerate(raiz.iter(f"{ns}p"), start=1):
        texto = "".join(nodo.text or "" for nodo in parrafo.iter(f"{ns}t")).strip()
        if texto:
            partes.append((f"párrafo {indice}", texto))
    return partes


def _pptx_texto(archivo: zipfile.ZipFile) -> List[Tuple[str, str]]:
    ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    nombres = sorted(
        (nombre for nombre in archivo.namelist()
         if re.fullmatch(r"ppt/slides/slide\d+\.xml", nombre)),
        key=lambda nombre: int(re.search(r"(\d+)", Path(nombre).stem).group(1)),
    )
    partes = []
    for nombre in nombres:
        raiz = _xml(archivo.read(nombre))
        texto = " ".join(nodo.text or "" for nodo in raiz.iter(f"{ns}t")).strip()
        if texto:
            numero = re.search(r"slide(\d+)", nombre).group(1)
            partes.append((f"diapositiva {numero}", texto))
    return partes


def _xlsx_texto(archivo: zipfile.ZipFile) -> List[Tuple[str, str]]:
    main_ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    compartidas: List[str] = []
    if "xl/sharedStrings.xml" in archivo.namelist():
        raiz = _xml(archivo.read("xl/sharedStrings.xml"))
        compartidas = ["".join(nodo.text or "" for nodo in item.iter(f"{main_ns}t"))
                       for item in raiz.iter(f"{main_ns}si")]
    partes = []
    nombres = sorted(nombre for nombre in archivo.namelist()
                     if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", nombre))
    for nombre in nombres:
        raiz = _xml(archivo.read(nombre))
        filas = []
        for celda in raiz.iter(f"{main_ns}c"):
            referencia = celda.attrib.get("r", "celda")
            tipo = celda.attrib.get("t")
            if tipo == "inlineStr":
                valor = "".join(nodo.text or "" for nodo in celda.iter(f"{main_ns}t"))
            else:
                nodo = celda.find(f"{main_ns}v")
                valor = "" if nodo is None else (nodo.text or "")
                if tipo == "s" and valor:
                    indice = int(valor)
                    valor = compartidas[indice] if indice < len(compartidas) else ""
            if valor:
                filas.append(f"{referencia}: {valor}")
        if filas:
            partes.append((nombre.rsplit("/", 1)[-1], "\n".join(filas)))
    return partes


def _pdf_texto(data: bytes) -> List[Tuple[str, str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Leer PDF requiere la dependencia declarada pypdf") from exc
    lector = PdfReader(io.BytesIO(data))
    if lector.is_encrypted:
        try:
            if not lector.decrypt(""):
                raise RuntimeError("El PDF cifrado requiere contraseña")
        except Exception as exc:
            raise RuntimeError("No se pudo descifrar el PDF") from exc
    partes = []
    for numero, pagina in enumerate(lector.pages, start=1):
        texto = (pagina.extract_text() or "").strip()
        if texto:
            partes.append((f"página {numero}", texto))
    return partes


def _url_documento(ruta: Path, sha256: str) -> str:
    return f"document://{sha256[:12]}/{quote(ruta.name)}"


def load_document(path: str) -> List[Dict[str, Any]]:
    """Extrae pasajes de un documento, con error explícito si no hay texto."""
    ruta = Path(path).expanduser().resolve()
    if not ruta.is_file():
        raise ValueError(f"Documento inexistente o no regular: {ruta}")
    if ruta.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"Documento supera el límite de {MAX_FILE_BYTES} bytes: {ruta}")
    sufijo = ruta.suffix.lower()
    if sufijo not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Formato no soportado: {sufijo or '(sin extensión)'}")
    try:
        data = ruta.read_bytes()
        if sufijo in (".txt", ".md", ".markdown"):
            partes = [("documento", data.decode("utf-8-sig"))]
        elif sufijo == ".csv":
            partes = [("documento", _texto_csv(data))]
        elif sufijo in (".html", ".htm"):
            partes = [("documento", _texto_html(data))]
        elif sufijo == ".pdf":
            partes = _pdf_texto(data)
        else:
            with zipfile.ZipFile(io.BytesIO(data)) as archivo:
                if sufijo == ".docx":
                    partes = _docx_texto(archivo)
                elif sufijo == ".pptx":
                    partes = _pptx_texto(archivo)
                else:
                    partes = _xlsx_texto(archivo)
    except (OSError, UnicodeError, zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
        raise RuntimeError(f"No se pudo leer {ruta}: {exc}") from exc
    sha256 = _sha256(data)
    url = _url_documento(ruta, sha256)
    resultados = []
    for ubicacion, texto in partes:
        resultados.extend(_resultados_texto(
            ruta.name, url, texto, "local-document", sha256, ubicacion))
    if not resultados:
        raise RuntimeError(f"Documento sin texto extraíble: {ruta}")
    return resultados


def load_documents(paths: Iterable[str]) -> List[Dict[str, Any]]:
    """Carga archivos o directorios en orden determinista."""
    resultados = []
    for valor in paths:
        ruta = Path(valor).expanduser().resolve()
        if ruta.is_dir():
            archivos = sorted(
                (item for item in ruta.rglob("*")
                 if item.is_file() and item.suffix.lower() in SUPPORTED_SUFFIXES),
                key=lambda item: str(item.relative_to(ruta)),
            )
            if not archivos:
                raise ValueError(f"Directorio sin documentos soportados: {ruta}")
            for archivo in archivos:
                resultados.extend(load_document(str(archivo)))
        else:
            resultados.extend(load_document(str(ruta)))
    if not resultados:
        raise ValueError("No se cargó ningún pasaje documental")
    return resultados


class PassageIndex:
    """Índice en memoria con puntuación híbrida BM25 + coseno léxico."""

    def __init__(self, passages: Iterable[Dict[str, Any]]):
        self.passages = list(passages)
        if not self.passages:
            raise ValueError("El índice exige al menos un pasaje")
        self._docs = [Counter(_tokens(p["snippet"])) for p in self.passages]
        self._lengths = [sum(doc.values()) for doc in self._docs]
        if any(length == 0 for length in self._lengths):
            raise ValueError("Todos los pasajes indexados deben contener términos")
        self._norms = [math.sqrt(sum((1 + math.log(freq)) ** 2 for freq in doc.values()))
                       for doc in self._docs]
        self._df: Counter = Counter()
        for doc in self._docs:
            self._df.update(doc.keys())
        self._avgdl = sum(self._lengths) / len(self._lengths)

    def _bm25(self, query: Counter) -> List[float]:
        total = len(self._docs)
        scores = []
        for doc, length in zip(self._docs, self._lengths):
            score = 0.0
            for term, qf in query.items():
                if term not in doc:
                    continue
                idf = math.log(1 + (total - self._df[term] + 0.5) / (self._df[term] + 0.5))
                tf = doc[term]
                denominador = tf + 1.5 * (0.25 + 0.75 * length / self._avgdl)
                score += idf * (tf * 2.5 / denominador) * qf
            scores.append(score)
        return scores

    def _cosine(self, query: Counter) -> List[float]:
        qnorm = math.sqrt(sum((1 + math.log(freq)) ** 2 for freq in query.values()))
        if not qnorm:
            return [0.0] * len(self._docs)
        scores = []
        for doc, norm in zip(self._docs, self._norms):
            producto = sum(
                (1 + math.log(freq)) * (1 + math.log(doc[term]))
                for term, freq in query.items() if term in doc
            )
            scores.append(producto / (qnorm * norm) if norm else 0.0)
        return scores

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        if max_results <= 0:
            return []
        consulta = Counter(_tokens(query))
        if not consulta:
            return []
        bm25 = self._bm25(consulta)
        coseno = self._cosine(consulta)
        max_bm25 = max(bm25, default=0.0)
        puntuaciones = []
        for indice, (b, c) in enumerate(zip(bm25, coseno)):
            normalizado = b / max_bm25 if max_bm25 else 0.0
            score = 0.7 * normalizado + 0.3 * c
            if score > 0 and math.isfinite(score):
                puntuaciones.append((score, indice))
        puntuaciones.sort(key=lambda item: (-item[0], item[1]))
        resultados = []
        for score, indice in puntuaciones[:max_results]:
            resultado = dict(self.passages[indice])
            resultado["relevance_score"] = round(score, 6)
            resultado["retrieval"] = "bm25+vector-cosine"
            resultados.append(resultado)
        return resultados


class LocalDocumentSearchAPI(SearchAPI):
    """Búsqueda offline sobre documentos locales, sin embeddings remotos."""

    def __init__(self, paths: Iterable[str]):
        self.passages = load_documents(paths)
        self.index = PassageIndex(self.passages)

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        return self.index.search(query, max_results)


class CompositeSearchAPI(SearchAPI):
    """Combina proveedores en orden declarado y deduplica URL + localización."""

    def __init__(self, providers: Iterable[SearchAPI]):
        self.providers = list(providers)
        if not self.providers:
            raise ValueError("CompositeSearchAPI exige al menos un proveedor")

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        resultados = []
        vistos = set()
        for provider in self.providers:
            for resultado in provider.search(query, max_results):
                clave = (resultado.get("url"), resultado.get("location"))
                if clave not in vistos:
                    vistos.add(clave)
                    resultados.append(resultado)
        return resultados[:max_results]


class FullTextSearchAPI(SearchAPI):
    """Descarga y segmenta páginas completas de otro buscador.

    No hay caída silenciosa a snippets: los errores parciales se reportan en
    `errors` y stderr; si ninguna fuente puede leerse, se eleva RuntimeError.
    """

    def __init__(self, search_api: SearchAPI, timeout: int = 20,
                 max_sources: int = 3, max_bytes: int = MAX_FETCH_BYTES):
        self.search_api = search_api
        self.timeout = timeout
        self.max_sources = max_sources
        self.max_bytes = max_bytes
        self.errors: List[str] = []

    def _get(self, url: str):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not _es_host_publico(parsed.netloc):
            raise ValueError(f"URL no pública o esquema no admitido: {url}")
        return requests.get(url, headers={"User-Agent": USER_AGENT},
                            timeout=self.timeout, allow_redirects=False, stream=True)

    def _fetch(self, url: str) -> Tuple[bytes, str, str]:
        actual = url
        for _ in range(4):
            response = self._get(actual)
            try:
                if response.status_code in (301, 302, 303, 307, 308):
                    destino = response.headers.get("Location")
                    if not destino:
                        raise RuntimeError("Redirección sin Location")
                    actual = urljoin(actual, destino)
                    continue
                response.raise_for_status()
                tipo = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                if tipo not in ("text/html", "application/xhtml+xml", "text/plain"):
                    raise RuntimeError(f"Content-Type no textual: {tipo or 'desconocido'}")
                datos = bytearray()
                for bloque in response.iter_content(8192):
                    datos.extend(bloque)
                    if len(datos) > self.max_bytes:
                        raise ValueError(f"Respuesta supera {self.max_bytes} bytes")
                return bytes(datos), response.encoding or "utf-8", actual
            finally:
                response.close()
        raise RuntimeError("Demasiadas redirecciones")

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        if max_results <= 0:
            return []
        self.errors = []
        candidatos = self.search_api.search(query, self.max_sources)
        pasajes = []
        for candidato in candidatos:
            url = candidato.get("url", "")
            try:
                data, encoding, final_url = self._fetch(url)
                if not data:
                    raise RuntimeError("Contenido vacío")
                texto = _texto_html(data, encoding)
                if not texto:
                    raise RuntimeError("Sin texto extraíble")
                pasajes.extend(_resultados_texto(
                    candidato.get("title") or final_url,
                    final_url, texto,
                    f"fulltext:{candidato.get('source', 'web')}",
                    _sha256(data), "contenido completo"))
            except (requests.RequestException, OSError, RuntimeError, ValueError) as exc:
                mensaje = f"{url}: {exc}"
                self.errors.append(mensaje)
                print(f"[FullTextSearchAPI] {mensaje}", file=sys.stderr)
        if not pasajes:
            detalle = "; ".join(self.errors) or "sin resultados"
            raise RuntimeError(f"No se pudo recuperar contenido completo: {detalle}")
        return PassageIndex(pasajes).search(query, max_results)
