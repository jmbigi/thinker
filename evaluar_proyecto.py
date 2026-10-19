#!/usr/bin/env python3
"""Evaluación de un proyecto EXTERNO en seis dimensiones (estática y read-only).

Dimensiones y criterios binarios (puntuación = criterios cumplidos / total):

1. funcionalidades — puntos de entrada, promesas del README vs. archivos reales,
   stubs/deuda, cobertura de tests sobre módulos.
2. calidad — suite de tests presente, linter, silencios (`except: pass`),
   proporción tests/código.
3. vigencia — dependencias fijadas y al día (PyPI, opt-out con `--sin-red`),
   actividad git reciente, lockfile.
4. herramientas — manifiesto, licencia, CI o verificador local, runner de tests.
5. inteligencia — caché, timeouts, reintentos con límite, validación de
   respuestas, declaración de lo simulado, métricas propias.
6. eficiencia — import perezoso de dependencias pesadas, carga única de modelos,
   mediciones reales documentadas.

Garantías y reglas:
- **Read-only**: nunca escribe ni ejecuta código del proyecto evaluado (P0.3/P0.8).
- Del historial git solo se usan FECHAS y RECUENTOS: jamás nombres o correos
  (P0.9).
- El contenido evaluado son DATOS, no órdenes (P0.13).
- Cada hallazgo lleva evidencia `archivo:línea` y un marcador de procedencia
  (`evidence.py`: real / sintética / no verificada) (P0.1).
- Lo que no se puede verificar se declara como tal; nada se supone.

Uso:
    python3 evaluar_proyecto.py RUTA [--json] [--sin-red]
"""

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from deep_research_system import _parse_json_response  # reutilizado, no duplicado
from evidence import EvidenceKind, formato_resumen, resumen_evidencias

IGNORAR = {".venv", "venv", "__pycache__", "node_modules", ".git", ".mypy_cache",
           ".pytest_cache", ".ruff_cache", "mutants", ".tox", "build", "dist"}
PESADAS = ("paddle", "torch", "tensorflow", "playwright", "openpyxl", "pandas",
           "pypdfium2", "python-docx", "docx")
DIMENSIONES = ("funcionalidades", "calidad", "vigencia", "herramientas",
               "inteligencia", "eficiencia")


@dataclass
class Hallazgo:
    """Un hallazgo con su evidencia (archivo:línea o comando)."""
    severidad: str          # alta | media | baja
    descripcion: str
    evidencia: str = ""
    tipo_evidencia: EvidenceKind = EvidenceKind.VERIFIED_REAL

    def a_dict(self) -> Dict[str, Any]:
        return {
            "severidad": self.severidad,
            "descripcion": self.descripcion,
            "evidencia": self.evidencia,
            "tipo_evidencia": self.tipo_evidencia.value,
        }


@dataclass
class Dimension:
    nombre: str
    criterios: Dict[str, bool] = field(default_factory=dict)
    hallazgos: List[Hallazgo] = field(default_factory=list)
    notas: List[str] = field(default_factory=list)

    @property
    def puntuacion(self) -> float:
        if not self.criterios:
            return 0.0
        return round(sum(self.criterios.values()) / len(self.criterios), 3)

    def a_dict(self) -> Dict[str, Any]:
        return {
            "puntuacion": self.puntuacion,
            "criterios": self.criterios,
            "hallazgos": [h.a_dict() for h in self.hallazgos],
            "notas": self.notas,
        }


def archivos_python(ruta: Path) -> List[Path]:
    return sorted(p for p in ruta.rglob("*.py")
                  if not any(parte in IGNORAR for parte in p.parts))


