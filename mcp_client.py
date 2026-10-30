#!/usr/bin/env python3
"""Cliente MCP stdio acotado y adaptador de búsqueda.

El servidor se ejecuta sin shell y sin heredar credenciales del entorno. Las
respuestas son datos no confiables: se validan antes de entrar al pipeline.
"""

import json
import os
import queue
import subprocess
import threading
from typing import Any, Dict, Iterable, List, Optional

from web_search import SearchAPI, _url_publica

PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOLS = {PROTOCOL_VERSION, "2024-11-05"}
MAX_STDERR = 64 * 1024


class MCPStdioClient:
    """Sesión JSON-RPC secuencial con timeout, allowlist y límite de salida."""

    def __init__(self, command: Iterable[str], timeout: float = 10.0,
                 max_output_bytes: int = 1024 * 1024,
                 allowed_tools: Optional[Iterable[str]] = None,
                 env: Optional[Dict[str, str]] = None):
        if isinstance(command, (str, bytes)):
            raise TypeError("command debe ser una secuencia de argumentos, no shell")
        self.command = list(command)
        if not self.command or not all(isinstance(arg, str) and arg for arg in self.command):
            raise ValueError("command debe contener argumentos no vacíos")
        if timeout <= 0 or max_output_bytes < 1:
            raise ValueError("timeout y max_output_bytes deben ser positivos")
        self.timeout = timeout
        self.max_output_bytes = max_output_bytes
        self.allowed_tools = set(allowed_tools) if allowed_tools is not None else None
        self.env = dict(env) if env is not None else {}
        self.audit_log: List[Dict[str, Any]] = []
        self._process = None
        self._responses = None
        self._stderr = bytearray()
        self._output_bytes = 0
        self._next_id = 0
        self._initialized = False

    def __enter__(self):
        entorno = {"PATH": os.environ.get("PATH", "")}
        if os.name == "nt" and "SystemRoot" in os.environ:
            entorno["SystemRoot"] = os.environ["SystemRoot"]
        entorno.update(self.env)
        try:
            self._process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=entorno,
            )
        except OSError as exc:
            raise RuntimeError(f"No se pudo iniciar el servidor MCP: {exc}") from exc
        self._responses = queue.Queue()
        threading.Thread(target=self._leer_stdout, args=(self._process,), daemon=True).start()
        threading.Thread(target=self._leer_stderr, args=(self._process,), daemon=True).start()
        try:
            self.initialize()
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _leer_stdout(self, proceso):
        try:
            while True:
                linea = proceso.stdout.readline(self.max_output_bytes + 1)
                if not linea:
                    self._responses.put(EOFError("Servidor MCP cerró stdout"))
                    return
                self._output_bytes += len(linea)
                if self._output_bytes > self.max_output_bytes:
                    proceso.kill()
                    self._responses.put(RuntimeError("Salida MCP demasiado grande"))
                    return
                self._responses.put(linea)
        except (OSError, ValueError) as exc:
            self._responses.put(exc)

    def _leer_stderr(self, proceso):
        try:
            while True:
                bloque = proceso.stderr.read(8192)
                if not bloque:
                    return
                restante = MAX_STDERR - len(self._stderr)
                if restante > 0:
                    self._stderr.extend(bloque[:restante])
        except (OSError, ValueError):
            return

    def _enviar(self, mensaje: Dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Servidor MCP no iniciado")
        try:
            self._process.stdin.write(json.dumps(mensaje).encode("utf-8") + b"\n")
            self._process.stdin.flush()
        except (OSError, BrokenPipeError) as exc:
            raise RuntimeError(f"No se pudo escribir al servidor MCP: {exc}") from exc

    def _respuesta(self, identificador: int) -> Dict[str, Any]:
        while True:
            try:
                linea = self._responses.get(timeout=self.timeout)
            except queue.Empty as exc:
                self._process.kill()
                raise TimeoutError(f"Timeout MCP ({self.timeout}s)") from exc
            if isinstance(linea, BaseException):
                raise RuntimeError(f"Fallo de transporte MCP: {linea}")
            try:
                mensaje = json.loads(linea)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise RuntimeError("Respuesta MCP no es JSON-RPC válido") from exc
            if mensaje.get("jsonrpc") != "2.0":
                raise RuntimeError("Respuesta MCP sin jsonrpc=2.0")
            if "id" not in mensaje:
                continue
            if mensaje.get("id") != identificador:
                raise RuntimeError(f"ID MCP inesperado: {mensaje.get('id')!r}")
            if "error" in mensaje:
                raise RuntimeError(f"Error MCP: {mensaje['error']}")
            if not isinstance(mensaje.get("result"), dict):
                raise RuntimeError("Respuesta MCP sin result objeto")
            return mensaje["result"]

    def _request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self._next_id += 1
        identificador = self._next_id
        self.audit_log.append({"method": method, "params": params})
        self._enviar({"jsonrpc": "2.0", "id": identificador,
                      "method": method, "params": params})
        return self._respuesta(identificador)

    def initialize(self) -> Dict[str, Any]:
        if self._initialized:
            raise RuntimeError("La sesión MCP ya estaba inicializada")
        resultado = self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "thinker-research", "version": "1.0"},
        })
        version = resultado.get("protocolVersion")
        if version not in SUPPORTED_PROTOCOLS:
            raise RuntimeError(f"Versión MCP no soportada: {version!r}")
        if "tools" not in resultado.get("capabilities", {}):
            raise RuntimeError("El servidor MCP no declara la capacidad tools")
        self._enviar({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True
        return resultado

    def list_tools(self) -> List[Dict[str, Any]]:
        if not self._initialized:
            raise RuntimeError("MCP no inicializado")
        herramientas = self._request("tools/list", {}).get("tools")
        if not isinstance(herramientas, list):
            raise RuntimeError("tools/list no devolvió una lista")
        if self.allowed_tools is not None:
            herramientas = [h for h in herramientas
                            if h.get("name") in self.allowed_tools]
        return herramientas

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("MCP no inicializado")
        if self.allowed_tools is not None and name not in self.allowed_tools:
            raise PermissionError(f"Herramienta MCP no permitida: {name}")
        resultado = self._request("tools/call", {"name": name, "arguments": arguments})
        if resultado.get("isError"):
            raise RuntimeError(f"La herramienta MCP {name} devolvió isError=true")
        return resultado

    def close(self) -> None:
        if self._process is None:
            return
        proceso = self._process
        self._process = None
        if proceso.stdin is not None:
            try:
                proceso.stdin.close()
            except OSError as exc:
                import sys
                print(f"[MCP] Error al cerrar stdin: {exc}", file=sys.stderr)
        try:
            proceso.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proceso.terminate()
            try:
                proceso.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait(timeout=2)


class MCPSearchAPI(SearchAPI):
    """Expone una herramienta MCP de búsqueda como SearchAPI."""

    def __init__(self, command: Iterable[str], tool: str = "search",
                 timeout: float = 10.0, max_output_bytes: int = 1024 * 1024):
        self.command = list(command) if not isinstance(command, (str, bytes)) else command
        self.tool = tool
        self.timeout = timeout
        self.max_output_bytes = max_output_bytes

    @staticmethod
    def _contenido(resultado: Dict[str, Any]) -> Any:
        if "structuredContent" in resultado:
            return resultado["structuredContent"]
        contenido = resultado.get("content", [])
        textos = [item.get("text", "") for item in contenido
                  if isinstance(item, dict) and item.get("type") == "text"]
        if not textos:
            raise RuntimeError("Herramienta MCP sin contenido textual")
        texto = "\n".join(textos)
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            return {"results": [{"title": "Resultado MCP", "snippet": texto}]}

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        if max_results <= 0:
            return []
        with MCPStdioClient(
                self.command, timeout=self.timeout,
                max_output_bytes=self.max_output_bytes,
                allowed_tools={self.tool}) as cliente:
            resultado = cliente.call_tool(
                self.tool, {"query": query, "max_results": max_results})
        datos = self._contenido(resultado)
        if isinstance(datos, dict):
            datos = datos.get("results", [])
        if not isinstance(datos, list):
            raise RuntimeError("Resultado MCP no contiene una lista de fuentes")
        resultados = []
        descartados = 0
        for indice, hit in enumerate(datos, start=1):
            if not isinstance(hit, dict):
                descartados += 1
                continue
            url = hit.get("url") or f"mcp://resultado/{indice}"
            if not url.startswith(("mcp://", "document://")) and not _url_publica(url):
                descartados += 1
                continue
            snippet = hit.get("snippet", hit.get("content", ""))
            resultados.append({
                "title": hit.get("title", f"MCP {indice}"),
                "url": url,
                "snippet": snippet,
                "source": "mcp",
                "sha256": hit.get("sha256", ""),
                "location": hit.get("location", "MCP tool result"),
            })
            if len(resultados) >= max_results:
                break
        if datos and not resultados:
            raise RuntimeError(f"Todos los resultados MCP fueron inválidos ({descartados})")
        return resultados
