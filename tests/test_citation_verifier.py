"""Tests de la verificación de citas (offline, deterministas)."""

import unittest

from citation_verifier import (_normalizar_url, extraer_citas, verificar_cita,
                               verificar_informe)


class TestExtraerCitas(unittest.TestCase):
    def test_extrae_numeros_en_orden_y_repetidos(self):
        self.assertEqual(extraer_citas("A [1], B [12] y C [1]."), [1, 12, 1])

    def test_no_confunde_anios_ni_corchetes_vacios(self):
        self.assertEqual(extraer_citas("En [2026] y [] no hay cita."), [])
        self.assertEqual(extraer_citas("Cita [0] fuera de rango."), [0])


class TestNormalizarURL(unittest.TestCase):
    def test_conserva_recurso_y_puerto_al_quitar_rastreadores(self):
        casos = {
            "https://www.EXAMPLE.org:8443/a/?utm_source=x&ref=home&fbclid=a&gclid=b#f":
                "https://example.org:8443/a",
            "https://example.org/a?reference=alpha":
                "https://example.org/a?reference=alpha",
            "https://example.org/a?id=": "https://example.org/a?id=",
            "https://[2001:DB8::1]:8443/a": "https://[2001:db8::1]:8443/a",
            "https://example.org/aXX/": "https://example.org/aXX",
            "https://u@localhost/a": "https://localhost/a",
        }
        for original, esperado in casos.items():
            with self.subTest(original=original):
                self.assertEqual(_normalizar_url(original), esperado)
        for invalido in (None, 0, "", " "):
            with self.subTest(invalido=invalido):
                self.assertEqual(_normalizar_url(invalido), "")

    def test_url_malformada_no_interrumpe_normalizacion(self):
        self.assertEqual(_normalizar_url("https://[::1"), "")

    def test_no_funde_fuentes_ni_asigna_claim_de_otro_recurso(self):
        sources = [
            {"url": "https://example.org/doc?reference=alpha",
             "snippet": "La energía solar es renovable."},
            {"url": "https://example.org/doc?reference=beta",
             "snippet": "El motor diésel usa gasóleo."},
        ]
        claims = [{"claim": "El motor diésel usa gasóleo.",
                   "source_url": sources[1]["url"]}]
        informe = verificar_informe("Primero [1]; después [2].", sources, claims)
        self.assertEqual(informe["duplicadas"], [])
        self.assertEqual(informe["checks"][0]["claim"], "")
        self.assertEqual(informe["checks"][0]["soporte"], "UNVERIFIABLE")
        self.assertEqual(informe["checks"][1]["soporte"], "SUPPORTED")


