# deepseek-free-agent: proveedor opt-in sin API key

`DeepSeekFreeAgentLLM` conecta thinker con la API HTTP de
[`deepseek-free-agent`](https://github.com/readfor/deepseek-browser-agent).
La integración se comprobó contra el paquete npm **1.11.3**, publicado con
licencia MIT. Ese servicio automatiza Chromium para enviar los prompts a
`chat.deepseek.com`; **no ejecuta el modelo localmente**.

No se añade una dependencia Python ni se instala automáticamente software de
terceros. El servicio es opt-in y las pruebas del adaptador son offline.

## Instalación y arranque manual

Requisitos del paquete externo: Node.js 18 o superior, Chromium y una cuenta de
DeepSeek. Revisa antes su licencia, código y condiciones de uso.

```bash
npm install -g deepseek-free-agent@1.11.3
npx playwright install chromium
npx deepseek-free-agent
```

En la primera ejecución, inicia sesión manualmente en la ventana del navegador.
Después puedes arrancar el servicio con `npx deepseek-free-agent --headless`.
La API queda en `http://127.0.0.1:9527`.

## Autorización formal obligatoria

Seleccionar el proveedor no autoriza el egreso. Después de revisar esta guía y
aislar el servicio, cada invocación de la CLI debe incluir
`--authorize-deepseek-agent`. Sin esa confirmación, `generate()` eleva
`PermissionError` antes de crear una tarea HTTP.

## Uso en thinker

```bash
research "Compara RAG y MCP" \
  --provider deepseek-free-agent --search wikipedia \
  --authorize-deepseek-agent

# Endpoint y timeout explícitos; la URL debe ser loopback:
research "Resume la evidencia" \
  --provider deepseek-free-agent --search wikipedia \
  --deepseek-agent-url http://127.0.0.1:9527 \
  --deepseek-agent-timeout 300 --authorize-deepseek-agent
```

También se puede definir `DEEPSEEK_AGENT_URL`. Desde Python, la autorización es
igualmente explícita:

```python
from deep_research_system import ResearchOrchestrator
from llm_providers import DeepSeekFreeAgentLLM
from web_search import WikipediaSearchAPI

llm = DeepSeekFreeAgentLLM(authorized=True)
report, context = ResearchOrchestrator(
    llm, WikipediaSearchAPI()).research("Compara RAG y MCP")
```

El plugin se llama `deepseek_free_agent`. Su configuración distribuida tiene
`authorized: false`; solo después de la revisión humana se cambia a `true` en
`config/plugins.yaml` o se pasa ese parámetro mediante `PluginConfig`:

```bash
python -m plugins.cli load deepseek_free_agent
python -m plugins.cli set-active llm deepseek_free_agent
```

## Controles del adaptador

- Solo acepta URLs HTTP(S) loopback, sin credenciales, rutas, query ni fragmento.
- Exige autorización booleana explícita; valores de entorno o cadenas no la
  activan accidentalmente.
- No sigue redirecciones y no reintenta una tarea: un fallo es visible y no se
  duplica una operación que el agente ya pudiera haber ejecutado.
- Usa timeout de conexión/lectura, cierra la respuesta y limita el cuerpo a 1 MB.
- Exige JSON con `status: "success"` y una respuesta textual no vacía.
- Envía `newChat: true` para evitar memoria entre llamadas y antepone una
  instrucción de responder solo texto, sin herramientas, archivos, comandos ni URLs.
- La caché por instancia evita repetir una tarea idéntica ya completada.
- `--max-llm-calls` sigue disponible como presupuesto opcional de thinker.

## Capas y patrones de diseño

La especificación aplica **defensa en profundidad**, no una única comprobación:

1. **Requisito y autorización:** selección opt-in más consentimiento explícito.
2. **Frontera de egreso:** URL loopback validada y política `public` obligatoria.
3. **Contención:** instrucción de solo lectura y servicio externo aislado por el
   usuario; thinker no le concede acceso al repositorio.
4. **Transporte:** timeout, sin redirecciones ni reintentos, cierre y tamaño máximo.
5. **Salida no confiable:** `answer` se devuelve como texto, nunca como comando,
   herramienta, código o prueba de verdad.
6. **Evidencia:** el pipeline delimita fuentes no confiables, audita citas de forma
   léxica y registra calidad de fuentes; una respuesta convincente no basta.
7. **Cambios:** contratos offline, Ruff, preflight, secretos, holdout, auditoría de
   diff y revisión humana antes de aceptar cambios.

Los patrones concretos son *Adapter* para aislar al tercero, *fail-fast* para URL,
autorización y contrato JSON, operación sin reintento para evitar duplicar efectos,
y *explicit capability* para el permiso de egreso. Los requisitos medibles están en
`docs/REQUISITOS-DEEPSEEK-FREE-AGENT.md`; los gates generales y sus límites están en
`docs/SALVAGUARDAS.md`.

## Límites de seguridad y privacidad

La instrucción de solo lectura reduce el riesgo, pero **no es un sandbox ni una
garantía**: el paquete externo incluye herramientas para escribir/borrar archivos
y ejecutar comandos. Su propia documentación contempla `force: true` para eludir
validaciones. Ejecuta el servicio en un espacio de trabajo aislado, sin secretos
ni permisos innecesarios, y revisa sus registros. No lo uses en el árbol real si
no aceptas ese riesgo.

Ninguna capa puede demostrar que un LLM «no miente». Thinker mitiga alucinación,
engaño e inyección tratando su salida como datos no confiables y contrastando
citas con las fuentes recuperadas. Esa comprobación es léxica, no una prueba de
verdad ni de respaldo semántico. La segunda pasada CoVe con el mismo proveedor no
es independiente; para decisiones importantes hacen falta fuentes primarias y
revisión humana. Nunca se ejecuta `answer` ni se interpreta como una herramienta.

El servidor 1.11.3 escucha sin especificar host y su API no tiene autenticación.
Restringir el cliente a loopback no impide que otra máquina acceda al servicio:
no expongas el puerto 9527 y aplica el cortafuegos correspondiente.

El proveedor solo es compatible con `--privacy public`. `local-only` y
`private-documents` lo rechazan porque el prompt sale del equipo hacia DeepSeek,
aunque la API intermedia sea localhost. No envíes claves, datos personales ni
documentos confidenciales.

Automatizar la interfaz web puede estar sujeto a condiciones del servicio y a
cambios de sus selectores. Requiere sesión y puede dejar de funcionar o provocar
restricciones de cuenta.

## «Gratuito» no significa «ilimitado»

Thinker no cobra ni añade una cuota propia al conector y el plugin estima coste
directo 0. No hay fallback a DeepSeek API, OpenRouter ni otro proveedor de pago:
si el servicio gratuito falla, la llamada eleva el error. Sin embargo, no se
promete disponibilidad ilimitada ni coste cero permanente del tercero: DeepSeek
puede imponer límites de cuenta, tasa, sesión o servicio; la cola externa procesa
tareas en serie y el hardware/navegador también tiene límites. Los fallos se
reportan, no se sustituyen silenciosamente por un mock.

## Verificación

`tests/test_deepseek_free_agent.py` comprueba el contrato HTTP y los controles
con respuestas dobles, sin red ni cuenta. La disponibilidad y calidad del modelo
real requieren una prueba opt-in con el servicio configurado; no se deducen de
los tests offline.

Fuentes externas consultadas: [README 1.11.3](https://unpkg.com/deepseek-free-agent@1.11.3/README.md),
[servidor HTTP 1.11.3](https://unpkg.com/deepseek-free-agent@1.11.3/src/server.js)
y [guía de seguridad](https://unpkg.com/deepseek-free-agent@1.11.3/docs/SECURITY_SOLUTION.md).