def leer(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def lineas_silenciosas(texto: str) -> List[int]:
    """Líneas de `except ...:` cuyo cuerpo es `pass`/`continue` (silencios)."""
    lineas = texto.splitlines()
    sospechosas = []
    for i, linea in enumerate(lineas):
        if not re.match(r"\s*except\b", linea):
            continue
        for siguiente in lineas[i + 1:i + 4]:
            if not siguiente.strip():
                continue
            if re.match(r"\s*(pass|continue)\s*$", siguiente):
                sospechosas.append(i + 1)
            break
    return sospechosas


def _git(ruta: Path, *args: str) -> Optional[str]:
    """Ejecuta git SOLO con argumentos de fecha/recuento (nunca autores)."""
    try:
        salida = subprocess.run(["git", "-C", str(ruta), *args],
                                capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return salida.stdout.strip() if salida.returncode == 0 else None


# --- Dimensiones -----------------------------------------------------------

def evaluar_funcionalidades(ruta: Path, py: List[Path]) -> Dimension:
    dim = Dimension("funcionalidades")
    entradas = [p for p in py if 'if __name__ == "__main__"' in leer(p)]
    dim.criterios["f1_puntos_de_entrada"] = len(entradas) > 0
    dim.notas.append(f"{len(entradas)} módulos con punto de entrada")

    readme = ruta / "README.md"
    prometidos = set()
    if readme.exists():
        prometidos = set(re.findall(r"`([A-Za-z0-9_./-]+\.py)`", leer(readme)))
        existentes = set()
        for p in py:
            existentes.add(p.name)
            existentes.add(p.relative_to(ruta).as_posix())
        faltan = sorted(n for n in prometidos
                        if n not in existentes
                        and not any(e.endswith("/" + n) for e in existentes))
        dim.criterios["f2_readme_vs_realidad"] = not faltan
        for nombre in faltan:
            dim.hallazgos.append(Hallazgo(
                "alta", f"El README promete {nombre} y no existe",
                "README.md"))
    else:
        dim.criterios["f2_readme_vs_realidad"] = False
        dim.hallazgos.append(Hallazgo("media", "Sin README.md", str(ruta)))

    deuda = []
    for p in py:
        for i, linea in enumerate(leer(p).splitlines(), 1):
            if "#" not in linea:
                continue
            comentario = linea.split("#", 1)[1]
            # "TODO REAL" es el nombre de una regla de dominio en algunos
            # proyectos (no una marca de deuda): se excluye.
            if re.search(r"\b(TODO|FIXME|XXX)\b", comentario) \
                    and "TODO REAL" not in comentario:
                deuda.append(f"{p.relative_to(ruta)}:{i}")
    dim.criterios["f3_sin_deuda_declarada"] = not deuda
    if deuda:
        dim.hallazgos.append(Hallazgo(
            "baja", f"{len(deuda)} marcas TODO/FIXME/XXX", ", ".join(deuda[:5])))

    modulos_test = [p for p in py if p.name.startswith("test_")]
    dim.criterios["f4_tests_de_varios_modulos"] = len(modulos_test) > 1
    dim.notas.append(f"{len(modulos_test)} archivos de test")
    return dim


def detectar_comando_tests(ruta: Path) -> Optional[Dict[str, Any]]:
    """Comando de tests DECLARADO por el proyecto (nunca adivinado).

    Orden de preferencia, y se registra el origen: (1) target `test:` del
    Makefile, (2) comando explícito en un script de verificación o README,
    (3) convención `unittest discover -s tests` si existe tests/.
    """
    makefile = ruta / "Makefile"
    if makefile.exists() and re.search(r"^test:", leer(makefile), re.M):
        return {"comando": ["make", "test"], "origen": "Makefile (target test)"}

    for candidato in list((ruta / "scripts").glob("*.sh")) + [ruta / "README.md",
                                                              ruta / "AGENTS.md"]:
        if not candidato.exists():
            continue
        m = re.search(r"(python3? -m (?:unittest|pytest)[^\n`]*)", leer(candidato))
        if m:
            return {"comando": m.group(1).split(),
                    "origen": f"{candidato.relative_to(ruta)}"}

    if (ruta / "tests").is_dir():
        return {"comando": ["python3", "-m", "unittest", "discover", "-s", "tests"],
                "origen": "convención: existe tests/"}
    return None


def ejecutar_tests(ruta: Path, timeout: int = 900) -> Dict[str, Any]:
    """Ejecuta el comando de tests declarado (opt-in explícito, P0.8).

    Es lo ÚNICO que ejecuta código del proyecto evaluado y solo se hace con
    `--ejecutar-tests`. Sin shell (`shell=False`), con timeout y salida capturada.
    """
    deteccion = detectar_comando_tests(ruta)
    if deteccion is None:
        return {"ejecutado": False,
                "motivo": "no se encontró un comando de tests declarado"}

    inicio = time.monotonic()
    try:
        proceso = subprocess.run(deteccion["comando"], cwd=str(ruta),
                                 capture_output=True, text=True, timeout=timeout,
                                 shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ejecutado": True, "comando": " ".join(deteccion["comando"]),
                "origen": deteccion["origen"], "error": type(exc).__name__,
                "detalle": str(exc)[:200]}
    duracion = round(time.monotonic() - inicio, 1)
    salida = (proceso.stdout or "") + (proceso.stderr or "")
    resumen = re.search(r"^Ran (\d+) tests?", salida, re.M)
    return {
        "ejecutado": True,
        "comando": " ".join(deteccion["comando"]),
        "origen": deteccion["origen"],
        "codigo": proceso.returncode,
        "ok": proceso.returncode == 0,
        "tests": int(resumen.group(1)) if resumen else None,
        "resumen": next((linea for linea in reversed(salida.splitlines())
                         if linea.startswith(("OK", "FAILED"))), ""),
        "duracion_s": duracion,
    }


def evaluar_calidad(ruta: Path, py: List[Path],
                    ejecutar: bool = False) -> Dimension:
    dim = Dimension("calidad")
    modulos_test = [p for p in py if p.name.startswith("test_")]
    lineas_codigo = sum(len(leer(p).splitlines()) for p in py if p not in modulos_test)
    lineas_test = sum(len(leer(p).splitlines()) for p in modulos_test)

    dim.criterios["c1_suite_de_tests"] = bool(modulos_test)
    dim.notas.append(f"{lineas_test} líneas de test / {lineas_codigo} de código")

    if ejecutar:
        resultado = ejecutar_tests(ruta)
        dim.notas.append(f"suite: {resultado.get('resumen') or resultado.get('motivo')}"
                         f" ({resultado.get('comando', 'sin comando')}, "
                         f"{resultado.get('duracion_s', '?')}s)")
        dim.criterios["c1b_suite_pasa"] = bool(resultado.get("ok"))
        if not resultado.get("ok"):
            dim.hallazgos.append(Hallazgo(
                "alta", f"La suite NO pasa: {resultado.get('resumen') or resultado.get('error')}",
                resultado.get("comando", "?")))
    else:
        dim.notas.append("suite NO ejecutada (sin --ejecutar-tests): no verificado")

    linter = any((ruta / f).exists() for f in ("pyproject.toml", ".flake8",
                                               "setup.cfg", ".pylintrc"))
    linter = linter or bool(list(ruta.glob(".ruff.toml")))
    if linter:
        linter = any(re.search(t, leer(ruta / f))
                     for f in ("pyproject.toml", "setup.cfg", ".flake8")
                     for t in ("ruff", "flake8", "pylint")) or (ruta / ".ruff.toml").exists()
    dim.criterios["c2_linter_configurado"] = linter
    if not linter:
        dim.hallazgos.append(Hallazgo(
            "media", "Sin linter configurado (ruff/flake8/pylint)",
            "pyproject.toml/setup.cfg ausentes o sin configurar"))

    silencios = []
    for p in py:
        for linea in lineas_silenciosas(leer(p)):
            silencios.append(f"{p.relative_to(ruta)}:{linea}")
    dim.criterios["c3_sin_silencios"] = not silencios
    if silencios:
        dim.notas.append(f"silencios detectados: {len(silencios)}")
    for marca in silencios:
        dim.hallazgos.append(Hallazgo(
            "media", "`except` con `pass`/`continue` (P1.26)", marca))

    proporcion = lineas_test / lineas_codigo if lineas_codigo else 0.0
    dim.criterios["c4_tests_sobre_codigo_30pct"] = proporcion >= 0.3
    dim.notas.append(f"proporción test/código: {proporcion:.2f}")
    return dim


def _dependencias(ruta: Path) -> List[Dict[str, str]]:
    deps = []
    req = ruta / "requirements.txt"
    if req.exists():
        for linea in leer(req).splitlines():
            linea = linea.split("#")[0].strip()
            if not linea:
                continue
            m = re.match(r"([A-Za-z0-9_.\-]+)\s*(==|>=|~=|<=|>|<)?\s*([\w.]*)", linea)
            if m:
                deps.append({"nombre": m.group(1).lower(),
                             "operador": m.group(2) or "",
                             "version": m.group(3)})
    pyproject = ruta / "pyproject.toml"
    if pyproject.exists():
        texto = leer(pyproject)
        # Solo el bloque `dependencies = [...]` de [project]: el resto del
        # archivo tiene listas (source_paths, pytest_add_cli_args_test_selection,
        # [project.scripts]...) que NO son dependencias.
        bloque = re.search(r"^dependencies\s*=\s*\[(.*?)\]", texto,
                           re.M | re.S)
        if bloque:
            for item in re.findall(r'"([^"]+)"', bloque.group(1)):
                m = re.match(r"([A-Za-z0-9_.\-]+)\s*(==|>=|~=)?\s*([\w.]*)", item)
                if m:
                    deps.append({"nombre": m.group(1).lower(),
                                 "operador": m.group(2) or "",
                                 "version": m.group(3)})
    # Una misma dependencia declarada en varios manifiestos se cuenta una vez,
    # prefiriendo la declaración más específica (==).
    unicas: Dict[str, Dict[str, str]] = {}
    for dep in deps:
        previa = unicas.get(dep["nombre"])
        if previa is None or (previa["operador"] != "==" and dep["operador"] == "=="):
            unicas[dep["nombre"]] = dep
    return list(unicas.values())


def ultima_version_pypi(nombre: str, timeout: int = 15) -> Dict[str, Any]:
    """Última versión publicada; si falla, el MOTIVO va en `error` (no se oculta)."""
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{nombre}/json",
                                    timeout=timeout) as respuesta:
            return {"version": json.load(respuesta)["info"]["version"], "error": ""}
    except Exception as exc:  # noqa: BLE001 - el motivo se declara en el informe
        return {"version": None, "error": f"{type(exc).__name__}: {exc}"}


def evaluar_vigencia(ruta: Path, deps: List[Dict[str, str]],
                     con_red: bool = True) -> Dimension:
    dim = Dimension("vigencia")

    tiene_lock = any((ruta / f).exists() for f in
                     ("requirements.lock", "poetry.lock", "uv.lock", "Pipfile.lock"))
    sin_fijar = [d["nombre"] for d in deps if d["operador"] != "=="]
    # Un lockfile da reproducibilidad aunque el manifiesto use rangos.
    dim.criterios["v1_dependencias_fijadas"] = bool(deps) and (not sin_fijar or tiene_lock)
    if sin_fijar and not tiene_lock:
        dim.hallazgos.append(Hallazgo(
            "media", f"Dependencias sin fijar: {', '.join(sin_fijar)}",
            "requirements.txt/pyproject.toml"))
    elif sin_fijar:
        dim.notas.append("rangos en el manifiesto cubiertos por lockfile")

    dim.criterios["v2_lockfile"] = tiene_lock
    if not tiene_lock:
        dim.hallazgos.append(Hallazgo(
            "media", "Sin lockfile (instalación no reproducible)", str(ruta)))

    fecha = _git(ruta, "log", "-1", "--format=%ad", "--date=short")
    commits = _git(ruta, "rev-list", "--count", "HEAD")
    recientes = _git(ruta, "log", "--since=180 days ago", "--oneline")
    n_recientes = len(recientes.splitlines()) if recientes else 0
    dim.criterios["v3_actividad_reciente"] = bool(fecha) and n_recientes > 0
    dim.notas.append(f"último commit: {fecha or 'sin git'}; commits totales: "
                     f"{commits or '?'}; últimos 180 días: {n_recientes}")

    if not con_red:
        dim.criterios["v4_dependencias_al_dia"] = False
        dim.notas.append("comprobación PyPI OMITIDA (--sin-red): no verificado")
        return dim

    atrasadas, no_verificadas = [], []
    for d in deps:
        if d["operador"] != "==" or not d["version"]:
            continue
        consulta = ultima_version_pypi(d["nombre"])
        if consulta["error"]:
            no_verificadas.append(f"{d['nombre']} ({consulta['error']})")
            continue
        if consulta["version"] != d["version"]:
            atrasadas.append(f"{d['nombre']} {d['version']} -> {consulta['version']}")
    # "No se pudo comprobar" NO es "está al día": el criterio exige verificación.
    dim.criterios["v4_dependencias_al_dia"] = not atrasadas and not no_verificadas
    for marca in atrasadas:
        dim.hallazgos.append(Hallazgo("media", f"Dependencia atrasada: {marca}",
                                      "PyPI (api.pypi.org)"))
    if no_verificadas:
        dim.hallazgos.append(Hallazgo(
            "baja", "No se pudo comprobar en PyPI: " + "; ".join(no_verificadas),
            "PyPI", EvidenceKind.UNVERIFIED))
    return dim


LICENCIAS_LIBRES = ("mit", "bsd", "apache", "gpl", "lgpl", "mpl", "isc",
                    "unlicense", "cc0", "psf", "zlib", "python software")


def licencia_pypi(nombre: str, timeout: int = 15) -> Dict[str, Any]:
    """Licencia declarada en PyPI; si falla, el MOTIVO va en `error`.

    `libre` se decide por el clasificador OSI o, si no lo hay, por el nombre de
    la licencia en texto libre (muchos paquetes solo rellenan ese campo).
    """
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{nombre}/json",
                                    timeout=timeout) as respuesta:
            info = json.load(respuesta)["info"]
    except Exception as exc:  # noqa: BLE001 - el motivo se declara en el informe
        return {"licencia": "desconocida", "libre": False,
                "error": f"{type(exc).__name__}: {exc}"}
    aprobada = next((c for c in info.get("classifiers", [])
                     if c.startswith("License :: OSI Approved")), "")
    if aprobada:
        return {"licencia": aprobada.split("::")[-1].strip(), "libre": True,
                "error": ""}
    texto = ((info.get("license") or "").strip().splitlines() or [""])[0][:60]
    return {"licencia": texto or "desconocida",
            "libre": any(marca in texto.lower() for marca in LICENCIAS_LIBRES),
            "error": ""}


