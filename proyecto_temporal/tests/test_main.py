"""Tests temporales para proyecto Forthtrade + Thinker."""

import os
from main import pensar_codigo


class TestProyectoTemporal:
    def test_entorno_validado(self):
        """Verificar que el entorno está configurado."""
        assert os.path.exists("pyproject.toml")

    def test_pensar_codigo(self):
        """Verificar que pensar_codigo retorna resultado."""
        resultado = pensar_codigo("test prompt")
        assert isinstance(resultado, str)

    def test_factorial(self):
        """Verificar función factorial."""
        from calculadora import factorial
        assert factorial(5) == 120
        assert factorial(0) == 1
        
    def test_suma(self):
        """Verificar función suma."""
        from calculadora import suma
        assert suma(2, 3) == 5
