"""Canario de compatibilidad del SDK openai (verificado en 1.x, 2.x y 3.x).

Comprueba la superficie que thinker usa de verdad: construir el cliente y el
endpoint `chat.completions.create` con `model`, `messages` y `timeout`. Si una
versión futura cambia esa superficie, este test falla de forma ruidosa (P1.19)
en vez de romper en producción.

Verificado el 2026-10-16 con openai 1.109.1, 2.54.0 y 3.33.0 (suite completa
403/403 en las tres).
"""

import inspect
import unittest

import openai


class TestSuperficieDelSdk(unittest.TestCase):
    def test_version_mayor_verificada(self):
        mayor = int(openai.__version__.split(".")[0])

        self.assertIn(mayor, (1, 2, 3),
                      f"SDK no verificado: openai {openai.__version__} "
                      f"(actualizar requirements y la verificación multi-versión)")

    def test_cliente_y_endpoint_existen_con_lo_que_usamos(self):
        cliente = openai.OpenAI(api_key="clave-ficticia-de-test")

        parametros = set(inspect.signature(
            cliente.chat.completions.create).parameters)
        for usado in ("model", "messages", "timeout"):
            self.assertIn(usado, parametros,
                          f"openai {openai.__version__} sin el parámetro `{usado}`")


if __name__ == "__main__":
    unittest.main()