def evaluar_herramientas(ruta: Path, deps: List[Dict[str, str]] = None,
                         con_red: bool = True) -> Dimension:
    dim = Dimension("herramientas")
    manifiestos = [f for f in ("requirements.txt", "pyproject.toml", "setup.py",
                               "package.json", "Pipfile") if (ruta / f).exists()]
    dim.criterios["h1_manifiesto"] = bool(manifiestos)
    dim.notas.append(f"manifiestos: {', '.join(manifiestos) or 'ninguno'}")

    licencia = [p.name for p in ruta.iterdir()
                if p.is_file() and re.match(r"(LICEN[CS]E|COPYING)", p.name, re.I)]
    dim.criterios["h2_licencia"] = bool(licencia)
    if not licencia:
        dim.hallazgos.append(Hallazgo(
            "alta", "Sin archivo de licencia: el uso/reutilización queda sin "
                    "términos (P1.18)", str(ruta)))

    ci = bool(list(ruta.glob(".github/workflows/*"))) or \
        (ruta / ".gitlab-ci.yml").exists() or \
        bool(list((ruta / "scripts").glob("*verif*"))) or (ruta / "Makefile").exists()
    dim.criterios["h3_verificacion_automatizada"] = ci
    if not ci:
        dim.hallazgos.append(Hallazgo(
            "media", "Sin CI ni script de verificación local", str(ruta)))

    runner = any("unittest" in leer(p) or "pytest" in leer(p) for p in
                 list(ruta.glob("scripts/*")) + [ruta / "Makefile"])
    dim.criterios["h4_runner_de_tests_declarado"] = runner or bool(
        list(ruta.glob("tests/*")))

    # Licencias de las dependencias (P1.18): declaradas y libres.
    deps = deps or []
    if not deps:
        dim.notas.append("sin dependencias declaradas: licencias no aplican")
    elif not con_red:
        dim.notas.append("licencias de dependencias OMITIDAS (--sin-red)")
    else:
        sin_verificar, no_libres = [], []
        for dep in deps:
            info = licencia_pypi(dep["nombre"])
            if info.get("error"):
                sin_verificar.append(f"{dep['nombre']} ({info['error']})")
            elif not info["libre"]:
                no_libres.append(f"{dep['nombre']} ({info['licencia']})")
        dim.criterios["h5_licencias_libres"] = not no_libres and not sin_verificar
        dim.notas.append(f"licencias consultadas en PyPI: {len(deps)}")
        if no_libres:
            dim.hallazgos.append(Hallazgo(
                "media", f"Dependencias sin licencia libre declarada: "
                         f"{', '.join(no_libres)}", "PyPI"))
        if sin_verificar:
            dim.hallazgos.append(Hallazgo(
                "baja", f"Licencia no verificable en PyPI: "
                        f"{', '.join(sin_verificar)}", "PyPI",
                EvidenceKind.UNVERIFIED))
    return dim


