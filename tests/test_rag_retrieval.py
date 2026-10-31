"""Tests de las métricas de recuperación RAG (offline, deterministas)."""

import math
import unittest

from tests.benchmarks.rag_retrieval import (evaluar, ndcg_at_k, recall_at_k,
                                            reciprocal_rank)


class TestMetricas(unittest.TestCase):
    def test_recall_at_k(self):
        self.assertEqual(recall_at_k(["a", "b", "c"], {"c"}, 1), 0.0)
        self.assertEqual(recall_at_k(["a", "b", "c"], {"c"}, 3), 1.0)
        self.assertEqual(recall_at_k(["a", "b"], {"a", "c"}, 2), 0.5)
        self.assertEqual(recall_at_k([], {"a"}, 5), 0.0)

    def test_reciprocal_rank(self):
        self.assertEqual(reciprocal_rank(["a", "b"], {"a"}), 1.0)
        self.assertEqual(reciprocal_rank(["a", "b"], {"b"}), 0.5)
        self.assertEqual(reciprocal_rank(["a", "b"], {"c"}), 0.0)

    def test_ndcg(self):
        self.assertAlmostEqual(ndcg_at_k(["a", "b"], {"a"}, 10), 1.0)
        self.assertAlmostEqual(ndcg_at_k(["b", "a"], {"a"}, 10),
                               1.0 / math.log2(3))
        self.assertEqual(ndcg_at_k(["a"], set(), 10), 0.0)

    def test_benchmark_determinista_y_en_rango(self):
        primero = evaluar()
        segundo = evaluar()
        self.assertEqual(primero["metricas"], segundo["metricas"])
        self.assertEqual(primero["resultados"][0]["ranked"],
                         segundo["resultados"][0]["ranked"])
        for valor in primero["metricas"].values():
            self.assertGreaterEqual(valor, 0.0)
            self.assertLessEqual(valor, 1.0)
        self.assertEqual(primero["corpus"], 10)
        self.assertEqual(primero["consultas"], 16)


if __name__ == "__main__":
    unittest.main()
