"""Tests del benchmark de precisión/recall del evaluador (R4)."""

import unittest

from tests.benchmarks.evaluador_precision import (CASOS, calcular_metricas,
                                                  evaluar_corpus)


class TestEvaluadorPrecision(unittest.TestCase):
    def test_calcular_metricas_tp_fp_fn(self):
        metrica = calcular_metricas(
            [True, True, False, False],
            [True, False, True, False])

        self.assertEqual(metrica["tp"], 1)
        self.assertEqual(metrica["fp"], 1)
        self.assertEqual(metrica["fn"], 1)
        self.assertEqual(metrica["precision"], 0.5)
        self.assertEqual(metrica["recall"], 0.5)

    def test_corpus_balanceado_y_sin_falsos(self):
        criterios = {caso["criterio"] for caso in CASOS}
        self.assertEqual(len(criterios), 14)
        self.assertEqual(len(CASOS), 28)
        for criterio in criterios:
            esperados = {caso["esperado"] for caso in CASOS
                         if caso["criterio"] == criterio}
            self.assertEqual(esperados, {True, False}, criterio)

        resultado = evaluar_corpus()

        self.assertEqual(resultado["casos"], 28)
        self.assertEqual(resultado["criterios"], 14)
        self.assertEqual(resultado["global"]["tp"], 14)
        self.assertEqual(resultado["global"]["fp"], 0)
        self.assertEqual(resultado["global"]["fn"], 0)
        self.assertEqual(resultado["global"]["precision"], 1.0)
        self.assertEqual(resultado["global"]["recall"], 1.0)
        for metrica in resultado["por_criterio"].values():
            self.assertEqual(metrica["precision"], 1.0)
            self.assertEqual(metrica["recall"], 1.0)
        self.assertIn("no es una campaña sobre proyectos reales",
                      resultado["cobertura"])


if __name__ == "__main__":
    unittest.main()