def evaluar_inteligencia(ruta: Path, py: List[Path]) -> Dimension:
    dim = Dimension("inteligencia")
    texto = "\n".join(leer(p) for p in py)

    dim.criterios["i1_cachea_trabajo_repetido"] = bool(
        re.search(r"\b(lru_cache|@cache|caché|cache\[|_cache)\b", texto))
    dim.criterios["i2_timeouts_explicitos"] = bool(
        re.search(r"timeout\s*=", texto))
    dim.criterios["i3_reintentos_con_limite"] = bool(
        re.search(r"(max_retries|reintent|backoff|retry)", texto, re.I))
    dim.criterios["i4_valida_respuestas"] = bool(
        re.search(r"json\.loads|JSONDecodeError|_parse_", texto))
    dim.criterios["i5_declara_lo_simulado"] = bool(
        re.search(r"(simulad|mock)", texto, re.I))
    dim.criterios["i6_metricas_propias"] = bool(
        re.search(r"(benchmark|rúbrica|rubrica|metric|medición|medicion)", texto, re.I))

    for clave, nombre in (("i1_cachea_trabajo_repetido", "caché"),
                          ("i2_timeouts_explicitos", "timeouts explícitos"),
                          ("i3_reintentos_con_limite", "reintentos con límite"),
                          ("i4_valida_respuestas", "validación de respuestas"),
                          ("i5_declara_lo_simulado", "declaración de lo simulado"),
                          ("i6_metricas_propias", "métricas propias")):
        if not dim.criterios[clave]:
            dim.hallazgos.append(Hallazgo("baja", f"Sin señal de {nombre}", "—"))
    return dim


