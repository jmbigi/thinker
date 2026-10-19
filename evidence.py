#!/usr/bin/env python3
"""Marcadores de evidencia para hallazgos y promociones.

Una afirmación solo puede promocionarse si su evidencia es **real** (observada
en el entorno actual) o, de forma explícita y justificada, si es **sintética**
(observada en una simulación declarada). Lo **no verificado** nunca promociona.

Los tres tipos son deliberadamente excluyentes:

- ``VERIFIED_REAL``: lectura o ejecución real y reproducible.
- ``VERIFIED_SYNTHETIC``: observado en un mock/simulación declarada.
- ``UNVERIFIED``: no se pudo comprobar (red, permiso, herramienta ausente).

Este módulo no ejecuta nada ni accede a la red: solo modela la evidencia.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Union


class EvidenceKind(str, Enum):
    """Procedencia de una evidencia, con marcador textual estable."""

    VERIFIED_REAL = "verified-real"
    VERIFIED_SYNTHETIC = "verified-synthetic"
    UNVERIFIED = "unverified"

    @property
    def marcador(self) -> str:
        """Marcador legible para informes y logs."""
        return f"[{self.value.upper()}]"


@dataclass(frozen=True)
class Evidence:
    """Evidencia atribuible a una fuente concreta.

    Las evidencias reales y sintéticas exigen una fuente no vacía; una
    evidencia no verificada puede no tenerla porque precisamente declara una
    ausencia de observación.
    """

    kind: EvidenceKind
    source: str
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EvidenceKind):
            raise TypeError("kind debe ser un EvidenceKind")
        if not isinstance(self.source, str):
            raise TypeError("source debe ser texto")
        if self.kind is not EvidenceKind.UNVERIFIED and not self.source.strip():
            raise ValueError("La evidencia verificada exige una fuente no vacía")

    @property
    def marcador(self) -> str:
        return self.kind.marcador


def puede_promocionar(evidence: Evidence, *, permitir_sintetica: bool = False,
                      justificacion: str = "") -> bool:
    """Decide si una evidencia permite promocionar una afirmación.

    La evidencia sintética solo se acepta con una autorización explícita y una
    justificación no vacía: así lo simulado queda declarado y auditable. Lo no
    verificado no se promociona nunca, ni siquiera con autorización.
    """
    if not isinstance(evidence, Evidence):
        raise TypeError("evidence debe ser un Evidence")
    if evidence.kind is EvidenceKind.VERIFIED_REAL:
        return True
    if evidence.kind is EvidenceKind.VERIFIED_SYNTHETIC:
        return permitir_sintetica and bool(justificacion.strip())
    return False


def resumen_evidencias(
        evidencias: Iterable[Union[Evidence, EvidenceKind]]) -> Dict[str, int]:
    """Cuenta evidencias por tipo; siempre devuelve las tres claves."""
    conteo = {kind.value: 0 for kind in EvidenceKind}
    for item in evidencias:
        kind = item.kind if isinstance(item, Evidence) else item
        if not isinstance(kind, EvidenceKind):
            raise TypeError(f"Elemento de evidencia no válido: {item!r}")
        conteo[kind.value] += 1
    return conteo


def formato_resumen(conteo: Dict[str, int]) -> str:
    """Formatea un resumen de evidencias para un informe de texto."""
    return " | ".join(
        f"{kind.marcador} {conteo.get(kind.value, 0)}" for kind in EvidenceKind)
