# Herramientas de código abierto para investigación profunda con LLM: guía actualizada a octubre de 2026

## 1. Introducción

La investigación profunda asistida por modelos de lenguaje (LLM) ha evolucionado más allá de los sistemas que simplemente responden preguntas a partir de una búsqueda web. Los frameworks actuales pueden descomponer problemas complejos, ejecutar búsquedas iterativas, leer documentos, contrastar evidencias, identificar contradicciones y producir informes estructurados con referencias a sus fuentes.

En paralelo, el ecosistema de código abierto ofrece alternativas que permiten construir sistemas de investigación más transparentes, personalizables y, en muchos casos, ejecutables localmente. Algunas pueden funcionar con modelos de pesos abiertos y motores de búsqueda gratuitos; otras combinan modelos locales con API comerciales para mejorar la calidad de la investigación.

Sin embargo, es importante distinguir entre tres características que no son equivalentes:

- **Código abierto:** el código puede inspeccionarse, modificarse y, según su licencia, redistribuirse.
- **Modelos de pesos abiertos:** los pesos del modelo están disponibles, pero su licencia y sus restricciones pueden variar.
- **Ejecución gratuita y local:** el sistema puede utilizarse sin pagar por inferencia a un proveedor externo, aunque sigue requiriendo hardware, electricidad, mantenimiento y, en ocasiones, servicios adicionales.

Esta guía presenta una selección de herramientas y proyectos relevantes para construir sistemas de investigación profunda, desde agentes sencillos hasta arquitecturas multiagente y modelos especializados. Se prioriza la utilidad práctica, la trazabilidad de las fuentes, la flexibilidad de los modelos y la posibilidad de controlar los costes.

**Nota sobre la verificación:** la fecha de referencia es octubre de 2026. La actividad de un repositorio, sus versiones, licencias, métricas de adopción y requisitos de ejecución pueden cambiar rápidamente. Las cifras históricas y las afirmaciones de rendimiento deben comprobarse en las fuentes oficiales antes de utilizarlas como datos definitivos. No debe interpretarse la inclusión de un proyecto como confirmación independiente de todas sus características o de su estado actual.

## 2. Comparativa de herramientas

La siguiente tabla resume las principales opciones que conviene evaluar. Las instalaciones y los requisitos indicados son orientativos cuando dependen de la versión, del modelo o de la configuración elegida.

| Herramienta | Enfoque principal | Modelos y servicios | Requisitos y consideraciones |
| --- | --- | --- | --- |
| **DeepDive** | Investigación web con énfasis en la verificación de afirmaciones y citas | Se presenta como una opción orientada a modelos locales mediante Ollama | Python y Ollama, si la versión elegida mantiene esa integración. Verificar paquete, CLI y licencia |
| **Passive Workers** | Investigación paralela mediante analistas independientes y síntesis editorial | Modelos locales a través de Ollama | Python y recursos suficientes para ejecutar varios modelos; comprobar compatibilidad y consumo de memoria |
| **deepthink-js** | Orquestación de razonamiento, búsqueda y verificación en un pipeline de varios pasos | Se describe como compatible con distintos proveedores y entornos locales | Node.js; verificar las integraciones, los límites de ejecución y la disponibilidad del paquete |
| **Noesium** | Framework de agentes cognitivos con descomposición de objetivos, memoria y herramientas | Se anuncia soporte para varios proveedores y modelos locales | Python; revisar la documentación y el catálogo de herramientas de la versión instalada |
| **Fathom-DeepResearch** | Investigación con modelos especializados en recuperación de información y síntesis | Modelos propios de pesos abiertos, según la descripción del proyecto | GPU recomendable; comprobar la licencia del código y de cada modelo por separado |
| **Cognitive Kernel-Pro** | Arquitectura modular de agentes y herramientas para investigación | Modelos abiertos y herramientas de búsqueda configurables, según su implementación | Revisar la procedencia del repositorio, los requisitos y los riesgos de ejecución de código |
| **WebThinker** | Intercalación de razonamiento, búsqueda web y redacción de informes | Modelos de razonamiento compatibles con la arquitectura del proyecto | La ejecución de modelos grandes puede requerir GPU y memoria considerable |
| **ManuSearch** | Investigación multiagente con planificación, búsqueda y lectura estructurada de páginas | Modelos servidos localmente y posibles servicios externos de búsqueda | Revisar los requisitos de inferencia, las claves API y la configuración de vLLM |
| **SPIRAL** | Planificación y evaluación de acciones mediante agentes especializados y búsqueda de soluciones | Modelos compatibles con su implementación experimental | Puede requerir configuración de investigación, dependencias específicas y aceleración por GPU |
| **Zeline** | Agentes con navegación, ejecución de herramientas y delegación de tareas | Ollama y endpoints compatibles, según la versión | Verificar el estado del proyecto, los permisos del navegador y las funciones disponibles |
| **Open Deep Research** | Agente configurable para investigar y sintetizar información mediante un flujo estructurado | Diferentes proveedores de modelos y herramientas de búsqueda | Python y el stack de LangGraph; algunas configuraciones necesitan servicios externos |
| **GPT-Researcher** | Investigación autónoma y generación de informes con múltiples fuentes | Proveedores comerciales y configuraciones alternativas | Python o Docker; la experiencia gratuita depende de los modelos y servicios seleccionados |