def evaluar_eficiencia(ruta: Path, py: List[Path],
                       pesadas_declaradas: List[str] = None) -> Dimension:
    dim = Dimension("eficiencia")
    texto_perezoso = 0
    cargas_unicas = 0
    for p in py:
        contenido = leer(p)
        for m in re.finditer(r"^\s+import |^\s+from ", contenido, re.M):
            inicio = contenido[:m.start()].count("\n")
            cabecera = "\n".join(contenido.splitlines()[:inicio])
            if any(pesada in m.group() for pesada in PESADAS) and "def " in cabecera:
                texto_perezoso += 1
        cargas_unicas += len(re.findall(r"(create_model|cargar_modelo|_load_model)",
                                        contenido))

    if pesadas_declaradas:
        dim.criterios["e1_import_perezoso_de_pesadas"] = texto_perezoso > 0
        dim.notas.append(f"imports perezosos detectados: {texto_perezoso}")
    else:
        # Sin dependencias pesadas declaradas el criterio no aplica: no se
        # castiga al proyecto por algo que no necesita (honestidad del informe).
        dim.criterios["e1_import_perezoso_de_pesadas"] = True
        dim.notas.append("sin dependencias pesadas declaradas: e1 no aplica")
    dim.criterios["e2_carga_unica_de_modelos"] = cargas_unicas > 0
    dim.notas.append(f"llamadas de carga de modelo: {cargas_unicas}")

    docs = list((ruta / "docs").glob("*.md")) if (ruta / "docs").is_dir() else []
    mediciones = any(re.search(r"\b\d+(\.\d+)?\s*(s|seg|MB|GB|min)\b", leer(d))
                     for d in docs)
    dim.criterios["e3_mediciones_documentadas"] = mediciones
    if not mediciones:
        dim.hallazgos.append(Hallazgo(
            "baja", "Sin mediciones reales (tiempo/RAM) en docs/", "docs/*.md"))

    dim.notas.append("sin medición en vivo: no se ejecuta código del proyecto "
                     "evaluado (P0.8)")
    return dim


# --- Mejoras propuestas: cada una nace de una métrica y trae su verificación --

MEJORAS: Dict[str, Dict[str, str]] = {
    "f1_puntos_de_entrada": {
        "prioridad": "baja",
        "propuesta": "Exponer un punto de entrada ejecutable (CLI)",
        "metrica": "hay módulos con `main()` y `if __name__ == \"__main__\"`"},
    "f2_readme_vs_realidad": {
        "prioridad": "alta",
        "propuesta": "Alinear README y código: implementar o retirar lo prometido",
        "metrica": "cada `archivo.py` citado en el README existe"},
    "f3_sin_deuda_declarada": {
        "prioridad": "baja",
        "propuesta": "Cerrar o priorizar las marcas TODO/FIXME/XXX de producción",
        "metrica": "0 marcas TODO/FIXME/XXX en el código de producción"},
    "f4_tests_de_varios_modulos": {
        "prioridad": "media",
        "propuesta": "Cubrir con tests los módulos que hoy no tienen ninguno",
        "metrica": "nº de archivos test_*.py > 1"},
    "c1_suite_de_tests": {
        "prioridad": "alta",
        "propuesta": "Crear una suite de tests ejecutable",
        "metrica": "`python3 -m unittest discover` devuelve OK"},
    "c2_linter_configurado": {
        "prioridad": "media",
        "propuesta": "Configurar un linter (p. ej. ruff) y dejarlo en 0 avisos",
        "metrica": "`ruff check .` sale con código 0"},
    "c3_sin_silencios": {
        "prioridad": "alta",
        "propuesta": "Sustituir los `except` con `pass`/`continue` por error "
                     "reportado o re-elevado (P1.26)",
        "metrica": "0 coincidencias del patrón except+pass/continue"},
    "c4_tests_sobre_codigo_30pct": {
        "prioridad": "media",
        "propuesta": "Acercar la proporción test/código al 30% o justificar la "
                     "excepción por escrito",
        "metrica": "líneas de test / líneas de código >= 0,30"},
    "v1_dependencias_fijadas": {
        "prioridad": "media",
        "propuesta": "Fijar las versiones de las dependencias (==) o generar lock",
        "metrica": "0 dependencias declaradas con operador distinto de =="},
    "v2_lockfile": {
        "prioridad": "media",
        "propuesta": "Generar un lockfile con hashes e instalar desde él",
        "metrica": "existe requirements.lock / uv.lock / poetry.lock"},
    "v3_actividad_reciente": {
        "prioridad": "baja",
        "propuesta": "Mantener actividad o declarar el proyecto como inactivo",
        "metrica": ">= 1 commit en los últimos 180 días"},
    "v4_dependencias_al_dia": {
        "prioridad": "media",
        "propuesta": "Actualizar las dependencias que van por detrás de PyPI",
        "metrica": "ninguna dependencia fijada por detrás de la última publicada"},
    "h1_manifiesto": {
        "prioridad": "alta",
        "propuesta": "Declarar las dependencias en un manifiesto",
        "metrica": "existe requirements.txt o pyproject.toml"},
    "h2_licencia": {
        "prioridad": "alta",
        "propuesta": "Añadir un archivo de licencia: sin él no hay términos de uso",
        "metrica": "existe LICENSE/COPYING"},
    "h3_verificacion_automatizada": {
        "prioridad": "media",
        "propuesta": "Añadir CI local (script de verificación) o remota",
        "metrica": "existe scripts/*verif*, Makefile o .github/workflows"},
    "h4_runner_de_tests_declarado": {
        "prioridad": "baja",
        "propuesta": "Documentar el comando de tests en README/Makefile",
        "metrica": "el comando de la suite aparece en README o Makefile"},
    "i1_cachea_trabajo_repetido": {
        "prioridad": "media",
        "propuesta": "Cachear trabajo repetido (respuestas o cómputo idéntico)",
        "metrica": "existe caché y se puede medir su tasa de aciertos"},
    "i2_timeouts_explicitos": {
        "prioridad": "alta",
        "propuesta": "Poner timeout explícito en toda llamada de red (P1.34)",
        "metrica": "cada cliente de red declara timeout y es configurable"},
    "i3_reintentos_con_limite": {
        "prioridad": "media",
        "propuesta": "Reintentar solo errores transitorios, con límite y backoff",
        "metrica": "existe max_retries/backoff y un test que agote los intentos"},
    "i4_valida_respuestas": {
        "prioridad": "alta",
        "propuesta": "Validar las respuestas externas antes de usarlas",
        "metrica": "el parseo falla de forma ruidosa (excepción) y hay test de ello"},
    "i5_declara_lo_simulado": {
        "prioridad": "media",
        "propuesta": "Declarar explícitamente lo simulado/mock (regla propia 4)",
        "metrica": "lo simulado aparece marcado como simulado en código y docs"},
    "i6_metricas_propias": {
        "prioridad": "media",
        "propuesta": "Medir lo que produce el sistema (benchmark o rúbrica propia)",
        "metrica": "existe un benchmark/rúbrica ejecutable y su salida se conserva"},
    "e1_import_perezoso_de_pesadas": {
        "prioridad": "media",
        "propuesta": "Importar perezosamente las dependencias pesadas (dentro de "
                     "la función que las usa)",
        "metrica": "el import pesado no ocurre al importar el módulo"},
    "e2_carga_unica_de_modelos": {
        "prioridad": "media",
        "propuesta": "Cargar cada modelo una sola vez (daemon o caché de proceso)",
        "metrica": "una sola carga por proceso, verificada en ejecución"},
    "e3_mediciones_documentadas": {
        "prioridad": "baja",
        "propuesta": "Documentar mediciones reales (tiempo/RAM/coste) por ruta",
        "metrica": "docs/ contiene cifras medidas con su fecha"},
    "c1b_suite_pasa": {
        "prioridad": "alta",
        "propuesta": "Dejar la suite en verde: ningún test puede fallar",
        "metrica": "el comando de tests declarado devuelve código 0"},
    "h5_licencias_libres": {
        "prioridad": "media",
        "propuesta": "Declarar o sustituir las dependencias cuya licencia libre "
                     "no se puede verificar en PyPI",
        "metrica": "todas las dependencias declaran licencia OSI en PyPI"},
}


