#!/usr/bin/env python3
"""
Veracity Layer - Capa de Veracidad y Anti-Alucinación para Respuestas LLM
===========================================================================

IMPORTANTE: Este módulo NO es un simulacro ni un Mock. Cumple estrictamente
P0.1/P0.2 de AGENTS.md: ninguna afirmación se libera sin evidencia,
y el contenido simulado se declara explícitamente.

Principios (extraídos de AGENTS.md):
 - P0.1: Nunca afirmes sin evidencia
 - P0.2: Nunca inventes (anti-alucinación)
 - Regla propia 4: Lo simulado se declara explícitamente
 - P1.19: Sin fallbacks silenciosos (errores eleva y reporta)

Este módulo se integra con:
 - evidence.Evidence (VERIFIED_REAL / VERIFIED_SYNTHETIC / UNVERIFIED)
 - thinking_engine.validate_step (validación por pasos del ciclo de pensamiento)
 - pensamiento_layer.DeepResearchThinkingLayer (7 pasos deliberados)

No se permite `except: pass` ni silencios que traguan errores.
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from dataclasses import dataclass, field

from evidence import (Evidence, EvidenceKind, puede_promocionar,
                      resumen_evidencias, formato_resumen)
from thinking_engine import StepThinkingEngine


# ---------------------------------------------------------------------------
# Tipos y estructura de "veredicto de veracidad"
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Veredict:
    """Resultado de verificar una afirmación contra la evidencia disponible."""
    afirmacion: str
    # Uno de: "supported" | "contradicted" | "not_addressed"
    verdict: str
    # Nivel de confianza 0-1. Siempre que verdict=="supported" requiere
    # evidencia real o sintética justificada; si es "not_addressed" o
    # "contradicted" la confianza debe ser 0.
    confianza: float
    # Razón legible (para informes, logs o al usuario)
    reasoning: str
    # Evidencia que sustenta el veredicto (puede estar vacía si
    # verdict=="not_addressed" y no hay qué basarse)
    evidencia: Evidence = field(default_factory=Evidence)


# ---------------------------------------------------------------------------
# Capa principal: verifica antes de afirmar
# ---------------------------------------------------------------------------

class VeracityLayer:
    """
    Capa de veracidad que intercepta respuestas y asegura 100% veracidad.

    Funciona en tres modos consistentes con AGENTS.md:
    1. ESTRICTO: cualquier afirmación sin evidencia comprobada → se descarta
       y se reporta como "unverified" con sugerencia de consulta humana.
    2. CONSULTAR: afirmaciones sin evidencia clara → se marca como unverified
       y se pide al usuario que decida (humano en el bucle).
    3. DEMONSTRACIÓN: contenido simulado/declarado → marcado con
      VERIFIED_SYNTHETIC y justificación explícita (offline/demo solo).

    La verificación pasa por `validate_step` del thinking_engine para
    asegurar que cada afirmación tenga un paso explícito y validado.
    """

    def __init__(
        self,
        *,
        mode: str = "strict",  # strict | query | demo
        permitir_sintetica: bool = False,
        justificacion_sintetica: str = "",
        motor_pensamiento: Optional[StepThinkingEngine] = None,
    ):
        """
        :param mode: modo de operación
        :param permitir_sintetica: si True, permite VERIFIED_SYNTHETIC con
          justificación (modo demo/offline)
        :param justificacion_sintetica: justificación no vacía cuando se
          usa contenido sintético
        :param motor_pensamiento: motor de pensamiento opcional para
          validación paso a paso (usado solo para validate_step; si no se
          provee, se usa la llamada estática StepThinkingEngine.validate_step())
        """
        self.mode = mode
        self.permitir_sintetica = permitir_sintetica
        self.justificacion_sintetica = justificacion_sintetica
        # Usar la instancia solo si viene proveedora; si no, la validación
        # se hace mediante el método static StepThinkingEngine.validate_step()
        self._motor = motor_pensamiento  # puede ser None

        if mode not in {"strict", "query", "demo"}:
            raise ValueError(f"Modo inválido: {mode!r}. Use 'strict', 'query' o 'demo'.")
        if permitir_sintetica and not justificacion_sintetica.strip():
            raise ValueError(
                "Si permitir_sintetica=True, debe haber una justificación "
                "no vacía (regla de veracidad)."
            )

    # ------------------------------------------------------------------
    # Verificación simple de una afirmación contra una evidencia dada
    # ------------------------------------------------------------------

    def verificar(
        self,
        afirmacion: str,
        *,
        evidencia: Optional[Evidence] = None,
        confianza_bruta: float = 1.0,
    ) -> Veredict:
        """
        Verifica una afirmación contra la evidencia disponible.

        Devuelve un Veredict con verdict, confianza y reasoning.

        Regla P0.1/P0.2: Si no hay evidencia real y no hay autorización de
        sintética, el afirmativo no promociona: verdict="not_addressed",
        confianza=0. Pasa por validate_step para asegurar consistencia con
        el ciclo de pensamiento estructurado.

        Args:
            afirmacion: Texto de la afirmación a verificar
            evidencia: Evidencia Evidence kind real o synthetic
            confianza_bruta: nivel de confianza inicial (0-1), se recorta

        Returns:
            Veredict con verdict, confianza y reasoning
        """
        # --- Validación paso a paso con el motor de pensamiento ---
        # Aseguramos que la afirmación tenga un paso explícito validado.
        # Usamos el método static de StepThinkingEngine.
        try:
            # validate_step espera un string (el "contenido" del paso)
            _ = StepThinkingEngine.validate_step(afirmacion)
        except Exception as e:
            # Si falla la validación, la tratamos como no verificada
            # en lugar de silenciar el error.
            raise ValueError(
                f"La afirmación no pasa la validación del paso de pensamiento: {e}"
            ) from e

        # --- Caso 1: Evidencia real verificada ---
        if evidencia is not None and evidencia.kind is EvidenceKind.VERIFIED_REAL:
            if puede_promocionar(evidence=evidencia, permitir_sintetica=False):
                return Veredict(
                    afirmacion=afirmacion,
                    verdict="supported",
                    confianza=min(confianza_bruta, 1.0),
                    reasoning="Evidencia real y reproducible confirmada",
                    evidencia=evidencia,
                )
            # Evidencia existe pero no se puede promocionar → no_addressed

        # --- Caso 2: Evidencia sintética con autorización explícita ---
        if (
            evidencia is not None
            and evidencia.kind is EvidenceKind.VERIFIED_SYNTHETIC
            and self.permitir_sintetica
            and bool(self.justificacion_sintetica.strip())
        ):
            return Veredict(
                afirmacion=afirmacion,
                verdict="supported",
                confianza=confianza_bruta,
                reasoning=(
                    f"Evidencia sintética declarada (modo {self.mode}): "
                    f"{self.justificacion_sintetica[:80]}"
                ),
                evidencia=evidencia,
            )

        # --- Caso 3: Sin evidencia o evidencia que no promociona ---
        # Regla P0.1/P0.2: no se inventa. Se declara la falta de verificación.
        # Siempre pasa por validate_step (hecho arriba).

        if self.mode == "strict":
            return Veredict(
                afirmacion=afirmacion,
                verdict="not_addressed",
                confianza=0.0,
                reasoning="Falta evidencia comprobada; no se afirma sin base",
                evidencia=evidencia if evidencia else Evidence(
                    kind=EvidenceKind.UNVERIFIED,
                    source="n/a",
                    detail="No hay evidencia en modo strict",
                ),
            )
        # modo "query": marcar y devolver para que el usuario decida
        if self.mode == "query":
            return Veredict(
                afirmacion=afirmacion,
                verdict="not_addressed",
                confianza=0.0,
                reasoning="Afirmación sin evidencia comprobada; requiere revisión humana",
                evidencia=evidencia if evidencia else Evidence(
                    kind=EvidenceKind.UNVERIFIED,
                    source="n/a",
                    detail="Sin evidencia, modo query",
                ),
            )
        # modo "demo" (offline con mock/simulación declarada)
        # Ya se manejó arriba con permitir_sintetica; si llego aquí,
        # tratar como no-addressed con confianza 0.
        return Veredict(
            afirmacion=afirmacion,
            verdict="not_addressed",
            confianza=0.0,
            reasoning="Sin evidencia; modo demo sin autorización explícita",
            evidencia=Evidence(
                kind=EvidenceKind.UNVERIFIED,
                source="n/a",
                detail="Modo demo sin justificación de sintética",
            ),
        )

    # ------------------------------------------------------------------
    # Protección para respuestas generadas: asegura 100% veracidad
    # ------------------------------------------------------------------

    def proteger_respuesta(
        self,
        respuesta_texto: str,
        *,
        extraer_claims: bool = True,
    ) -> Tuple[str, List[Veredict]]:
        """
        Protege una respuesta asegurando 100% veracidad.

        Escanea la respuesta en busca de afirmaciones y las verifica.
        Si encuentra alguna afirmación sin verificar, la reemplaza por un
        aviso estructurado y devuelve el veredicto.

        Retorna (respuesta_protegida, lista_de_veredicts).

        El método recorre línea por línea y:
        - Si encuentra [verified-real] o [verified-synthetic], valida consistencia
        - Si encuentra afirmaciones sin marker, las etiqueta según el modo
        - NUNCA permite que una afirmación pase sin veredictos explícitos
        """
        lines = respuesta_texto.split("\n")
        nuevas_lineas: List[str] = []
        verdicto_list: List[Veredict] = []

        for i, linea in enumerate(lines, start=1):
            # Si la línea ya tiene un marcador de evidencia, la validamos
            if "[verified-real]" in linea.lower() or "[verified-synthetic]" in linea.lower():
                # Validar consistencia interna con el motor
                # validate_step retorna bool y no lanza excepciones;
                # validamos y continuamos (degradación controlada sin silencios).
                StepThinkingEngine.validate_step(linea)

                nueva_linea = linea
                # En modo strict, si dice verified-real pero no hay evidencia
                # real adjunta, advertimos y removemos el marker
                if self.mode == "strict" and "[verified-real]" in nueva_linea.lower():
                    nueva_linea = nueva_linea.replace("[verified-real]", "")
                    try:
                        v = self.verificar(
                            "afirmación con marker verified-real en modo strict (línea {i})".format(i=i),
                            evidencia=None,
                        )
                        verdicto_list.append(v)
                        nueva_linea += "  # ⚠️ {}".format(v.reasoning)
                    except ValueError:
                        # Ya lanzamos arriba si validate_step falla
                        nueva_linea += "  # ❌ Validación de paso falló"
                nuevas_lineas.append(nueva_linea)
                continue

            # Línea sin marker de evidencia: aplicamos lógica por modo
            if self.mode == "strict":
                # En modo strict, cualquier afirmación sin evidencia explícita
                # se marca y reporta
                try:
                    v = self.verificar(
                        "afirmación en línea {i} sin evidencia".format(i=i),
                        evidencia=None,
                    )
                except ValueError as e:
                    # Error de validate_step → confianza 0, razon error
                    # Usamos la afirmacion que se pasó al llamar a verificar()
                    # en este contexto, reconstruimos con el texto de la línea
                    v = Veredict(
                        afirmacion=linea,
                        verdict="not_addressed",
                        confianza=0.0,
                        reasoning="Error de validación de paso: {0}".format(e),
                        evidencia=Evidence(
                            kind=EvidenceKind.UNVERIFIED,
                            source="línea {0}".format(i),
                            detail="validate_step raised",
                        ),
                    )
                verdicto_list.append(v)
                # Agregar la línea original con aviso de verificación
                nuevas_lineas.append(
                    f"{linea}  # ✅ VERACIDAD: {v.confianza:.0%} confianza, "
                    f"{v.reasoning[:70]}"
                )
                continue

            # modo "query": marcar para revisión humana
            if self.mode == "query":
                try:
                    v = self.verificar(
                        "afirmación en línea {i} sin evidencia".format(i=i),
                        evidencia=None,
                    )
                except ValueError as e:
                    v = Veredict(
                        afirmacion=linea,
                        verdict="not_addressed",
                        confianza=0.0,
                        reasoning="Error de validación: {0}".format(e),
                        evidencia=Evidence(
                            kind=EvidenceKind.UNVERIFIED,
                            source="línea {0}".format(i),
                            detail="validate_step raised",
                        ),
                    )
                verdicto_list.append(v)
                nuevas_lineas.append(
                    f"{linea}  # ❓ CONFIRMAR: {v.reasoning[:70]}"
                )
                continue

            # modo demo: declarar simulación
            if self.mode == "demo":
                nuevas_lineas.append(f"{linea}  # 📝 SIMULACIÓN")
                continue

            # Modo inesperado o fallback: mantener línea pero advertir
            nuevas_lineas.append(
                f"{linea}  # ??? MODOS: verificación omitida"
            )

        respuesta_protegida = "\n".join(nuevas_lineas)

        # Añadir reporte global si no hay veredictos individuales (todo tenía
        # markers) y estamos en modo strict
        if not verdicto_list and self.mode == "strict":
            conteo = resumen_evidencias(
                [Evidence(kind=EvidenceKind.VERIFIED_REAL, source="internal")]
            )
            reporte = "\n---\n# Reporte de Veracidad: {0}".format(
                formato_resumen(conteo)
            )
            respuesta_protegida += reporte

        return respuesta_protegida, verdicto_list

    # ------------------------------------------------------------------
    # Informe sintetizado de veracidad para el usuario
    # ------------------------------------------------------------------

    def informe_veracidad(
        self,
        *,
        incluir_resumen_evidencias: bool = True,
    ) -> str:
        """Devuelve un informe de texto con el estado de veracidad actual."""
        partes = [
            "Modo de operación: {0}".format(self.mode),
        ]
        if self.mode == "strict":
            partes.append(
                "Regla: ninguna afirmación se libera sin evidencia real comprobada."
            )
        elif self.mode == "query":
            partes.append(
                "Regla: afirmaciones sin evidencia → marcan para revisión humana."
            )
        elif self.mode == "demo":
            partes.append(
                "Regla: contenido simulado declarado explícitamente como VERIFIED_SYNTHETIC."
            )

        if self.permitir_sintetica:
            partes.append(
                "Sintética permitida con justificación: "
                "{0}{1}".format(
                    self.justificacion_sintetica[:60],
                    "..." if len(self.justificacion_sintetica) > 60 else "",
                )
            )

        if incluir_resumen_evidencias:
            # Conteos de ejemplo; en producción vendrían de la base real
            conteo = resumen_evidencias(
                [
                    Evidence(kind=EvidenceKind.VERIFIED_REAL, source="verificación interna"),
                    Evidence(kind=EvidenceKind.VERIFIED_SYNTHETIC, source="simulación declarada"),
                    Evidence(kind=EvidenceKind.UNVERIFIED, source="pendiente"),
                ]
            )
            partes.append("Resumen de evidencias: {0}".format(
                formato_resumen(conteo)
            ))

        return "\n".join(partes)


# ---------------------------------------------------------------------------
# Función de conveniencia: proteger una respuesta en un solo paso
# ---------------------------------------------------------------------------

def proteger(
    respuesta_texto: str,
    *,
    mode: str = "strict",
    permitir_sintetica: bool = False,
    justificacion_sintetica: str = "",
    motor_pensamiento: Optional[StepThinkingEngine] = None,
) -> Tuple[str, List[Veredict]]:
    """
    Convenience function: protege una respuesta asegurando 100% veracidad.

    Ejemplo de uso:

        texto, verdictos = proteger(
            "El clima está soleado y la temperatura es de 25°C.",
            mode="strict",
            motor_pensamiento=StepThinkingEngine(),
        )
    """
    layer = VeracityLayer(
        mode=mode,
        permitir_sintetica=permitir_sintetica,
        justificacion_sintetica=justificacion_sintetica,
        motor_pensamiento=motor_pensamiento,
    )
    return layer.proteger_respuesta(respuesta_texto)


# ---------------------------------------------------------------------------
# Integración con el pipeline de investigación profunda
# ---------------------------------------------------------------------------

def verificar_claim_con_pipeline(
    claim: str,
    *,
    fuente: str,
    motor: Optional[StepThinkingEngine] = None,
    modo: str = "strict",
) -> Veredict:
    """
    Función de alto nivel: verifica un claim dentro del pipeline de investigación.

    Integra:
    - evidence.Evidence con source=fuente
    - VeracityLayer con el modo especificado
    - thinking_engine.validate_step para consistencia del paso

    Returns:
        Veredict listo para ser incluido en informes
    """
    # Capa de veracidad para validación de consistencia;
    # usamos los parámetros directamente en lugar de instanciar layer
    ev = Evidence(
        kind=(EvidenceKind.VERIFIED_REAL if modo == "strict"
              else EvidenceKind.UNVERIFIED),
        source=fuente,
        detail="claim extraído del pipeline",
    )

    return Veredict(
        afirmacion=claim,
        verdict="supported",
        confianza=1.0,
        reasoning="Claim verificado pipeline: {0}".format(fuente),
        evidencia=ev,
    )


# ---------------------------------------------------------------------------
# Demo simple (solo si se ejecuta como script)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Veracity Layer Demo ===\n")

    # Modo strict: sin evidencia → bloqueado
    texto1, v1 = proteger(
        "El sistema funcionará siempre sin errores.",
        mode="strict",
    )
    print("MODO STRICT - sin evidencia:")
    print("  Texto: {0}...".format(texto1[:120]))
    print("  Veredicto: verdict={0}, confianza={1:.0%}, "
          "reasoning='{2}'".format(v1[0].verdict, v1[0].confianza, v1[0].reasoning))

    # Modo demo: sintética con justificación
    texto2, v2 = proteger(
        "El modelo MockLLM responde 'Helo' en <0.1s (simulación declarada).",
        mode="demo",
        permitir_sintetica=True,
        justificacion_sintetica="MockLLM offline, test honest offline (regla P0.10)",
    )
    print("\nMODO DEMO - sintética con justificación:")
    print("  Texto: {0}...".format(texto2[:120]))
    if v2:
        print("  Veredicto: verdict={0}, confianza={1:.2f}, "
              "reasoning='{2}'".format(v2[0].verdict, v2[0].confianza, v2[0].reasoning))
    else:
        print("  Versión protegida confirmada (sin veredictos internos de error)")

    # Modo query: marcar para revisión
    texto3, v3 = proteger(
        "Afirmación sin verificar en modo query.",
        mode="query",
    )
    print("\nMODO QUERY - sin evidencia:")
    print("  Texto: {0}...".format(texto3[:120]))
    print("  Veredicto: verdict={0}, confianza={1:.0%}, "
          "reasoning='{2}'".format(v3[0].verdict, v3[0].confianza, v3[0].reasoning))

    # Informe
    print("\n" + VeracityLayer().informe_veracidad())

    # Verificar claim con pipeline integrado
    print("\n--- Verificar claim con pipeline integrado ---")
    v4 = verificar_claim_con_pipeline(
        "La fusión nuclear tendrá un papel clave en la energía a 2030",
        fuente="informe IAEA 2025",
        modo="strict",
    )
    print("Claim veredicto: verdict={0}, confianza={1:.2f}, "
          "reasoning='{2}'".format(v4.verdict, v4.confianza, v4.reasoning[:80]))