### Cómo interpretar la comparativa

No todas las herramientas persiguen el mismo objetivo. Algunas priorizan la calidad de las citas; otras, la autonomía del agente, la experimentación con modelos de razonamiento o la integración con aplicaciones existentes.

Por tanto, no existe una única clasificación válida para todos los escenarios. Para elegir correctamente conviene evaluar cinco dimensiones:

1. **Calidad de la evidencia:** si el sistema recupera documentos pertinentes y vincula las afirmaciones con pasajes concretos.
2. **Autonomía:** si puede identificar lagunas de información y lanzar búsquedas adicionales sin intervención constante.
3. **Control de costes:** si permite utilizar modelos locales y buscadores autoalojados.
4. **Reproducibilidad:** si conserva las consultas, las fuentes, las decisiones y los resultados intermedios.
5. **Seguridad y mantenimiento:** si dispone de dependencias actualizadas, licencias claras y controles para ejecutar herramientas externas.

## 3. Recomendaciones según el objetivo

### 3.1. DeepDive — verificación de citas y control local

**Mejor punto de partida.**

Adecuado para generar informes con afirmaciones vinculadas a extractos recuperados de las fuentes. Utiliza Ollama de forma predeterminada y dispone de una opción de funcionamiento sin conexiones externas mediante su modo offline y corpus local. La validación del extracto demuestra que el texto aparece en la fuente recuperada, no que la fuente sea necesariamente verdadera.