# Criterios que dependen de otro (se proponen en secuencia, no sueltos).
SECUENCIA = {
    "v2_lockfile": 2,          # después de fijar versiones (v1)
    "h4_runner_de_tests_declarado": 2,
    "e2_carga_unica_de_modelos": 2,
}


def _esfuerzo(n_sitios: int) -> str:
    """Esfuerzo estimado por número de sitios afectados (declarado, no oculto)."""
    if n_sitios <= 1:
        return "bajo"
    if n_sitios <= 10:
        return "medio"
    return "alto"


def _cifras_de_notas(notas: List[str]) -> Dict[str, str]:
    """Cifras citadas por las notas de una dimensión (para cuantificar el plan)."""
    cifras = {}
    for nota in notas:
        m = re.search(r"([a-záéíóúñ ]+):\s*(\d+)", nota)
        if m:
            cifras[m.group(1).strip()] = m.group(2)
    return cifras


def proponer_mejoras(informe: Dict[str, Any]) -> List[Dict[str, str]]:
    """Plan de mejora DERIVADO de las métricas del informe.

    Cada propuesta nace de un criterio incumplido y añade lo que la tabla fija
    no puede dar: cuántos sitios afecta, qué evidencia la respalda, el esfuerzo
    estimado, la secuencia respecto a otras propuestas y la verificación exacta
    (la métrica es el criterio de aceptación). Se ordena por prioridad y, a
    igualdad, por menor esfuerzo (más valor por unidad de trabajo).
    """
    propuestas = []
    for nombre, datos in informe["dimensiones"].items():
        cifras = _cifras_de_notas(datos["notas"])
        evidencias = [h["evidencia"] for h in datos["hallazgos"] if h["evidencia"]]
        for criterio, ok in datos["criterios"].items():
            if ok:
                continue
            plan = MEJORAS.get(criterio)
            if plan is None:
                continue
            propuestas.append({
                "dimension": nombre,
                "criterio": criterio,
                "prioridad": plan["prioridad"],
                "propuesta": plan["propuesta"],
                "metrica": plan["metrica"],
                "sitios": len(evidencias),
                "esfuerzo": _esfuerzo(len(evidencias)),
                "secuencia": SECUENCIA.get(criterio, 1),
                "datos_medidos": cifras,
                "evidencia": evidencias[:5],
            })
    orden = {"alta": 0, "media": 1, "baja": 2}
    propuestas.sort(key=lambda p: (orden.get(p["prioridad"], 3), p["secuencia"],
                                   {"bajo": 0, "medio": 1, "alto": 2}[p["esfuerzo"]],
                                   p["criterio"]))
    return propuestas


def plan_texto(informe: Dict[str, Any]) -> List[str]:
    """Resumen del plan: cuántas propuestas por prioridad y el orden de trabajo."""
    propuestas = informe.get("mejoras", [])
    if not propuestas:
        return ["Plan de mejora: nada que proponer (todos los criterios cumplen)."]
    conteo: Dict[str, int] = {}
    for p in propuestas:
        conteo[p["prioridad"]] = conteo.get(p["prioridad"], 0) + 1
    resumen = ", ".join(f"{n} {prioridad}" for prioridad, n in
                        sorted(conteo.items(),
                               key=lambda x: {"alta": 0, "media": 1, "baja": 2}[x[0]]))
    return [f"Plan de mejora: {len(propuestas)} propuestas ({resumen}); "
            f"ordenadas por prioridad, secuencia y esfuerzo."]


# --- Síntesis con LLM (opt-in): lo que el plan mecánico no ve ----------------

PROMPT_SINTESIS = """Eres un ingeniero de software senior. Con SOLO la evidencia
medida que se te da (no inventes archivos, métricas, APIs ni líneas), propón
mejoras de FONDO que un plan mecánico por criterios no vería: diseño, estructura,
algoritmos, eficiencia o riesgos del proyecto.

Si algo no se puede decidir con la evidencia medida, NO lo inventes: formúlalo
como pregunta abierta (se investigará después).

Responde SOLO un objeto JSON con estas dos claves:
{"propuestas": [{"dimension": "funcionalidades|calidad|vigencia|herramientas|inteligencia|eficiencia",
                 "propuesta": "acción concreta",
                 "por_que": "razón breve",
                 "evidencia": "archivo:línea o medición tomada del informe",
                 "como_verificar": "métrica que la cerraría"}],
 "preguntas_abiertas": ["qué no puedes decidir sin más información"]}

Máximo 5 propuestas, ordenadas por impacto.

INFORME MEDIDO:"""