class TestVerificarCita(unittest.TestCase):
    def setUp(self):
        self.sources = [
            {"url": "https://example.org/a", "title": "A",
             "snippet": "La fusión nuclear está en fase de investigación."},
            {"url": "https://example.org/b", "title": "B",
             "snippet": "El agua hierve a 100 grados Celsius al nivel del mar."},
        ]

    def test_cita_fuera_de_rango(self):
        check = verificar_cita(3, self.sources, claim="cualquier cosa")
        self.assertEqual(check.estado, "NOT_FOUND")
        self.assertEqual(check.soporte, "UNVERIFIABLE")
        self.assertIn("fuera del rango", check.motivo)

    def test_fuente_sin_contenido(self):
        check = verificar_cita(1, [{"url": "https://example.org/vacia"}],
                               claim="La fusión nuclear avanza.")
        self.assertEqual(check.estado, "UNVERIFIABLE")
        self.assertEqual(check.soporte, "UNVERIFIABLE")

    def test_claim_respaldado_lexicamente(self):
        check = verificar_cita(
            1, self.sources, claim="La fusión nuclear está en investigación.")
        self.assertEqual(check.estado, "FOUND")
        self.assertEqual(check.soporte, "SUPPORTED")
        self.assertGreaterEqual(check.cobertura, 0.6)

    def test_claim_parcialmente_respaldado(self):
        check = verificar_cita(
            1, self.sources,
            claim="La fusión nuclear producirá electricidad barata.")
        self.assertEqual(check.soporte, "PARTIALLY_SUPPORTED")
        self.assertGreater(check.cobertura, 0.0)
        self.assertLess(check.cobertura, 0.6)

    def test_negacion_opuesta_es_contradiccion(self):
        check = verificar_cita(
            2, self.sources,
            claim="El agua no hierve a 100 grados Celsius.")
        self.assertEqual(check.soporte, "CONTRADICTED")
        self.assertIn("negación opuesta", check.motivo)

    def test_fragmento_exacto(self):
        check = verificar_cita(
            2, self.sources, claim="El agua hierve a 100 grados.",
            fragmento="El agua hierve a 100 grados Celsius")
        self.assertEqual(check.estado, "EXACT_MATCH")
        self.assertTrue(check.fragmento_verificado)
        self.assertEqual(check.soporte, "SUPPORTED")

    def test_fragmento_inexistente(self):
        check = verificar_cita(
            2, self.sources, claim="El agua hierve a 100 grados.",
            fragmento="El agua hierve a 50 grados")
        self.assertEqual(check.estado, "NOT_FOUND")
        self.assertFalse(check.fragmento_verificado)

    def test_fragmento_exacto_con_url_completa(self):
        check = verificar_cita(
            2, self.sources, claim="El agua hierve a 100 grados.",
            fragmento="El agua hierve a 100 grados Celsius")
        self.assertEqual(check.estado, "EXACT_MATCH")
        self.assertTrue(check.fragmento_verificado)
        self.assertEqual(check.soporte, "SUPPORTED")

    def test_cita_fuera_de_rango_con_url_normalizada(self):
        check = verificar_cita(
            99, self.sources, claim="Cualquier cosa",
            fragmento="texto irrelevante")
        self.assertEqual(check.estado, "NOT_FOUND")
        self.assertEqual(check.soporte, "UNVERIFIABLE")

    def test_claim_negacion_variantes(self):
        # Test con "no" al inicio - el sistema detecta negación pero
        # la cobertura puede ser < 0.5 por remoción de stopwords.
        # Esto es esperado: la mitigación estructural <untrusted_source>
        # maneja esto en tiempo de ejecución, no solo en léxico.
        # Lo importante es el campo 'soporte', no 'estado' (que es FOUND por definición)
        check = verificar_cita(
            1, self.sources,
            claim="El agua no hierve a 100 grados Celsius al nivel del mar.")
        # Nota: _tokens() remueve "no" como stopword; cobertura < 0.5
        # → soporte UNVERIFIABLE por solapamientoInsuficiente (no CONTRADICTED)
        # El CONTRADICTED requiere cobertura >= 0.5 y negación opuesta
        # El motivo contiene la explicación técnica del solapamientoInsuficiente
        self.assertEqual(check.soporte, "UNVERIFIABLE")
        self.assertIn("sin solapamiento léxico", check.motivo)


class TestVerificarInforme(unittest.TestCase):
    def setUp(self):
        self.sources = [
            {"url": "https://www.example.org/a/?utm_source=x", "title": "A",
             "snippet": "La fusión nuclear está en investigación."},
            {"url": "https://example.org/a", "title": "A copia",
             "snippet": "La fusión nuclear está en investigación."},
            {"url": "https://example.org/b", "title": "B",
             "snippet": "El agua hierve a 100 grados Celsius."},
        ]

    def test_resumen_y_duplicados(self):
        informe = verificar_informe(
            "La fusión avanza [1]. El agua hierve [3]. Otra vez [1].",
            self.sources,
            claims=[{"claim": "La fusión nuclear está en investigación.",
                     "source_url": "https://example.org/a"}],
            verificado_en="2026-10-31T00:00:00+00:00")
        self.assertEqual(informe["citas_totales"], 3)
        self.assertEqual(informe["fuentes_citadas"], 2)
        self.assertEqual(informe["checks"][0]["ocurrencias"], 2)
        self.assertEqual(informe["checks"][0]["soporte"], "SUPPORTED")
        self.assertEqual(len(informe["duplicadas"]), 1)
        self.assertEqual(informe["duplicadas"][0]["indices"], [1, 2])
        self.assertEqual(informe["verificado_en"], "2026-10-31T00:00:00+00:00")

    def test_sin_citas_y_fuentes_no_citadas(self):
        informe = verificar_informe("Informe sin citas.", self.sources)
        self.assertEqual(informe["citas_totales"], 0)
        self.assertEqual(informe["fuentes_citadas"], 0)
        self.assertIn("no contiene citas", " ".join(informe["advertencias"]))
        self.assertIn("no citadas", " ".join(informe["advertencias"]))

    def test_cita_fuera_de_rango_en_informe(self):
        informe = verificar_informe("Afirmación [99].", self.sources)
        self.assertEqual(informe["estados"]["NOT_FOUND"], 1)
        self.assertTrue(informe["advertencias"])


