"""Presupuesto LLM seguro entre hilos."""

import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from llm_providers import BudgetLLM


class _Provider:
    def __init__(self):
        self.calls = 0

    def generate(self, prompt, model=None, **kwargs):
        self.calls += 1
        time.sleep(0.005)
        return prompt


class TestBudgetLLM(unittest.TestCase):
    def test_error_e_invalidacion(self):
        with self.assertRaises(ValueError):
            BudgetLLM(_Provider(), 0)
        provider = BudgetLLM(_Provider(), 1)
        self.assertEqual(provider.generate("una"), "una")
        with self.assertRaisesRegex(RuntimeError, "agotado"):
            provider.generate("dos")

    def test_hilos_no_superan_el_presupuesto(self):
        budget = BudgetLLM(_Provider(), 3)
        errores = []

        def llamar(indice):
            try:
                return budget.generate(str(indice))
            except RuntimeError as exc:
                errores.append(str(exc))
                return None

        with ThreadPoolExecutor(max_workers=8) as executor:
            resultados = list(executor.map(llamar, range(10)))

        self.assertEqual(sum(r is not None for r in resultados), 3)
        self.assertEqual(budget.calls, 3)
        self.assertEqual(len(errores), 7)
        self.assertTrue(all("3/3" in error for error in errores))

    def test_lock_especifico_por_instancia(self):
        budget = BudgetLLM(_Provider(), 1)
        self.assertTrue(isinstance(budget._lock, type(threading.Lock())))


if __name__ == "__main__":
    unittest.main()
