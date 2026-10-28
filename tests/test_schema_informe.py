"""Contrato público del informe JSON (docs/schema-v2.json).

Validador mínimo del subconjunto de JSON Schema que usa el esquema
($ref, type, const, enum, required, properties, additionalProperties,
items, minimum/maximum, minLength). Sin dependencias nuevas.
"""

import copy
import json
import unittest
from pathlib import Path

from evaluar_proyecto import evaluar
from tests.helpers import crear_proyecto

RAIZ = Path(__file__).resolve().parent.parent
ESQUEMA = json.loads((RAIZ / "docs" / "schema-v2.json").read_text(
    encoding="utf-8"))


def _resolver(ref, esquema):
    assert ref.startswith("#/")
    nodo = esquema
    for parte in ref[2:].split("/"):
        nodo = nodo[parte]
    return nodo


def validar(dato, esquema, ruta="$", raiz=None):
    """Devuelve la lista de errores (vacía si cumple)."""
    raiz = raiz or esquema
    errores = []
    if "$ref" in esquema:
        return validar(dato, _resolver(esquema["$ref"], raiz), ruta, raiz)
    if "const" in esquema and dato != esquema["const"]:
        errores.append(f"{ruta}: se esperaba const {esquema['const']!r}")
    if "enum" in esquema and dato not in esquema["enum"]:
        errores.append(f"{ruta}: {dato!r} no está en {esquema['enum']}")
    tipos = esquema.get("type")
    if tipos:
        tipos = tipos if isinstance(tipos, list) else [tipos]
        mapa = {"object": dict, "array": list, "string": str,
                "number": (int, float), "integer": int, "boolean": bool,
                "null": type(None)}
        if not any(isinstance(dato, mapa[t]) for t in tipos
                   if t != "integer") and "integer" not in tipos:
            errores.append(f"{ruta}: tipo {type(dato).__name__} no está en {tipos}")
        elif "integer" in tipos and not isinstance(dato, int):
            errores.append(f"{ruta}: se esperaba integer")
    if isinstance(dato, (int, float)) and not isinstance(dato, bool):
        if "minimum" in esquema and dato < esquema["minimum"]:
            errores.append(f"{ruta}: {dato} < minimum")
        if "maximum" in esquema and dato > esquema["maximum"]:
            errores.append(f"{ruta}: {dato} > maximum")
    if isinstance(dato, str) and "minLength" in esquema \
            and len(dato) < esquema["minLength"]:
        errores.append(f"{ruta}: cadena más corta que minLength")
    if isinstance(dato, dict):
        for clave in esquema.get("required", []):
            if clave not in dato:
                errores.append(f"{ruta}: falta la clave obligatoria {clave!r}")
        props = esquema.get("properties", {})
        extra = esquema.get("additionalProperties", True)
        for clave, valor in dato.items():
            if clave in props:
                errores.extend(validar(valor, props[clave],
                                       f"{ruta}.{clave}", raiz))
            elif extra is False:
                errores.append(f"{ruta}: clave no permitida {clave!r}")
            elif isinstance(extra, dict):
                errores.extend(validar(valor, extra, f"{ruta}.{clave}", raiz))
    if isinstance(dato, list) and "items" in esquema:
        for i, item in enumerate(dato):
            errores.extend(validar(item, esquema["items"], f"{ruta}[{i}]", raiz))
    return errores


class TestEsquemaDelInforme(unittest.TestCase):
    def _informe(self):
        raiz = crear_proyecto(self, {"app.py": "x = 1\n"})
        return evaluar(raiz, con_red=False)

    def test_el_informe_real_cumple_el_esquema(self):
        errores = validar(self._informe(), ESQUEMA)
        self.assertEqual(errores, [])

    def test_una_clave_obligatoria_ausente_falla(self):
        informe = self._informe()
        del informe["mejoras"]
        self.assertTrue(validar(informe, ESQUEMA))

    def test_schema_version_distinta_falla(self):
        informe = self._informe()
        informe["schema_version"] = 3
        error = "\n".join(validar(informe, ESQUEMA))
        self.assertIn("schema_version", error)

    def test_nivel_invalido_y_clave_extra_fallan(self):
        informe = self._informe()
        informe["cobertura"]["nivel"] = "altísima"
        informe["cobertura"]["inventada"] = 1
        error = "\n".join(validar(informe, ESQUEMA))
        self.assertIn("nivel", error)
        self.assertIn("inventada", error)

    def test_hallazgo_con_severidad_invalida_falla(self):
        informe = self._informe()
        informe["dimensiones"]["calidad"]["hallazgos"].append({
            "severidad": "crítica", "descripcion": "x", "evidencia": "x",
            "tipo_evidencia": "unverified", "criterio": "c3_sin_silencios"})
        error = "\n".join(validar(informe, ESQUEMA))
        self.assertIn("severidad", error)

    def test_el_esquema_declara_los_campos_opt_in(self):
        informe = self._informe()
        self.assertNotIn("requisitos", informe)
        self.assertIn("requisitos", ESQUEMA["properties"])
        self.assertIn("sintesis_llm", ESQUEMA["properties"])
        self.assertIn("investigacion", ESQUEMA["properties"])

    def test_copia_valida_sigue_cumpliendo(self):
        informe = copy.deepcopy(self._informe())
        self.assertEqual(validar(informe, ESQUEMA), [])


if __name__ == "__main__":
    unittest.main()