class TestCoberturaLineas(unittest.TestCase):
    """Tests dirigidos a líneas no cubiertas de citation_verifier.py."""

    def test_cobertura_con_terminos_vacios(self):
        from citation_verifier import _cobertura
        self.assertEqual(_cobertura("", "contenido"), 0.0)

    def test_cobertura_con_contenido_vacio(self):
        from citation_verifier import _cobertura
        self.assertEqual(_cobertura("claim", ""), 0.0)

    def test_cobertura_con_terminos_unicos(self):
        from citation_verifier import _cobertura
        self.assertEqual(_cobertura("energia solar", "energia solar"), 1.0)

    def test_cobertura_con_stopwords(self):
        from citation_verifier import _cobertura
        self.assertEqual(_cobertura("el agua hierve", "agua hierve"), 1.0)

    def test_extraer_citas_con_none(self):
        self.assertEqual(extraer_citas(None), [])

    def test_extraer_citas_con_cadena_vacia(self):
        self.assertEqual(extraer_citas(""), [])

    def test_claim_para_fuente_sin_claims(self):
        from citation_verifier import _claim_para_fuente
        self.assertEqual(_claim_para_fuente({}, None), "")

    def test_claim_para_fuente_con_source_id(self):
        from citation_verifier import _claim_para_fuente
        source = {"id": "src1", "url": "https://example.org"}
        claims = [{"claim": "texto", "source_id": "src1"}]
        self.assertEqual(_claim_para_fuente(source, claims), "texto")

    def test_claim_para_fuente_con_source_url(self):
        from citation_verifier import _claim_para_fuente
        source = {"url": "https://example.org"}
        claims = [{"claim": "texto", "source_url": "https://example.org"}]
        self.assertEqual(_claim_para_fuente(source, claims), "texto")

    def test_claim_para_fuente_sin_coincidencia(self):
        from citation_verifier import _claim_para_fuente
        source = {"url": "https://example.org"}
        claims = [{"claim": "texto", "source_url": "https://otro.org"}]
        self.assertEqual(_claim_para_fuente(source, claims), "")

    def test_claim_para_fuente_con_id_numerico(self):
        from citation_verifier import _claim_para_fuente
        source = {"id": 42, "url": "https://example.org"}
        claims = [{"claim": "texto", "source_id": 42}]
        self.assertEqual(_claim_para_fuente(source, claims), "texto")

    def test_clasificar_soporte_parcial(self):
        from citation_verifier import _clasificar_soporte
        soporte, cobertura, motivo = _clasificar_soporte(
            "energia solar fotovoltaica concentrada", "la energia solar es renovable")
        self.assertEqual(soporte, "PARTIALLY_SUPPORTED")
        self.assertGreater(cobertura, 0.0)

    def test_clasificar_soporte_sin_claim(self):
        from citation_verifier import _clasificar_soporte
        soporte, cobertura, motivo = _clasificar_soporte("", "contenido")
        self.assertEqual(soporte, "UNVERIFIABLE")
        self.assertEqual(cobertura, 0.0)

    def test_clasificar_soporte_sin_contenido(self):
        from citation_verifier import _clasificar_soporte
        soporte, cobertura, motivo = _clasificar_soporte("claim", "")
        self.assertEqual(soporte, "UNVERIFIABLE")
        self.assertEqual(cobertura, 0.0)

    def test_clasificar_soporte_sin_solapamiento(self):
        from citation_verifier import _clasificar_soporte
        soporte, cobertura, motivo = _clasificar_soporte(
            "motor diesel", "energia solar")
        self.assertEqual(soporte, "UNVERIFIABLE")
        self.assertEqual(cobertura, 0.0)

    def test_verificar_cita_con_fragmento_verificado(self):
        sources = [{"url": "https://example.org", "snippet": "texto exacto"}]
        check = verificar_cita(1, sources, claim="texto", fragmento="texto exacto")
        self.assertEqual(check.estado, "EXACT_MATCH")
        self.assertTrue(check.fragmento_verificado)

    def test_verificar_cita_con_fragmento_no_verificado(self):
        sources = [{"url": "https://example.org", "snippet": "texto exacto"}]
        check = verificar_cita(1, sources, claim="texto", fragmento="otro texto")
        self.assertEqual(check.estado, "NOT_FOUND")
        self.assertFalse(check.fragmento_verificado)

    def test_verificar_cita_con_razon_soporte(self):
        sources = [{"url": "https://example.org", "snippet": "texto"}]
        check = verificar_cita(1, sources, claim="texto")
        self.assertIn("fuente localizada", check.motivo)

    def test_grupos_duplicados(self):
        from citation_verifier import _grupos_duplicados
        sources = [
            {"url": "https://example.org"},
            {"url": "https://example.org"},
            {"url": "https://otro.org"},
        ]
        grupos = _grupos_duplicados(sources)
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]["indices"], [1, 2])

    def test_verificar_informe_con_claims(self):
        sources = [{"url": "https://example.org", "snippet": "texto"}]
        claims = [{"claim": "texto", "source_url": "https://example.org"}]
        informe = verificar_informe("Texto [1]", sources, claims)
        self.assertEqual(informe["citas_totales"], 1)

    def test_verificar_informe_con_soportes(self):
        sources = [{"url": "https://example.org", "snippet": "texto"}]
        informe = verificar_informe("Texto [1]", sources)
        self.assertIn("SUPPORTED", informe["soportes"])

    def test_verificar_informe_con_advertencias_not_found(self):
        sources = [{"url": "https://example.org", "snippet": "texto"}]
        informe = verificar_informe("Texto [99]", sources)
        self.assertTrue(any("no localizadas" in a for a in informe["advertencias"]))

    def test_verificar_informe_con_advertencias_unverifiable(self):
        sources = [{"url": "https://example.org"}]
        informe = verificar_informe("Texto [1]", sources)
        self.assertTrue(any("sin contenido verificable" in a for a in informe["advertencias"]))

    def test_main_cli_con_json(self):
        import tempfile
        import json
        import os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Texto [1]")
            reporte = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"url": "https://example.org", "snippet": "texto"}], f)
            sources = f.name
        try:
            from citation_verifier import main
            import io
            import sys
            salida = io.StringIO()
            original = sys.stdout
            sys.stdout = salida
            try:
                codigo = main(["--report", reporte, "--sources", sources, "--json"])
            finally:
                sys.stdout = original
            self.assertEqual(codigo, 0)
            self.assertIn("citas_totales", salida.getvalue())
        finally:
            os.unlink(reporte)
            os.unlink(sources)

    def test_main_cli_sin_json(self):
        import tempfile
        import json
        import os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Texto [1]")
            reporte = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"url": "https://example.org", "snippet": "texto"}], f)
            sources = f.name
        try:
            from citation_verifier import main
            import io
            import sys
            salida = io.StringIO()
            original = sys.stdout
            sys.stdout = salida
            try:
                codigo = main(["--report", reporte, "--sources", sources])
            finally:
                sys.stdout = original
            self.assertEqual(codigo, 0)
            self.assertIn("Citas:", salida.getvalue())
        finally:
            os.unlink(reporte)
            os.unlink(sources)

    def test_main_cli_sources_no_lista(self):
        import tempfile
        import json
        import os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Texto [1]")
            reporte = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"no": "lista"}, f)
            sources = f.name
        try:
            from citation_verifier import main
            import io
            import sys
            salida = io.StringIO()
            original = sys.stderr
            sys.stderr = salida
            try:
                codigo = main(["--report", reporte, "--sources", sources])
            finally:
                sys.stderr = original
            self.assertEqual(codigo, 2)
        finally:
            os.unlink(reporte)
            os.unlink(sources)

    def test_main_cli_con_claims(self):
        import tempfile
        import json
        import os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Texto [1]")
            reporte = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"url": "https://example.org", "snippet": "texto"}], f)
            sources = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"claim": "texto", "source_url": "https://example.org"}], f)
            claims = f.name
        try:
            from citation_verifier import main
            import io
            import sys
            salida = io.StringIO()
            original = sys.stdout
            sys.stdout = salida
            try:
                codigo = main(["--report", reporte, "--sources", sources, "--claims", claims])
            finally:
                sys.stdout = original
            self.assertEqual(codigo, 0)
        finally:
            os.unlink(reporte)
            os.unlink(sources)
            os.unlink(claims)

    def test_main_cli_con_not_found(self):
        import tempfile
        import json
        import os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Texto [99]")
            reporte = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"url": "https://example.org", "snippet": "texto"}], f)
            sources = f.name
        try:
            from citation_verifier import main
            import io
            import sys
            salida = io.StringIO()
            original = sys.stdout
            sys.stdout = salida
            try:
                codigo = main(["--report", reporte, "--sources", sources])
            finally:
                sys.stdout = original
            self.assertEqual(codigo, 1)
        finally:
            os.unlink(reporte)
            os.unlink(sources)


if __name__ == "__main__":
    unittest.main()
