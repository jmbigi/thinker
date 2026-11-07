"""Contrato offline del gate local fail-closed para tool calls.

No usa red ni el plugin dsh-agent-gate: prueba la política local de
`LocalToolGate`, que replica su semántica (riesgo, raíces, cuota, auditoría).
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from llm_providers import (GateCheckedLLM, GateDecision, GateResult,
                           LocalToolGate, gate_check)


class _Provider:
    model = "stub"
    base_url = None

    def generate(self, prompt, model=None, **kwargs):
        return "respuesta"


class TestLocalToolGate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "dentro.txt").write_text("ok", encoding="utf-8")
        self.audit = self.root / "auditoria.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def _gate(self, **kwargs):
        kwargs.setdefault("allowed_roots", [self.root])
        kwargs.setdefault("max_calls_per_minute", 100)
        return LocalToolGate(**kwargs)

    def test_sin_allowed_roots_deniega_cualquier_ruta(self):
        gate = LocalToolGate(allowed_roots=[], max_calls_per_minute=100)
        resultado = gate.check("read_file", {"path": str(self.root / "dentro.txt")})
        self.assertEqual(resultado.decision, GateDecision.DENY)
        self.assertIn("allowed_roots", resultado.reason)
        self.assertEqual(resultado.risk_level, "read_only")

    def test_ruta_dentro_de_la_raiz_se_permite(self):
        resultado = self._gate().check(
            "read_file", {"path": str(self.root / "dentro.txt")})
        self.assertEqual(resultado.decision, GateDecision.ALLOW)
        self.assertEqual(resultado.reason, "permitido")

    def test_ruta_fuera_de_la_raiz_se_deniega(self):
        resultado = self._gate().check("read_file", {"path": "/etc/passwd"})
        self.assertEqual(resultado.decision, GateDecision.DENY)
        self.assertIn("fuera de allowed_roots", resultado.reason)

    def test_traversal_se_resuelve_antes_de_comparar(self):
        resultado = self._gate().check(
            "read_file", {"path": str(self.root / ".." / "fuera.txt")})
        self.assertEqual(resultado.decision, GateDecision.DENY)

    def test_symlink_que_escapa_se_deniega(self):
        enlace = self.root / "enlace"
        try:
            os.symlink("/etc/passwd", enlace)
        except (OSError, NotImplementedError):
            # Sin symlinks no hay escape que probar; se comprueba el mismo
            # destino directo para que la prueba siga teniendo una aserción.
            self.assertEqual(
                self._gate().check("read_file", {"path": "/etc/passwd"}).decision,
                GateDecision.DENY)
            return
        resultado = self._gate().check("read_file", {"path": str(enlace)})
        self.assertEqual(resultado.decision, GateDecision.DENY)

    def test_herramienta_prohibida_se_deniega_aunque_la_ruta_sea_valida(self):
        resultado = self._gate().check(
            "run_shell", {"cmd": "cat", "path": str(self.root / "dentro.txt")})
        self.assertEqual(resultado.decision, GateDecision.DENY)
        self.assertEqual(resultado.risk_level, "forbidden")
        self.assertIn("prohibida", resultado.reason)

    def test_allowlist_restringe_a_lo_declarado(self):
        gate = self._gate(allow_tools=["read_file"])
        self.assertEqual(
            gate.check("read_file", {"path": str(self.root / "dentro.txt")}).decision,
            GateDecision.ALLOW)
        self.assertEqual(
            gate.check("list_dir", {"path": str(self.root)}).decision,
            GateDecision.DENY)

    def test_deny_tools_gana_a_la_allowlist(self):
        gate = self._gate(allow_tools=["read_file"], deny_tools=["read_file"])
        self.assertEqual(
            gate.check("read_file", {"path": str(self.root / "dentro.txt")}).decision,
            GateDecision.DENY)

    def test_escritura_sin_callback_se_deniega(self):
        resultado = self._gate().check(
            "write_file", {"path": str(self.root / "nuevo.txt")})
        self.assertEqual(resultado.decision, GateDecision.DENY)
        self.assertIn("confirmación", resultado.reason)

    def test_escritura_confirmada_se_permite(self):
        gate = self._gate(confirm=lambda tool, args: True)
        resultado = gate.check("write_file", {"path": str(self.root / "nuevo.txt")})
        self.assertEqual(resultado.decision, GateDecision.ALLOW)
        self.assertEqual(resultado.reason, "confirmado")

    def test_confirmacion_rechazada_se_deniega(self):
        gate = self._gate(confirm=lambda tool, args: False)
        self.assertEqual(
            gate.check("write_file", {"path": str(self.root / "nuevo.txt")}).decision,
            GateDecision.DENY)

    def test_confirmacion_que_falla_se_deniega(self):
        def rompe(tool, args):
            raise RuntimeError("operador no disponible")
        gate = self._gate(confirm=rompe)
        resultado = gate.check("write_file", {"path": str(self.root / "nuevo.txt")})
        self.assertEqual(resultado.decision, GateDecision.DENY)
        self.assertIn("confirmación falló", resultado.reason)

    def test_limite_por_minuto(self):
        gate = self._gate(max_calls_per_minute=2)
        self.assertEqual(
            gate.check("read_file", {"path": str(self.root / "dentro.txt")}).decision,
            GateDecision.ALLOW)
        self.assertEqual(
            gate.check("read_file", {"path": str(self.root / "dentro.txt")}).decision,
            GateDecision.ALLOW)
        tercera = gate.check("read_file", {"path": str(self.root / "dentro.txt")})
        self.assertEqual(tercera.decision, GateDecision.DENY)
        self.assertIn("llamadas/minuto", tercera.reason)

    def test_limite_cero_deniega_todo(self):
        gate = self._gate(max_calls_per_minute=0)
        self.assertEqual(gate.check("search", {"query": "x"}).decision,
                         GateDecision.DENY)

    def test_auditoria_jsonl_no_guarda_los_argumentos_crudos(self):
        gate = self._gate(audit_path=self.audit)
        gate.check("read_file", {"path": str(self.root / "dentro.txt")})
        linea = json.loads(self.audit.read_text(encoding="utf-8").strip())
        self.assertEqual(linea["tool"], "read_file")
        self.assertEqual(linea["decision"], "allow")
        self.assertEqual(len(linea["args_sha256"]), 64)
        self.assertNotIn("dentro.txt", json.dumps(linea))

    def test_auditoria_no_escribible_deniega(self):
        gate = self._gate(audit_path="/proc/1/auditoria-imposible.jsonl")
        resultado = gate.check("read_file", {"path": str(self.root / "dentro.txt")})
        self.assertEqual(resultado.decision, GateDecision.DENY)
        self.assertIn("auditoría", resultado.reason)

    def test_rutas_anidadas_tambien_se_comprueban(self):
        resultado = self._gate().check(
            "read_file", {"opciones": {"ruta_hija": "/etc/passwd"}})
        self.assertEqual(resultado.decision, GateDecision.DENY)
        self.assertIn("allowed_roots", resultado.reason)

    def test_gate_check_usa_el_gate_inyectado(self):
        gate = self._gate()
        resultado = gate_check(
            "read_file", {"path": str(self.root / "dentro.txt")}, gate=gate)
        self.assertEqual(resultado.decision, GateDecision.ALLOW)


class TestGateCheckedLLM(unittest.TestCase):
    def test_check_tool_deniega_con_fail_closed(self):
        gate = LocalToolGate(allowed_roots=[], max_calls_per_minute=100)
        llm = GateCheckedLLM(_Provider(), gate=gate)
        with self.assertRaisesRegex(PermissionError, "Gate denegó"):
            llm.check_tool("read_file", {"path": "/etc/passwd"})

    def test_check_tool_devuelve_denegacion_sin_fail_closed(self):
        gate = LocalToolGate(allowed_roots=[], max_calls_per_minute=100)
        llm = GateCheckedLLM(_Provider(), gate=gate, fail_closed=False)
        self.assertEqual(
            llm.check_tool("read_file", {"path": "/etc/passwd"}).decision,
            GateDecision.DENY)

    def test_generate_no_ejecuta_herramientas(self):
        llm = GateCheckedLLM(_Provider())
        self.assertEqual(llm.generate("hola"), "respuesta")


class TestGateResult(unittest.TestCase):
    def test_from_json_allow(self):
        resultado = GateResult.from_json(
            {"decision": "ALLOW", "reason": "ok", "risk_level": "read_only"})
        self.assertEqual(resultado.decision, GateDecision.ALLOW)

    def test_from_json_need_confirm_se_trata_como_denegado(self):
        resultado = GateResult.from_json({"decision": "need_confirm"})
        self.assertEqual(resultado.decision, GateDecision.DENY)

    def test_from_json_desconocido_es_error(self):
        self.assertEqual(GateResult.from_json({}).decision, GateDecision.ERROR)


if __name__ == "__main__":
    unittest.main()
