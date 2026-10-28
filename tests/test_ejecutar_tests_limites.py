"""Límites de recursos del subproceso de `--ejecutar-tests` (opt-in, P0.8).

El timeout acota el tiempo de pared; el límite de CPU (POSIX) protege además
ante un proceso que ignore la señal de terminación. En Windows no hay
`resource`: el test se omite y el timeout sigue siendo la protección.
"""

import os
import unittest

from evaluar_proyecto import ejecutar_tests
from tests.helpers import crear_proyecto


@unittest.skipUnless(os.name == "posix", "resource.setrlimit es POSIX")
class TestLimiteDeCpu(unittest.TestCase):
    def test_el_limite_de_cpu_llega_al_subproceso(self):
        raiz = crear_proyecto(self, {
            "Makefile": (
                "test:\n"
                "\tpython3 -c \"import resource; "
                "open('limite.txt', 'w').write(str("
                "resource.getrlimit(resource.RLIMIT_CPU)[0]))\"\n"),
        })

        resultado = ejecutar_tests(raiz, timeout=30, limite_cpu_s=42)

        self.assertTrue(resultado["ejecutado"])
        self.assertTrue(resultado["ok"])
        self.assertEqual((raiz / "limite.txt").read_text(), "42")

    def test_sin_limite_explicito_se_usa_timeout_mas_margen(self):
        raiz = crear_proyecto(self, {
            "Makefile": (
                "test:\n"
                "\tpython3 -c \"import resource; "
                "open('limite.txt', 'w').write(str("
                "resource.getrlimit(resource.RLIMIT_CPU)[0]))\"\n"),
        })

        resultado = ejecutar_tests(raiz, timeout=30)

        self.assertTrue(resultado["ok"])
        self.assertEqual((raiz / "limite.txt").read_text(), "90")


if __name__ == "__main__":
    unittest.main()
