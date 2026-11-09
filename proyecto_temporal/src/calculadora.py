#!/usr/bin/env python3
"""Módulo de cálculo temporal - proyecto Forthtrade + Thinker."""

def factorial(n: int) -> int:
    """Calcular factorial de manera recursiva."""
    if n < 0:
        raise ValueError("No factorial de números negativos")
    if n == 0:
        return 1
    return n * factorial(n - 1)

def suma(a: int, b: int) -> int:
    """Calcular suma de dos números."""
    return a + b