def investigar_preguntas(preguntas: List[str], search_api,
                         max_por_pregunta: int = 2) -> List[Dict[str, Any]]:
    """Resuelve las dudas declaradas por el modelo con búsqueda real y citada.

    Reutiliza `web_search` (Wikipedia/DuckDuckGo, sin API key). Cada hallazgo
    lleva su URL para poder verificarlo; si la búsqueda falla o no devuelve nada,
    se declara (nunca se rellena con texto inventado).
    """
    from web_search import formulate_query

    hallazgos = []
    for pregunta in preguntas:
        try:
            resultados = search_api.search(formulate_query(pregunta, 5))
        except Exception as exc:  # noqa: BLE001 - se declara el fallo
            hallazgos.append({"pregunta": pregunta,
                              "error": f"{type(exc).__name__}: {exc}"})
            continue
        fuentes = [{"titulo": r.get("title", ""), "url": r.get("url", "")}
                   for r in resultados[:max_por_pregunta]]
        hallazgos.append({"pregunta": pregunta, "fuentes": fuentes,
                          "sin_resultados": not fuentes})
    return hallazgos


def _digesto(informe: Dict[str, Any], max_hallazgos: int = 20) -> str:
    """Resumen del informe medido para el prompt (solo datos del propio informe)."""
    lineas = [f"ruta: {informe['ruta']}",
              f"python: {informe['archivos_python']} archivos / "
              f"{informe['lineas_python']} líneas"]
    for nombre, datos in informe["dimensiones"].items():
        fallos = [c for c, ok in datos["criterios"].items() if not ok]
        lineas.append(f"- {nombre}: {datos['puntuacion']:.2f} | "
                      f"fallos: {fallos or '—'}")
        for h in datos["hallazgos"][:max_hallazgos]:
            marca = EvidenceKind(h["tipo_evidencia"]).marcador
            lineas.append(f"    {marca} ({h['severidad']}) "
                          f"{h['descripcion'][:110]} — {h['evidencia']}")
        for nota in datos["notas"]:
            lineas.append(f"    · {nota}")
    return "\n".join(lineas)


def sintetizar_con_llm(informe: Dict[str, Any], llm) -> Dict[str, Any]:
    """Genera propuestas con un LLM a partir del informe medido (opt-in).

    Control anti-invención (mecánico): cada propuesta se marca `con_respaldo`
    solo si su campo `evidencia` aparece en la evidencia medida del informe. Las
    que no lo tengan se conservan pero quedan marcadas: son juicio, no medición.
    """
    evidencia_medida = " ".join(
        [h["evidencia"] for d in informe["dimensiones"].values()
         for h in d["hallazgos"]]
        + [n for d in informe["dimensiones"].values() for n in d["notas"]]
        + [informe["ruta"]])

    respuesta = llm.generate(PROMPT_SINTESIS + "\n" + _digesto(informe))
    datos = _parse_json_response(respuesta)
    if isinstance(datos, dict):
        crudas = datos.get("propuestas", [])
        preguntas = [str(p) for p in datos.get("preguntas_abiertas", [])]
    elif isinstance(datos, list):          # contrato antiguo: solo propuestas
        crudas, preguntas = datos, []
    else:
        raise ValueError("La síntesis debe ser un objeto o array JSON")
    if not isinstance(crudas, list):
        raise ValueError("`propuestas` debe ser una lista")

    propuestas = []
    for item in crudas:
        if not isinstance(item, dict):
            continue
        propuesta = {
            "dimension": str(item.get("dimension", "")),
            "propuesta": str(item.get("propuesta", "")),
            "por_que": str(item.get("por_que", "")),
            "evidencia": str(item.get("evidencia", "")),
            "como_verificar": str(item.get("como_verificar", "")),
        }
        clave = propuesta["evidencia"].split()[0] if propuesta["evidencia"] else ""
        propuesta["con_respaldo"] = bool(clave) and clave in evidencia_medida
        propuestas.append(propuesta)

    return {"modelo": getattr(llm, "model", "?"),
            "propuestas": propuestas,
            "preguntas_abiertas": preguntas,
            "sin_respaldo": sum(1 for p in propuestas if not p["con_respaldo"])}


def evaluar(ruta: Path, con_red: bool = True,
            ejecutar_tests_flag: bool = False, llm=None,
            investigar: bool = False, search_api=None) -> Dict[str, Any]:
    """Evalúa un proyecto y devuelve el informe completo (sin escribir nada).

    `ejecutar_tests_flag` es un opt-in EXPLÍCITO: es lo único que ejecuta código
    del proyecto evaluado (P0.8), siempre con el comando que el propio proyecto
    declara.
    """
    if not ruta.is_dir():
        raise ValueError(f"No es un directorio: {ruta}")
    py = archivos_python(ruta)
    deps = _dependencias(ruta)
    pesadas = [d["nombre"] for d in deps
               if any(pesada in d["nombre"] for pesada in PESADAS)]
    dimensiones = [
        evaluar_funcionalidades(ruta, py),
        evaluar_calidad(ruta, py, ejecutar_tests_flag),
        evaluar_vigencia(ruta, deps, con_red),
        evaluar_herramientas(ruta, deps, con_red),
        evaluar_inteligencia(ruta, py),
        evaluar_eficiencia(ruta, py, pesadas),
    ]
    global_ = round(sum(d.puntuacion for d in dimensiones) / len(dimensiones), 3)
    no_verificado = []
    if not ejecutar_tests_flag:
        no_verificado.append(
            "la suite de tests NO se ejecuta (usa --ejecutar-tests para "
            "verificarla; P0.8: ejecutar código ajeno es opt-in)")
    if not con_red:
        no_verificado.append("versiones y licencias de dependencias no "
                             "consultadas (--sin-red)")
    tipos_evidencia = [h.tipo_evidencia for d in dimensiones
                       for h in d.hallazgos]
    tipos_evidencia.extend([EvidenceKind.UNVERIFIED] * len(no_verificado))
    informe = {
        "ruta": str(ruta),
        "archivos_python": len(py),
        "lineas_python": sum(len(leer(p).splitlines()) for p in py),
        "dependencias": deps,
        "dimensiones": {d.nombre: d.a_dict() for d in dimensiones},
        "global": global_,
        "no_verificado": no_verificado,
        "evidencia": resumen_evidencias(tipos_evidencia),
    }
    informe["mejoras"] = proponer_mejoras(informe)
    if llm is not None:
        informe["sintesis_llm"] = sintetizar_con_llm(informe, llm)
        preguntas = informe["sintesis_llm"]["preguntas_abiertas"]
        if investigar and preguntas:
            if search_api is None:
                from web_search import WikipediaSearchAPI
                search_api = WikipediaSearchAPI()
            informe["investigacion"] = investigar_preguntas(preguntas, search_api)
    return informe


