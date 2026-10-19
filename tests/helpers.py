"""Dobles de prueba compartidos (SIMULADOS): sin red, sin API keys, deterministas."""

import tempfile
from pathlib import Path
from types import SimpleNamespace


def crear_proyecto(caso, archivos):
    """Crea un proyecto temporal con los archivos indicados y lo limpia al final."""
    tmp = tempfile.TemporaryDirectory()
    caso.addCleanup(tmp.cleanup)
    raiz = Path(tmp.name)
    for nombre, contenido in archivos.items():
        ruta = raiz / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(contenido, encoding="utf-8")
    return raiz


class StubLLM:
    """LLM falso para tests (SIMULADO): responde según la función inyectada."""

    def __init__(self, responder):
        self._responder = responder
        self.prompts = []

    def generate(self, prompt, model=None, **kwargs):
        self.prompts.append(prompt)
        return self._responder(prompt)


class StubSearch:
    """Búsqueda falsa para tests (SIMULADA): devuelve resultados fijos."""

    def __init__(self, results):
        self._results = results
        self.queries = []

    def search(self, query, max_results=5):
        self.queries.append(query)
        return self._results[:max_results]


class FakeAPIError(Exception):
    """Error de API simulado con `status_code`, como las excepciones del SDK openai."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def ok_chat_response(content):
    """Respuesta simulada del endpoint de chat con la forma del SDK openai>=1.0."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def make_chat_client(outcomes):
    """Cliente OpenAI falso: cada llamada a `create` consume un outcome.

    Cada outcome es una respuesta (se devuelve) o una excepción (se eleva).
    Expone `.calls` con las llamadas realizadas.
    """
    calls = []

    def create(model, messages, **kwargs):
        calls.append({"model": model, "messages": messages, **kwargs})
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    client.calls = calls
    return client
