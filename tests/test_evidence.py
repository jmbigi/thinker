"""Tests de evidence.py: tipos, atribución y regla de promoción."""

import unittest

from evidence import (Evidence, EvidenceKind, formato_resumen,
                      puede_promocionar, resumen_evidencias)


class TestEvidenceKind(unittest.TestCase):
    def test_valores_y_marcadores_estables(self):
        self.assertEqual(EvidenceKind.VERIFIED_REAL.value, "verified-real")
        self.assertEqual(EvidenceKind.VERIFIED_SYNTHETIC.value,
                         "verified-synthetic")
        self.assertEqual(EvidenceKind.UNVERIFIED.value, "unverified")
        self.assertEqual(EvidenceKind.VERIFIED_REAL.marcador,
                         "[VERIFIED-REAL]")
        self.assertEqual(EvidenceKind.VERIFIED_SYNTHETIC.marcador,
                         "[VERIFIED-SYNTHETIC]")
        self.assertEqual(EvidenceKind.UNVERIFIED.marcador, "[UNVERIFIED]")


class TestEvidence(unittest.TestCase):
    def test_evidencia_real_exige_fuente(self):
        with self.assertRaises(ValueError):
            Evidence(EvidenceKind.VERIFIED_REAL, "   ")

    def test_evidencia_sintetica_exige_fuente(self):
        with self.assertRaises(ValueError):
            Evidence(EvidenceKind.VERIFIED_SYNTHETIC, "")

    def test_evidencia_no_verificada_puede_no_tener_fuente(self):
        evidencia = Evidence(EvidenceKind.UNVERIFIED, "")
        self.assertEqual(evidencia.marcador, "[UNVERIFIED]")
        self.assertEqual(evidencia.source, "")

    def test_tipo_invalido_se_rechaza(self):
        with self.assertRaises(TypeError):
            Evidence("verified-real", "archivo.py:1")  # type: ignore[arg-type]

    def test_fuente_no_textual_se_rechaza(self):
        with self.assertRaises(TypeError):
            Evidence(EvidenceKind.VERIFIED_REAL, 42)  # type: ignore[arg-type]


class TestPromocion(unittest.TestCase):
    def test_real_promociona(self):
        evidencia = Evidence(EvidenceKind.VERIFIED_REAL, "tests/test_x.py")
        self.assertTrue(puede_promocionar(evidencia))

    def test_sintetica_no_promociona_por_defecto(self):
        evidencia = Evidence(EvidenceKind.VERIFIED_SYNTHETIC,
                             "MockLLM (simulado)")
        self.assertFalse(puede_promocionar(evidencia))

    def test_sintetica_exige_autorizacion_y_justificacion(self):
        evidencia = Evidence(EvidenceKind.VERIFIED_SYNTHETIC,
                             "MockLLM (simulado)")
        self.assertFalse(puede_promocionar(
            evidencia, permitir_sintetica=True, justificacion="  "))
        self.assertFalse(puede_promocionar(
            evidencia, permitir_sintetica=False,
            justificacion="modo demo offline"))
        self.assertTrue(puede_promocionar(
            evidencia, permitir_sintetica=True,
            justificacion="modo demo offline declarado"))

    def test_no_verificada_no_promociona_nunca(self):
        evidencia = Evidence(EvidenceKind.UNVERIFIED, "PyPI")
        self.assertFalse(puede_promocionar(evidencia))
        self.assertFalse(puede_promocionar(
            evidencia, permitir_sintetica=True,
            justificacion="autorización explícita"))

    def test_entrada_que_no_es_evidencia_se_rechaza(self):
        with self.assertRaises(TypeError):
            puede_promocionar(EvidenceKind.VERIFIED_REAL)  # type: ignore[arg-type]


class TestResumen(unittest.TestCase):
    def test_resumen_vacio_incluye_las_tres_claves(self):
        self.assertEqual(resumen_evidencias([]), {
            "verified-real": 0,
            "verified-synthetic": 0,
            "unverified": 0,
        })

    def test_cuenta_evidencias_y_tipos(self):
        resumen = resumen_evidencias([
            Evidence(EvidenceKind.VERIFIED_REAL, "a.py"),
            EvidenceKind.VERIFIED_REAL,
            Evidence(EvidenceKind.VERIFIED_SYNTHETIC, "MockLLM"),
            EvidenceKind.UNVERIFIED,
        ])
        self.assertEqual(resumen, {
            "verified-real": 2,
            "verified-synthetic": 1,
            "unverified": 1,
        })

    def test_elemento_invalido_se_rechaza(self):
        with self.assertRaises(TypeError):
            resumen_evidencias(["verified-real"])  # type: ignore[list-item]

    def test_formato_resumen_usa_los_marcadores(self):
        texto = formato_resumen({"verified-real": 2, "verified-synthetic": 0,
                                 "unverified": 1})
        self.assertIn("[VERIFIED-REAL] 2", texto)
        self.assertIn("[VERIFIED-SYNTHETIC] 0", texto)
        self.assertIn("[UNVERIFIED] 1", texto)


if __name__ == "__main__":
    unittest.main()
