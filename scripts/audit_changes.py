#!/usr/bin/env python3
"""Auditoría determinista de un diff para detectar señales de cambios no deseados.

No detecta autoría ni intención: detecta patrones mecánicos compatibles con
scope creep, sustitución de requisitos, test tampering y debilitamiento de
gates. Es read-only, offline y no llama a ningún modelo.

Uso:
    python3 scripts/audit_changes.py --staged
    python3 scripts/audit_changes.py --base origin/main
    git diff origin/main...HEAD | python3 scripts/audit_changes.py --diff -
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from evidence import EvidenceKind, formato_resumen, resumen_evidencias  # noqa: E402

SEVERIDADES = ("alta", "media", "baja")
ORDEN_SEVERIDAD = {severidad: indice for indice, severidad in
                   enumerate(SEVERIDADES)}

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_TEST_FUNC = re.compile(
    r"^\s*(?:async\s+)?def\s+test_\w+|^\s*(?:it|test)\s*\(|^\s*func\s+Test\w+")
_ASSERT = re.compile(
    r"(\bassert\w*|\bself\.assert\w+|\bexpect\s*\(|\bshould\b|"
    r"\bpytest\.raises\b|\bassertRaises\b)")
_MATCHER_FUERTE = re.compile(
    r"\b(assertEqual|assertIn|assertGreater|assertLess|assertAlmostEqual|"
    r"assertRaises|assertIs)\b|\.toBe\(|\.toEqual\(|\.toContain\(")
_MATCHER_FLOJO = re.compile(
    r"\b(assertTrue|assertFalse|assertIsNotNone|assertIsNone)\b|"
    r"\.toBeDefined\(|\.toBeTruthy\(|\.toBeFalsy\(")
_SKIP = re.compile(
    r"^\s*(@pytest\.mark\.(?:skip|xfail)\b|@unittest\.skip\b|"
    r"self\.skipTest\s*\(|pytest\.skip\s*\(|it\.skip\s*\(|xit\s*\(|"
    r"t\.Skip\s*\(|test\.skip\s*\()")
_SUPPR_BLANDA = re.compile(
    r"(#\s*noqa\s*$|#\s*type:\s*ignore\s*$|//\s*@ts-nocheck\b|"
    r"/\*\s*eslint-disable\s*\*/|#\s*ruff:\s*noqa\b|"
    r"#\s*mypy:\s*ignore-errors\b|//\s*nolint\s*$)")
_SUPPR_ESPECIFICA = re.compile(
    r"(#\s*noqa:\s*[A-Z0-9]+|#\s*type:\s*ignore\[|"
    r"//\s*eslint-disable-next-line|//\s*@ts-ignore\b|"
    r"#\[allow\([^)]+\)\])")
_COV = re.compile(
    r"(fail_under|coverageThreshold|cov-fail-under|fail-under)\D*(\d+)",
    re.I)
_CONFIG_BLOQUEO = re.compile(
    r"([\"']?(?:strict|noimplicitany)[\"']?\s*[:=]\s*false|"
    r"[\"']?ignore_errors[\"']?\s*[:=]\s*true|"
    r"continue-on-error\s*:\s*true|allow_failure\s*:\s*true)", re.I)
_CONFIG_REVISION = re.compile(
    r"(--ignore\b|extend-ignore|[\"']?exclude[\"']?\s*[:=]|"
    r"[\"']?omit[\"']?\s*[:=]|ignorepatterns|coverage\s*:\s*false)", re.I)
_DEP_TXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[^\]]+\])?\s*([<>=!~].*)?$")
_DEP_PYPROJECT = re.compile(
    r'^\s*"[A-Za-z0-9][A-Za-z0-9._-]*(\[[^\]]+\])?\s*[<>=!~]')
_PELIGROS = (
    (re.compile(r"\bgit\s+push\b[^\n]*(?:--force|-f)\b"), "git push --force", "alta"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard", "alta"),
    (re.compile(r"\brm\s+-rf\b"), "rm -rf", "alta"),
    (re.compile(r"--no-verify\b"), "--no-verify", "alta"),
    (re.compile(r"\b(?:curl|wget)\b[^\n]*\|\s*(?:bash|sh)\b"),
     "descarga ejecutada con shell", "alta"),
    (re.compile(r"\bchmod\s+777\b"), "chmod 777", "media"),
    (re.compile(r"\b(?:eval|exec)\s*\("), "eval/exec", "media"),
)
_SECRETO = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{12,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"(?i:password|token|secret|api[_-]?key)\s*[:=]\s*\S+)")

RUTAS_TEST = {"tests", "test", "spec", "specs", "__tests__", "cypress", "e2e",
              "holdout"}
EXTENSIONES_TEST = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java",
                    ".rb", ".rs"}
EXTENSIONES_CODIGO = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java",
                      ".rb", ".rs"}
LOCKS = {
    "requirements.lock", "poetry.lock", "uv.lock", "pipfile.lock", "pdm.lock",
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "cargo.lock",
    "go.sum", "gradle.lockfile", "packages.lock.json",
}
MANIFIESTOS = {
    "pyproject.toml", "setup.py", "setup.cfg", "package.json", "cargo.toml",
    "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
}
CONFIGS = {
    "pyproject.toml", "setup.cfg", "tox.ini", "pytest.ini", "tsconfig.json",
    "package.json", "makefile", ".coveragerc", "codecov.yml",
    ".pre-commit-config.yaml",
}


@dataclass
class OpcionesAuditoria:
    permitir: List[str] = field(default_factory=list)
    max_archivos: int = 20
    max_lineas: int = 800

    def __post_init__(self) -> None:
        self.permitir = [p.strip().strip("/") for p in self.permitir if p.strip()]


@dataclass
class LineaDiff:
    numero: int
    texto: str


@dataclass
class ArchivoDiff:
    ruta: str
    nuevo: bool = False
    borrado: bool = False
    binario: bool = False
    agregadas: List[LineaDiff] = field(default_factory=list)
    eliminadas: List[LineaDiff] = field(default_factory=list)


@dataclass
class Hallazgo:
    regla: str
    severidad: str
    archivo: str
    linea: int
    descripcion: str
    evidencia: str
    tipo_evidencia: EvidenceKind = EvidenceKind.VERIFIED_REAL

    def a_dict(self):
        return {
            "regla": self.regla,
            "severidad": self.severidad,
            "archivo": self.archivo,
            "linea": self.linea,
            "descripcion": self.descripcion,
            "evidencia": self.evidencia,
            "tipo_evidencia": self.tipo_evidencia.value,
        }


def parsear_diff(texto: str) -> List[ArchivoDiff]:
    """Parsea un diff unificado de git; no ejecuta nada."""
    archivos: List[ArchivoDiff] = []
    actual: Optional[ArchivoDiff] = None
    nueva_linea = 0
    en_hunk = False
    for linea in texto.splitlines():
        if linea.startswith("diff --git "):
            resto = linea[len("diff --git "):]
            ruta = resto.split(" b/", 1)[1] if " b/" in resto else resto
            actual = ArchivoDiff(ruta=ruta)
            archivos.append(actual)
            en_hunk = False
            continue
        if actual is None:
            continue
        if not en_hunk and linea.startswith("new file mode "):
            actual.nuevo = True
            continue
        if not en_hunk and linea.startswith("deleted file mode "):
            actual.borrado = True
            continue
        if not en_hunk and (linea.startswith("Binary files ")
                            or linea.startswith("GIT binary patch")):
            actual.binario = True
            continue
        if not en_hunk and linea.startswith("--- "):
            ruta = linea[4:].strip()
            if ruta != "/dev/null":
                actual.ruta = ruta[2:] if ruta.startswith("a/") else ruta
            continue
        if not en_hunk and linea.startswith("+++ "):
            ruta = linea[4:].strip()
            if ruta != "/dev/null":
                actual.ruta = ruta[2:] if ruta.startswith("b/") else ruta
            continue
        hunk = _HUNK.match(linea)
        if hunk:
            nueva_linea = int(hunk.group(1))
            en_hunk = True
            continue
        if not en_hunk:
            continue
        if linea.startswith("+"):
            actual.agregadas.append(LineaDiff(nueva_linea, linea[1:]))
            nueva_linea += 1
        elif linea.startswith("-"):
            actual.eliminadas.append(LineaDiff(nueva_linea, linea[1:]))
        elif linea.startswith(" "):
            nueva_linea += 1
    return [archivo for archivo in archivos if archivo.ruta]


def _permitido(ruta: str, permitir: Sequence[str]) -> bool:
    return any(ruta == prefijo or ruta.startswith(prefijo.rstrip("/") + "/")
               for prefijo in permitir)


def _es_test(ruta: str) -> bool:
    p = Path(ruta)
    nombre = p.name.lower()
    if nombre == "conftest.py":
        return True
    if p.suffix.lower() not in EXTENSIONES_TEST:
        return False
    partes = {parte.lower() for parte in p.parts[:-1]}
    return bool(partes & RUTAS_TEST) or nombre.startswith("test_") \
        or nombre.endswith("_test.py") or nombre.endswith("_test.go") \
        or ".test." in nombre or ".spec." in nombre


def _es_codigo(ruta: str) -> bool:
    return Path(ruta).suffix.lower() in EXTENSIONES_CODIGO


def _es_lock(ruta: str) -> bool:
    return Path(ruta).name.lower() in LOCKS


def _es_manifiesto(ruta: str) -> bool:
    nombre = Path(ruta).name.lower()
    return nombre in MANIFIESTOS or bool(re.match(r"requirements.*\.(txt|in)$",
                                                  nombre))


def _es_requisitos(ruta: str) -> bool:
    nombre = Path(ruta).name.lower()
    return (ruta == "docs/REQUISITOS.md" or ruta.startswith("specs/")
            or (nombre.startswith("requisitos")
                and nombre.endswith((".md", ".txt", ".yaml", ".yml"))))


def _es_config(ruta: str) -> bool:
    nombre = Path(ruta).name.lower()
    return (nombre in CONFIGS or ruta.startswith(".github/")
            or nombre.startswith("eslint.config")
            or nombre in {".eslintrc", ".eslintrc.json", ".eslintrc.js"})


def _es_config_cobertura(ruta: str) -> bool:
    nombre = Path(ruta).name.lower()
    return nombre in {"pyproject.toml", "setup.cfg", "tox.ini", "pytest.ini",
                      "package.json", ".coveragerc", "codecov.yml"} \
        or nombre.startswith("jest.config")


def _es_ejecutable(ruta: str) -> bool:
    p = Path(ruta)
    return (p.suffix.lower() in {".sh", ".bash", ".zsh"}
            or p.name == "Makefile" or ruta.startswith(".github/workflows/"))


def _redactar(texto: str, maximo: int = 140) -> str:
    limpio = _SECRETO.sub("[REDACTADO]", texto.strip())
    return limpio[:maximo] + ("…" if len(limpio) > maximo else "")


def _es_comentario(texto: str) -> bool:
    return texto.strip().startswith(("#", "//"))


def _es_fixture(texto: str) -> bool:
    """Línea que parece dato de test (tupla, lista o dict literal)."""
    return texto.strip().startswith(("(", "[", "{"))


def _add(hallazgos: List[Hallazgo], regla: str, severidad: str, archivo: str,
         linea: int, descripcion: str, evidencia: str) -> None:
    hallazgos.append(Hallazgo(regla, severidad, archivo, linea, descripcion,
                              _redactar(evidencia)))


def _revisar_rutas(ad: ArchivoDiff, opciones: OpcionesAuditoria,
                   hallazgos: List[Hallazgo]) -> None:
    ruta = ad.ruta
    if _es_test(ruta) and ad.borrado:
        _add(hallazgos, "test_borrado", "alta", ruta, 0,
             "archivo de test eliminado", ruta)
        return
    if ruta.startswith("holdout/"):
        _add(hallazgos, "holdout_modificado", "media", ruta, 0,
             "holdout modificado; revisar y actualizar hashes", ruta)
        return
    if _permitido(ruta, opciones.permitir):
        return
    nombre = Path(ruta).name.lower()
    if (nombre == ".env" or
            (nombre.startswith(".env.") and nombre not in {
                ".env.example", ".env.sample", ".env.template"}) or
            nombre.endswith((".pem", ".key")) or
            nombre in {"id_rsa", "id_ed25519"}):
        _add(hallazgos, "ruta_sensible", "alta", ruta, 0,
             "archivo sensible modificado", ruta)
        return
    if (ruta.startswith(".github/") or ruta.startswith("scripts/hooks/")
            or nombre in {".gitlab-ci.yml", ".pre-commit-config.yaml"}):
        _add(hallazgos, "ci_hooks", "alta", ruta, 0,
             "configuración de CI/hooks modificada", ruta)
        return
    if _es_test(ruta):
        _add(hallazgos, "tests_modificados", "media", ruta, 0,
             "tests modificados; revisar integridad", ruta)
        return
    if _es_lock(ruta):
        _add(hallazgos, "lockfile", "media", ruta, 0,
             "lockfile modificado", ruta)
        return
    if _es_requisitos(ruta):
        _add(hallazgos, "requisitos_modificados", "media", ruta, 0,
             "requisitos o especificación modificados", ruta)
        return
    if ruta == "AGENTS.md":
        _add(hallazgos, "reglas_modificadas", "media", ruta, 0,
             "reglas del proyecto modificadas", ruta)
        return
    if _es_manifiesto(ruta):
        _add(hallazgos, "manifiesto", "media", ruta, 0,
             "manifiesto o dependencias modificados", ruta)
        return
    if nombre in {"makefile", "tox.ini", "pytest.ini", "setup.cfg"}:
        _add(hallazgos, "config_build", "media", ruta, 0,
             "configuración de build/tests modificada", ruta)
        return
    if ad.borrado:
        _add(hallazgos, "archivo_eliminado", "media", ruta, 0,
             "archivo eliminado", ruta)
    if ad.binario:
        _add(hallazgos, "binario", "media", ruta, 0,
             "archivo binario modificado", ruta)


def _es_assert(linea: LineaDiff) -> bool:
    texto = linea.texto.strip()
    if _es_fixture(texto) or texto.startswith(
            ("def ", "async def ", "class ", "#", "//", "*")):
        return False
    return bool(_ASSERT.search(texto))


def _revisar_tests(ad: ArchivoDiff, hallazgos: List[Hallazgo]) -> None:
    removed_funcs = sum(1 for linea in ad.eliminadas
                        if _TEST_FUNC.search(linea.texto))
    added_funcs = sum(1 for linea in ad.agregadas
                      if _TEST_FUNC.search(linea.texto))
    removed_asserts = [linea for linea in ad.eliminadas
                       if _es_assert(linea)]
    added_asserts = [linea for linea in ad.agregadas if _es_assert(linea)]

    if removed_funcs > added_funcs:
        _add(hallazgos, "test_eliminado", "media", ad.ruta, 0,
             f"{removed_funcs - added_funcs} función(es) de test eliminada(s)",
             "diff")
    elif len(removed_asserts) > len(added_asserts):
        severidad = "alta" if not added_asserts else "media"
        _add(hallazgos, "asserts_eliminados", severidad, ad.ruta,
             removed_asserts[0].numero,
             f"{len(removed_asserts)} asserts eliminados y "
             f"{len(added_asserts)} añadidos",
             removed_asserts[0].texto)

    removed_matcher = [linea for linea in ad.eliminadas
                       if not _es_fixture(linea.texto)
                       and _MATCHER_FUERTE.search(linea.texto)]
    added_loose = [linea for linea in ad.agregadas
                   if not _es_fixture(linea.texto)
                   and _MATCHER_FLOJO.search(linea.texto)]
    if removed_matcher and added_loose:
        _add(hallazgos, "matcher_flojo", "media", ad.ruta,
             added_loose[0].numero,
             "matcher fuerte sustituido por uno más flojo",
             added_loose[0].texto)

    if ad.nuevo and added_funcs and not added_asserts:
        _add(hallazgos, "test_sin_asserts", "media", ad.ruta, 0,
             "archivo de test nuevo sin aserciones detectadas", "diff")


def _valores(patron: re.Pattern, lineas: List[LineaDiff]) -> List[int]:
    valores = []
    for linea in lineas:
        if _es_comentario(linea.texto):
            continue
        valores.extend(int(m.group(2)) for m in patron.finditer(linea.texto))
    return valores


def _revisar_cobertura(ad: ArchivoDiff, hallazgos: List[Hallazgo]) -> None:
    eliminadas = _valores(_COV, ad.eliminadas)
    agregadas = _valores(_COV, ad.agregadas)
    if eliminadas and not agregadas:
        _add(hallazgos, "cobertura_rebajada", "alta", ad.ruta, 0,
             "umbral de cobertura eliminado", "diff")
    elif eliminadas and agregadas and min(agregadas) < max(eliminadas):
        _add(hallazgos, "cobertura_rebajada", "alta", ad.ruta, 0,
             f"umbral de cobertura rebajado de {max(eliminadas)} "
             f"a {min(agregadas)}", "diff")
    elif agregadas and not eliminadas:
        _add(hallazgos, "cobertura_revision", "media", ad.ruta, 0,
             "umbral de cobertura añadido; revisar intención", "diff")


def _revisar_dependencias(ad: ArchivoDiff, hallazgos: List[Hallazgo]) -> None:
    nuevas: List[LineaDiff] = []
    for linea in ad.agregadas:
        texto = linea.texto.strip()
        if not texto or texto.startswith(("#", "-", "//", "git+", "http",
                                         "file:")):
            continue
        if ad.ruta.endswith((".txt", ".in")) and _DEP_TXT.match(texto):
            nuevas.append(linea)
        elif ad.ruta.endswith("pyproject.toml") \
                and _DEP_PYPROJECT.match(texto):
            nuevas.append(linea)
    if nuevas:
        _add(hallazgos, "dependencia_nueva", "media", ad.ruta,
             nuevas[0].numero,
             f"{len(nuevas)} posible(s) dependencia(s) añadida(s)",
             nuevas[0].texto)


def _revisar_contenido(ad: ArchivoDiff,
                       hallazgos: List[Hallazgo]) -> None:
    if ad.borrado:
        return
    ruta = ad.ruta
    if _es_test(ruta):
        for linea in ad.agregadas:
            if _es_comentario(linea.texto) or _es_fixture(linea.texto):
                continue
            if _SKIP.search(linea.texto):
                _add(hallazgos, "skip_añadido", "alta", ruta, linea.numero,
                     "skip/xfail añadido a un test", linea.texto)
        _revisar_tests(ad, hallazgos)

    if _es_codigo(ruta) or _es_config(ruta) or _es_ejecutable(ruta):
        for linea in ad.agregadas:
            if _es_fixture(linea.texto):
                continue
            if _SUPPR_BLANDA.search(linea.texto):
                _add(hallazgos, "supresion_global", "alta", ruta,
                     linea.numero, "supresión global de un gate añadida",
                     linea.texto)
            elif _SUPPR_ESPECIFICA.search(linea.texto):
                _add(hallazgos, "supresion_especifica", "media", ruta,
                     linea.numero, "supresión específica añadida",
                     linea.texto)

    if _es_config_cobertura(ruta):
        _revisar_cobertura(ad, hallazgos)

    if _es_config(ruta):
        for linea in ad.agregadas:
            if _es_comentario(linea.texto) or _es_fixture(linea.texto):
                continue
            if _CONFIG_BLOQUEO.search(linea.texto):
                _add(hallazgos, "config_relajada", "alta", ruta,
                     linea.numero, "configuración de gate relajada",
                     linea.texto)
            elif _CONFIG_REVISION.search(linea.texto):
                _add(hallazgos, "config_revisar", "media", ruta,
                     linea.numero, "configuración de gate modificada",
                     linea.texto)

    if _es_manifiesto(ruta):
        _revisar_dependencias(ad, hallazgos)

    if _es_ejecutable(ruta):
        for linea in ad.agregadas:
            if _es_comentario(linea.texto) or _es_fixture(linea.texto):
                continue
            for patron, descripcion, severidad in _PELIGROS:
                if patron.search(linea.texto):
                    _add(hallazgos, "comando_peligroso", severidad, ruta,
                         linea.numero, descripcion, linea.texto)

    if _es_codigo(ruta):
        for linea in ad.agregadas:
            if _es_comentario(linea.texto) or _es_fixture(linea.texto):
                continue
            if re.search(r"\b(?:eval|exec)\s*\(", linea.texto):
                _add(hallazgos, "eval_exec", "media", ruta, linea.numero,
                     "eval/exec añadido en código", linea.texto)


def _revisar_presupuesto(archivos: List[ArchivoDiff],
                         opciones: OpcionesAuditoria,
                         hallazgos: List[Hallazgo]) -> None:
    if opciones.max_archivos > 0 and len(archivos) > opciones.max_archivos:
        _add(hallazgos, "presupuesto_archivos", "media", "", 0,
             f"{len(archivos)} archivos > {opciones.max_archivos}", "diff")
    total = sum(len(a.agregadas) + len(a.eliminadas) for a in archivos)
    if opciones.max_lineas > 0 and total > opciones.max_lineas:
        _add(hallazgos, "presupuesto_lineas", "media", "", 0,
             f"{total} líneas cambiadas > {opciones.max_lineas}", "diff")


def auditar_diff(texto: str, opciones: Optional[OpcionesAuditoria] = None):
    """Devuelve el informe de señales del diff; no escribe ni ejecuta nada."""
    opciones = opciones or OpcionesAuditoria()
    archivos = parsear_diff(texto)
    hallazgos: List[Hallazgo] = []
    for ad in archivos:
        _revisar_rutas(ad, opciones, hallazgos)
        _revisar_contenido(ad, hallazgos)
    _revisar_presupuesto(archivos, opciones, hallazgos)
    hallazgos.sort(key=lambda h: (ORDEN_SEVERIDAD.get(h.severidad, 3),
                                  h.archivo, h.linea, h.regla))
    resumen = {severidad: sum(1 for h in hallazgos
                              if h.severidad == severidad)
               for severidad in SEVERIDADES}
    veredicto = ("BLOQUEAR" if resumen["alta"]
                 else "REVISAR" if resumen["media"] or resumen["baja"]
                 else "OK")
    return {
        "archivos": len(archivos),
        "lineas_agregadas": sum(len(a.agregadas) for a in archivos),
        "lineas_eliminadas": sum(len(a.eliminadas) for a in archivos),
        "presupuesto": {
            "max_archivos": opciones.max_archivos,
            "max_lineas": opciones.max_lineas,
        },
        "hallazgos": [h.a_dict() for h in hallazgos],
        "resumen": resumen,
        "veredicto": veredicto,
        "nota": "Señales mecánicas; no prueban autoría ni intención. "
                "Un REVISAR puede ser legítimo.",
        "evidencia": resumen_evidencias([h.tipo_evidencia for h in hallazgos]),
    }


def informe_texto(informe) -> str:
    max_archivos = informe["presupuesto"]["max_archivos"]
    max_lineas = informe["presupuesto"]["max_lineas"]
    presupuesto = (
        f"{max_archivos if max_archivos > 0 else 'sin límite'} archivos / "
        f"{max_lineas if max_lineas > 0 else 'sin límite'} líneas")
    lineas = [
        f"AUDITORÍA DE CAMBIOS (read-only): {informe.get('fuente', '?')}",
        f"Archivos: {informe['archivos']} | "
        f"+{informe['lineas_agregadas']}/-{informe['lineas_eliminadas']} | "
        f"presupuesto: {presupuesto}",
        "",
    ]
    if not informe["hallazgos"]:
        lineas.append("Sin señales en este diff.")
    for h in informe["hallazgos"]:
        ubicacion = (f"{h['archivo']}:{h['linea']}"
                     if h["archivo"] and h["linea"]
                     else (h["archivo"] or "diff"))
        lineas.append(f"[{h['severidad'].upper()}] {h['regla']} "
                      f"{ubicacion} — {h['descripcion']}")
        lineas.append(f"    evidencia: {h['evidencia']}")
    lineas.append("")
    resumen = informe["resumen"]
    lineas.append(f"VEREDICTO: {informe['veredicto']} "
                  f"({resumen['alta']} alta, {resumen['media']} media, "
                  f"{resumen['baja']} baja)")
    lineas.append(f"Evidencia: {formato_resumen(informe['evidencia'])}")
    lineas.append(f"Nota: {informe['nota']}")
    return "\n".join(lineas)


def _obtener_diff(args) -> Tuple[str, str]:
    if args.diff is not None:
        if args.diff == "-":
            return sys.stdin.read(), "stdin"
        try:
            return Path(args.diff).read_text(encoding="utf-8"), args.diff
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(f"No se pudo leer {args.diff}: {exc}") from exc

    if args.base:
        comando = ["git", "diff", "--unified=0", "--no-color",
                   "--no-ext-diff", f"{args.base}...HEAD"]
        fuente = f"git diff {args.base}...HEAD"
    elif args.staged:
        comando = ["git", "diff", "--cached", "--unified=0", "--no-color",
                   "--no-ext-diff"]
        fuente = "git diff --cached"
    else:
        raise ValueError("indica --staged, --base o --diff")

    try:
        proceso = subprocess.run(comando, capture_output=True, text=True,
                                 check=False)
    except OSError as exc:
        raise ValueError(f"No se pudo ejecutar git diff: {exc}") from exc
    if proceso.returncode != 0:
        detalle = (proceso.stderr or proceso.stdout).strip()[:200]
        raise ValueError(f"git diff falló: {detalle}")
    return proceso.stdout, fuente


def _codigo_salida(veredicto: str, umbral: str) -> int:
    if umbral == "ninguno":
        return 0
    if umbral == "bloquear":
        return 1 if veredicto == "BLOQUEAR" else 0
    return 0 if veredicto == "OK" else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audita un diff en busca de señales de cambios no deseados "
                    "(read-only, offline).")
    fuente = parser.add_mutually_exclusive_group()
    fuente.add_argument("--staged", action="store_true",
                        help="audita el diff preparado (git diff --cached)")
    fuente.add_argument("--base", metavar="REV",
                        help="audita REV...HEAD (p. ej. origin/main)")
    fuente.add_argument("--diff", metavar="ARCHIVO",
                        help="lee un diff de ARCHIVO; '-' para stdin")
    parser.add_argument("--permitir", action="append", default=[],
                        metavar="RUTA",
                        help="suprime hallazgos de ruta para ese prefijo; "
                             "las reglas de contenido siguen activas")
    parser.add_argument("--max-archivos", type=int, default=20,
                        help="presupuesto de archivos (0 = sin límite)")
    parser.add_argument("--max-lineas", type=int, default=800,
                        help="presupuesto de líneas cambiadas (0 = sin límite)")
    parser.add_argument("--fallar-en", choices=("ninguno", "revisar", "bloquear"),
                        default="revisar",
                        help="cuándo devolver código 1 (defecto: revisar)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.max_archivos < 0 or args.max_lineas < 0:
        print("ERROR: los presupuestos no pueden ser negativos",
              file=sys.stderr)
        return 2

    opciones = OpcionesAuditoria(
        permitir=args.permitir, max_archivos=args.max_archivos,
        max_lineas=args.max_lineas)
    try:
        texto, fuente_diff = _obtener_diff(args)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    informe = auditar_diff(texto, opciones)
    informe["fuente"] = fuente_diff
    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        print(informe_texto(informe))
    return _codigo_salida(informe["veredicto"], args.fallar_en)


if __name__ == "__main__":
    sys.exit(main())
