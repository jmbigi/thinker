"""Contrato del inventario único de equivalencias R3."""

import json
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


class TestInventarioEquivalencias(unittest.TestCase):
    def test_conteo_unico_y_duplicados(self):
        evaluador = json.loads((RAIZ / "docs/r3-equivalencias-inventario.json").read_text(
            encoding="utf-8"))
        preflight = json.loads(
            (RAIZ / "docs/r3-preflight-equivalencias-inventario.json").read_text(
                encoding="utf-8"))

        self.assertEqual(evaluador["total_registros"], 90)
        self.assertEqual(evaluador["total_unicos"], 78)
        self.assertEqual(evaluador["total_duplicados"], 12)
        self.assertEqual(preflight["total_registros"], 49)
        self.assertEqual(preflight["total_unicos"], 49)
        self.assertEqual(preflight["total_duplicados"], 0)
        self.assertEqual(49 + evaluador["total_unicos"], 127)
        self.assertEqual(evaluador["total_validados"], 76)
        self.assertEqual(preflight["total_validados"], 49)
        self.assertEqual(evaluador["total_validados"] + preflight["total_validados"], 125)
        validados = {(r["funcion"], r["mutante"])
                     for r in evaluador["registros"]
                     if r["verificacion"]["estado"] == "validado"}
        self.assertEqual(len(validados), 76)
        self.assertEqual(sum(r["verificacion"]["estado"] == "validado"
                             for r in evaluador["registros"]), 88)
        self.assertEqual(sum(r["verificacion"]["estado"] == "validado"
                             for r in preflight["registros"]), 49)

        claves = set()
        duplicados = []
        for registro in evaluador["registros"]:
            clave = (registro["funcion"], registro["mutante"])
            if clave in claves:
                duplicados.append(registro)
            else:
                claves.add(clave)
            if registro["duplicado_de"] == "E32":
                self.fail("E32 debe enlazar al grupo anterior, no a sí mismo")
        self.assertEqual(len(duplicados), 12)
        self.assertTrue(all(r["duplicado_de"] for r in duplicados))
        nuevos_e32 = [r for r in evaluador["registros"]
                      if r["grupo"] == "E32" and not r["duplicado_de"]]
        self.assertEqual(
            [(r["grupo"], r["funcion"], r["mutante"], r["duplicado_de"])
             for r in nuevos_e32],
            [("E32", "_leer_requirements", 25, None)])

        e1 = [r for r in evaluador["registros"] if r["grupo"] == "E1"]
        self.assertEqual([r["verificacion"]["ids_actuales"] for r in e1],
                         [[234, 236], [234, 236]])
        e23 = [r for r in evaluador["registros"]
               if r["grupo"] == "E23" and r["mutante"] in (124, 126)]
        self.assertEqual([r["verificacion"]["estado"] for r in e23],
                         ["no_equivalente_actual_cubierto_por_tests"] * 2)
        pre_map = {(r["funcion"], r["mutante"]): r["verificacion"]["id_actual"]
                   for r in preflight["registros"]}
        self.assertEqual(pre_map[("revisar_imports", 28)], 29)
        self.assertEqual(pre_map[("revisar_imports", 29)], 30)
        self.assertEqual(pre_map[("revisar_imports", 56)], 62)


if __name__ == "__main__":
    unittest.main()