- Documentación y guía de inicio: [openintelligence-labs.github.io/deepdive-docs](https://openintelligence-labs.github.io/deepdive-docs/)

### 3.2. Passive Workers — análisis independiente en paralelo

Interesante para comparar las conclusiones de varios modelos locales y conservar los desacuerdos en el informe final. También contempla la investigación sobre documentos privados y una interfaz web local. Su ejecución requiere más recursos que un único agente porque puede utilizar varios modelos en una misma investigación.

- PyPI: [pypi.org/project/passiveworkers](https://pypi.org/project/passiveworkers/)
- GitHub: [github.com/wikithoughts/passiveworkers](https://github.com/wikithoughts/passiveworkers)

### 3.3. Open Deep Research — personalización del flujo de trabajo

Es una buena referencia para desarrolladores que quieran modificar la planificación, la búsqueda, la compresión de evidencias y la redacción final. Admite distintos proveedores y herramientas de búsqueda, además de integración con MCP.

**Advertencia importante:** el repositorio original de LangChain fue archivado el 21 de agosto de 2026. Sigue siendo útil para estudiar, ejecutar o adaptar el código, pero ya no debe tratarse como un proyecto con mantenimiento activo en ese repositorio.

- Código: [github.com/langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research)

### 3.4. CognitiveKernel-Pro — experimentación con agentes

Resulta relevante para estudiar arquitecturas de investigación profunda y entrenamiento de agentes con herramientas. Su repositorio contempla el uso de herramientas gratuitas y la sustitución de Google Search por DuckDuckGo. Antes de desplegarlo, hay que revisar sus dependencias y aislar cualquier ejecución de código generado.

- Código: [github.com/Tencent/CognitiveKernel-Pro](https://github.com/Tencent/CognitiveKernel-Pro)

### 3.5. Noesium — construcción de agentes propios

Una opción para quienes necesitan algo más que un investigador web preconfigurado. Ofrece arquitectura basada en eventos, coordinación de subagentes, memoria y múltiples herramientas. Es especialmente útil si se desea desarrollar un sistema de investigación como parte de una aplicación más amplia.

- Instalación y documentación: [pypi.org/project/noesium](https://pypi.org/project/noesium/)

### 3.6. GPT-Researcher — generación de informes extensos

Alternativa conocida para automatizar investigaciones web y personalizar los informes generados. Conviene revisar qué versión del repositorio se está utilizando, qué proveedores admite y cuánto cuesta la búsqueda y la inferencia con la configuración seleccionada. El código abierto no implica que todos los servicios asociados sean gratuitos.

- Código: [github.com/assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher)

### 3.7. Proyectos de investigación avanzada

WebThinker, ManuSearch, SPIRAL y Fathom-DeepResearch merecen atención si el objetivo no es simplemente utilizar un agente, sino estudiar nuevas estrategias de razonamiento, recuperación y planificación.

No obstante, hay que diferenciar un artículo científico de una herramienta lista para producción. La publicación de resultados en un benchmark no garantiza que el repositorio sea fácil de instalar, que los pesos estén disponibles, que las licencias permitan cualquier uso o que el rendimiento se reproduce en un ordenador personal.

Para estos proyectos, la evaluación debería incluir el artículo original, el repositorio oficial, los archivos de modelos disponibles y las instrucciones de reproducción de los experimentos. No conviene atribuirles una superioridad general frente a sistemas propietarios basándose únicamente en una métrica o un conjunto de tareas.

## 4. Inicio rápido: ejecutar DeepDive localmente

DeepDive es una opción razonable para comenzar porque dispone de documentación específica, un paquete instalable y una configuración predeterminada con Ollama. Los requisitos publicados incluyen Python 3.12 o posterior.

### Paso 1. Instalar Ollama y descargar un modelo

Instala Ollama desde su [sitio oficial](https://ollama.com/). Después, descarga un modelo compatible con el uso de herramientas y sigue la guía de DeepDive.

```bash
ollama pull llama3.2
```

La disponibilidad del modelo no garantiza por sí sola que vaya a funcionar correctamente en todas las tareas de investigación. La capacidad de seguir instrucciones, utilizar herramientas y producir referencias fiables importa tanto como el tamaño del modelo.

### Paso 2. Instalar DeepDive

En un entorno virtual de Python 3.12 o posterior:

```bash
python -m venv .venv
```

Activa el entorno virtual y ejecuta:

```bash
python -m pip install --upgrade pip
pip install deepdive-research
```

En macOS o Linux, la activación habitual es:

```bash
source .venv/bin/activate
```

En Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Comprueba que el comando esté disponible:

```bash
deepdive --help
```

### Paso 3. Ejecutar una investigación

```bash
deepdive research \
  "¿Cuál es el estado actual de la fusión nuclear?" \
  -o informe.md
```

La sintaxis exacta de los argumentos debe contrastarse con la versión instalada mediante `deepdive --help`. La documentación oficial es la referencia para los requisitos, los modos de ejecución y los formatos de exportación.

### Paso 4. Auditar el resultado

No te limites a leer las conclusiones. Comprueba también:

- Que las fuentes existan y sean pertinentes para la pregunta.
- Que cada cita respalde realmente la afirmación a la que está asociada.
- Que las cifras, fechas y nombres propios coincidan con los documentos originales.
- Que se incluyan fuentes primarias cuando estén disponibles.
- Que el informe distinga entre hechos documentados, inferencias e incertidumbres.

El objetivo es obtener un informe verificable, no simplemente un texto que parezca convincente.

## 5. Cómo funciona la arquitectura de investigación profunda

La diferencia entre un chatbot convencional y un sistema de investigación profunda no reside únicamente en el modelo de lenguaje. Está en el proceso que organiza la búsqueda, la evaluación de las fuentes y la elaboración del informe.

1. **Pregunta de investigación.** Objetivo, alcance, restricciones y criterios de calidad.
2. **Planificación y descomposición.** Subpreguntas, hipótesis y lagunas de información.
3. **Recuperación de información.**
   - **3A. Búsqueda web.** Motores de búsqueda, APIs y rastreo de páginas.
   - **3B. Documentos propios.** PDF, artículos, bases documentales y RAG.
4. **Evaluación y contraste de evidencias.** Credibilidad, corroboración, contradicciones y citas.
5. **Revisión iterativa.** Nuevas búsquedas cuando faltan datos o aparecen conflictos.
6. **Informe final.** Síntesis, referencias, limitaciones y conclusiones trazables.

Esta arquitectura es una referencia conceptual, no una descripción idéntica de todos los frameworks. Algunos ejecutan las etapas secuencialmente; otros utilizan varios agentes en paralelo o permiten que un planificador decida cuándo buscar más información.

### Técnicas que mejoran los resultados

- **Planificación iterativa:** las consultas se refinan a medida que aparecen nuevas evidencias.
- **Recuperación híbrida:** combina búsqueda semántica con coincidencias léxicas, por ejemplo mediante BM25.
- **Diversidad de fuentes:** evita que el informe dependa exclusivamente de páginas que repiten una misma noticia.
- **Verificación de afirmaciones:** comprueba si los documentos respaldan las conclusiones concretas.
- **Autocrítica controlada:** identifica lagunas, contradicciones y errores antes de redactar la versión definitiva.
- **Evaluación reproducible:** conserva las consultas, las fuentes, las versiones de los modelos y los parámetros relevantes.

La autocrítica no constituye una garantía de verdad: un modelo puede revisar su respuesta y seguir equivocándose. Siempre que sea posible, conviente contrastar las afirmaciones con evidencia externa independiente.

## 6. Requisitos de hardware y costes

El hardware necesario depende del modelo, su cuantización, el contexto utilizado, la concurrencia y la velocidad de generación deseada. Las siguientes cifras son orientativas para modelos locales cuantizados, no requisitos oficiales de cada proyecto.

| Tamaño del modelo | Memoria aproximada para los pesos | Perfil de uso |
| --- | --- | --- |
| 3B–4B | 2–4 GB | Pruebas y tareas sencillas |
| 7B–8B | 4–6 GB | Investigación básica y agentes ligeros |
| 12B–14B | 7–10 GB | Síntesis y análisis más exigentes |
| 30B–32B | 18–24 GB | Razonamiento avanzado, según el modelo |
| 70B | 40–48 GB o más | Informes complejos y mayor capacidad de síntesis |

A estas cifras hay que sumar la memoria para el contexto, la caché, el runtime y el resto de las aplicaciones. La memoria necesaria puede aumentar considerablemente con contextos largos y ejecuciones simultáneas.

### Qué elegir según el equipo

- **Portátil sin GPU dedicada.** Comienza con un modelo pequeño y un solo agente. Es viable realizar investigaciones moderadas, aunque la inferencia puede ser lenta y las ejecuciones prolongadas resultar poco prácticas.
- **Equipo con GPU de 12–16 GB de VRAM.** Permite experimentar con modelos cuantizados medianos, recuperación documental y agentes con varias herramientas. Para modelos grandes puede ser necesario reducir el contexto o repartir la carga entre CPU y GPU.
- **Mac con Apple Silicon.** La memoria unificada puede ser útil para modelos locales. Hay que considerar la memoria disponible para el sistema completo y no confundir la memoria total del dispositivo con la memoria libre para inferencia.

### Costes que suelen pasar desapercibidos

Aunque el código y los modelos sean gratuitos, una investigación profunda puede consumir recursos por cuatro vías:

1. **Inferencia:** varias llamadas al LLM por cada pregunta y por cada agente.
2. **Búsqueda y extracción:** límites de peticiones, cuotas de API y restricciones de acceso a sitios web.
3. **Infraestructura:** GPU, servidor, almacenamiento y electricidad.
4. **Mantenimiento:** actualización de dependencias, reparación de integraciones y controles de seguridad.

Para mantener el coste bajo, empieza con un modelo local, limita el número de iteraciones, reutiliza documentos ya recuperados y reserva los modelos más grandes para las partes que realmente necesitan razonamiento adicional.

## 7. Privacidad, seguridad y limitaciones

La ejecución local reduce la exposición de los datos al proveedor de inferencia, pero no garantiza que todo el sistema funcione sin conexión.

Un agente puede enviar consultas a motores de búsqueda externos, descargar páginas, consultar APIs o utilizar servicios de telemetría. Para trabajar con documentación confidencial, hay que revisar cada una de estas rutas de datos.

Antes de ejecutar cualquier framework:

- Verifica la licencia del código, de los modelos y de los datasets.
- Utiliza un entorno virtual o un contenedor aislado.
- No proporciones credenciales personales al código de terceros.
- Limita los permisos de archivos, red y ejecución de comandos.
- Inspecciona el código que ejecuta scripts generados por un LLM.
- Trata las páginas web recuperadas como contenido no confiable: pueden incluir instrucciones maliciosas destinadas a manipular al agente.
- Conserva registros suficientes para reconstruir cómo se produjo el informe.

Una consideración adicional es la diferencia entre citar una página y verificar una afirmación. Una URL puede ser válida y, aun así, no respaldar el texto citado. Incluso una cita que reproduce correctamente un pasaje puede proceder de una fuente desactualizada, sesgada o incorrecta.

## 8. Fuentes oficiales para comprobar versiones y documentación

Los siguientes enlaces permiten contrastar las instalaciones, licencias y capacidades antes de adoptar una herramienta.

| Proyecto | Fuente principal |
| --- | --- |
| DeepDive | [Documentación](https://openintelligence-labs.github.io/deepdive-docs/) · [Versiones](https://github.com/openintelligence-labs/deepdive/releases) |
| Passive Workers | [PyPI](https://pypi.org/project/passiveworkers/) · [GitHub](https://github.com/wikithoughts/passiveworkers) |
| deepthink-js | [npm](https://www.npmjs.com/package/deepthink-js) · [GitHub](https://github.com/crazystuffxyz/deepthink-js) |
| Noesium | [PyPI](https://pypi.org/project/noesium/) |
| Fathom-DeepResearch | [Búsqueda del repositorio y publicaciones](https://github.com/search?q=Fathom-DeepResearch&type=repositories) |
| CognitiveKernel-Pro | [GitHub](https://github.com/Tencent/CognitiveKernel-Pro) |
| WebThinker | [Búsqueda de publicaciones y código](https://github.com/search?q=WebThinker&type=repositories) |
| ManuSearch | [Búsqueda del proyecto](https://github.com/search?q=ManuSearch&type=repositories) |
| SPIRAL | [Búsqueda del proyecto](https://github.com/search?q=SPIRAL+IBM+LLM&type=repositories) |
| Zeline | [GitHub](https://github.com/Mftrferdinand/Zeline) |
| Open Deep Research | [GitHub](https://github.com/langchain-ai/open_deep_research) |
| GPT-Researcher | [GitHub](https://github.com/assafelovic/gpt-researcher) |

Las páginas de búsqueda de GitHub no sustituyen a la documentación oficial de un proyecto: sirven para localizar el repositorio correcto cuando el nombre no identifica inequívocamente una implementación.

## 9. Conclusiones

El ecosistema de investigación profunda con LLM ofrece varias rutas viables, pero elegir bien exige separar tres objetivos: producir informes fiables, ejecutar modelos con autonomía y controlar la infraestructura.

- **Para comenzar con un flujo local y citas rastreables:** DeepDive.
- **Para comparar resultados de modelos locales:** Passive Workers.
- **Para desarrollar un agente configurable:** Open Deep Research, teniendo en cuenta que su repositorio original está archivado.
- **Para construir sistemas cognitivos con herramientas y subagentes:** Noesium.
- **Para investigar arquitecturas experimentales:** CognitiveKernel-Pro y los proyectos académicos, tras verificar sus implementaciones y condiciones de reproducción.
- **Para automatizar informes extensos con una infraestructura flexible:** GPT-Researcher.

La recomendación general es comenzar con un único agente, un modelo compatible con las herramientas y una estrategia explícita de verificación. Después, incorpora paralelización, memoria, RAG y bucles de crítica únicamente cuando resuelvan una limitación identificada.

La calidad de un sistema de investigación profunda no se mide por cuántos agentes utiliza, cuántas páginas consulta o cuánto texto produce. Se mide por su capacidad para responder la pregunta con evidencia suficiente, reconocer lo que no sabe y permitir que otra persona compruebe sus conclusiones.

**Criterio final:** prioriza la trazabilidad, la reproducibilidad, la seguridad y el coste total de ejecución por encima de las afirmaciones promocionales o de las posiciones aisladas en benchmarks.