def informe_texto(informe: Dict[str, Any]) -> List[str]:
    lineas = [f"EVALUACIÓN DE PROYECTO (read-only): {informe['ruta']}",
              f"Python: {informe['archivos_python']} archivos / "
              f"{informe['lineas_python']} líneas", ""]
    for nombre, datos in informe["dimensiones"].items():
        lineas.append(f"== {nombre.upper()} — {datos['puntuacion']:.2f} ==")
        for criterio, ok in datos["criterios"].items():
            lineas.append(f"  [{'OK ' if ok else 'NO '}] {criterio}")
        for h in datos["hallazgos"]:
            marca = EvidenceKind(h["tipo_evidencia"]).marcador
            lineas.append(f"  {marca} ({h['severidad']}) {h['descripcion']} — {h['evidencia']}")
        for nota in datos["notas"]:
            lineas.append(f"  · {nota}")
        lineas.append("")
    lineas.append(f"GLOBAL: {informe['global']:.3f}")
    lineas.append(f"Evidencia: {formato_resumen(informe['evidencia'])}")
    lineas.append("")
    lineas.extend(plan_texto(informe))
    lineas.append("== MEJORAS PROPUESTAS (por prioridad, con su verificación) ==")
    for m in informe["mejoras"]:
        lineas.append(f"  [{m['prioridad']:>5}] {m['dimension']}: {m['propuesta']}")
        lineas.append(f"          sitios: {m['sitios']} | esfuerzo: {m['esfuerzo']}")
        lineas.append(f"          verificación: {m['metrica']}")
    if "sintesis_llm" in informe:
        sintesis = informe["sintesis_llm"]
        lineas.append("")
        lineas.append(f"== PROPUESTAS DEL MODELO ({sintesis['modelo']}) — juicio, no "
                      f"medición; sin respaldo medido: {sintesis['sin_respaldo']} ==")
        for propuesta in sintesis["propuestas"]:
            marca = "con respaldo medido" if propuesta["con_respaldo"] else "SIN RESPALDO"
            lineas.append(f"  [{propuesta['dimension']}] {propuesta['propuesta']} "
                          f"({marca})")
            lineas.append(f"          por qué: {propuesta['por_que']}")
            lineas.append(f"          evidencia citada: {propuesta['evidencia']}")
            lineas.append(f"          verificación: {propuesta['como_verificar']}")
        if sintesis["preguntas_abiertas"]:
            lineas.append(f"  Preguntas abiertas (lo que el modelo declara NO saber): "
                          f"{len(sintesis['preguntas_abiertas'])}")
            for pregunta in sintesis["preguntas_abiertas"]:
                lineas.append(f"    · {pregunta}")
    if "investigacion" in informe:
        lineas.append("")
        lineas.append("== INVESTIGACIÓN DE LAS DUDAS (fuentes citadas, verificables) ==")
        for hallazgo in informe["investigacion"]:
            lineas.append(f"  ? {hallazgo['pregunta']}")
            if hallazgo.get("error"):
                lineas.append(f"    ERROR: {hallazgo['error']}")
            elif hallazgo.get("sin_resultados"):
                lineas.append("    sin resultados (se declara, no se inventa)")
            for fuente in hallazgo.get("fuentes", []):
                lineas.append(f"    - {fuente['titulo']}: {fuente['url']}")
    lineas.append("")
    lineas.append("No verificado: " + "; ".join(informe["no_verificado"]))
    return lineas


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evalúa un proyecto externo en 6 dimensiones (read-only).")
    parser.add_argument("ruta", help="ruta del proyecto a evaluar")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--sin-red", action="store_true",
                        help="omite la comprobación de versiones y licencias en PyPI")
    parser.add_argument("--ejecutar-tests", action="store_true",
                        help="EJECUTA el comando de tests declarado por el proyecto "
                             "(opt-in explícito: es lo único que corre código "
                             "ajeno, P0.8)")
    parser.add_argument("--sintesis-llm", action="store_true",
                        help="pide a un LLM propuestas de FONDO a partir del informe "
                             "medido (opt-in; requiere key y red; coste 0 con :free)")
    parser.add_argument("--modelo", default=None,
                        help="modelo para la síntesis (defecto: el gratuito del proyecto)")
    parser.add_argument("--investigar", action="store_true",
                        help="resuelve las dudas del modelo con búsqueda real y cita "
                             "las fuentes (implica --sintesis-llm; requiere red)")
    args = parser.parse_args()

    llm = None
    if args.sintesis_llm or args.investigar:
        from llm_providers import OpenRouterLLM
        llm = OpenRouterLLM(model=args.modelo) if args.modelo else OpenRouterLLM()

    try:
        informe = evaluar(Path(args.ruta).resolve(), con_red=not args.sin_red,
                          ejecutar_tests_flag=args.ejecutar_tests, llm=llm,
                          investigar=args.investigar)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        print("\n".join(informe_texto(informe)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
