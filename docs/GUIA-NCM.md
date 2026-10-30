# Guía de librerías y repositorios open source para NCM en Python

**Incorporado:** 2026-10-26. **Alcance:** documento de referencia externo,
independiente del pipeline de thinker. **Método:** cada repositorio, paper y
paquete citado se comprobó contra su fuente primaria (API de GitHub, API de
arXiv, Crossref, PyPI o el propio repositorio) el 2026-10-26; el resultado
individual está en el **anexo A** y las correcciones aplicadas al texto se
marcan donde corresponden. Lo que no se pudo verificar se declara como tal; no
se completa con memoria.

**Cómo usar este documento:** las cuatro acepciones de NCM son independientes.
Elija la sección por el **problema** (generación de texto, mapas cognitivos,
indeterminación o clasificación incremental), no por el acrónimo. El anexo B
explica qué encaje tiene —y qué no— en thinker.

## 1. Resumen ejecutivo

El acrónimo **NCM** es ambiguo. En el ecosistema Python conviven cuatro
conceptos distintos, con madurez open source muy diferente:

| Concepto de NCM | Librería / Repositorio principal | Licencia | Madurez open source | Caso de uso típico |
| :--- | :--- | :--- | :--- | :--- |
| **Next-Concept Modeling** | `HazyResearch/ncm` (GitHub) | MIT | Release de investigación (octubre 2026), no empaquetado en PyPI | Generación de texto paralela coarse-to-fine |
| **Neural Cognitive Maps** | Repositorios específicos (ver §3) | Varía (MIT, CC BY 4.0, etc.) | Implementaciones para papers concretos | Neurociencia computacional, planificación, memoria |
| **Neutrosophic Cognitive Maps** | `NCMPy` (software del paper, sin paquete PyPI) | Open source (paper asociado) | Librería dedicada con paper publicado | Modelado de indeterminación en sistemas complejos |
| **Nearest Class Mean** | **`Avalanche`** y **`CapyMOA`** | MIT / BSD-3-Clause | Integrado en librerías de *Continual Learning* de uso extendido | Clasificación incremental, aprendizaje continuo |

Recomendación general: para **aprendizaje continuo**, `Avalanche` es la opción
más madura y mantenida; para **generación de texto rápida**, `HazyResearch/ncm`
es el punto de partida obligado, con la advertencia de que es un release de
investigación; para **mapas cognitivos**, las opciones son específicas y dependen
del enfoque (neural o neutrosófico) que se quiera explorar.

## 2. Next-Concept Modeling (NCM)

### 2.1. Repositorio oficial: `HazyResearch/ncm`

Es la implementación de referencia de **Hazy Research (Stanford)**, publicada
como paper en arXiv el 2026-10-09 y como repositorio en GitHub el 2026-10-11.
El repositorio está bajo **licencia MIT**.

**Instalación:**

```bash
git clone https://github.com/HazyResearch/ncm.git
cd ncm
pip install -r requirements.txt
```

**Qué incluye:**

- Código del marco **coarse-to-fine** que utiliza un **VQ-VAE multiescala**
  (multiscale residual VQ tokenizer) para representar secuencias como una
  jerarquía de códigos discretos, y un **transformer** que predice esa jerarquía
  nivel a nivel, generando todos los códigos de un nivel en paralelo.
- La generación requiere **una evaluación forward por nivel**, lo que reduce el
  número de pasos secuenciales en comparación con los modelos autorregresivos y
  de difusión.

**Rendimiento reportado en el paper (arXiv:2610.14162), según su abstract:**

- En **LM1B**, NCM logra mejor perplejidad generativa que el mejor baseline de
  difusión, siendo **21× más rápido**.
- En **OpenWebText**, es competitivo con el mejor DLM, siendo **10× más rápido**.
- En **XSum**, iguala el ROUGE-L del mejor DLM, siendo **31× más rápido**.
- En **Sudoku**, supera a los baselines autorregresivos y de difusión en todos
  los niveles de dificultad, usando menos evaluaciones de función (NFE).

### 2.2. Checkpoints pre-entrenados: `hazyresearch/ncm-checkpoints`

En Hugging Face se han publicado los **tokenizers** y **generadores** entrenados,
junto con archivos `config.yaml` que describen la arquitectura y los parámetros
de muestreo.

**Modelos disponibles** (verificados en la model card):

- **XSum** (sumarización)
- **WMT14 De–En** (traducción alemán-inglés)
- **Sudoku** (fácil, medio, difícil)
- **LM1B** (One Billion Word, en tamaños small/medium/large con tokenizer
  compartido)
- **TinyStories**
- **OpenWebText**

Cada modelo consta de un **tokenizer congelado** (`tokenizer.pt`) y un
**generador de siguiente concepto** (`generator.pt`), lo que permite experimentar
sin reentrenar desde cero. El dataset tokenizado asociado está en
`hazyresearch/ncm-datasets`.

**Enlaces útiles:**

- Blog oficial: `hazyresearch.stanford.edu/blog/2026-10-12-ncm`
- Paper: arXiv:2610.14162
- Hugging Face collection: `huggingface.co/collections/hazyresearch/ncm`

### 2.3. Consideraciones prácticas

- **Requiere Python 3.10+** y un entorno PyTorch con CUDA para un rendimiento
  óptimo (así lo indica el README).
- No está empaquetado en PyPI; hay que clonar el repositorio e instalar
  dependencias manualmente.
- Es un **release de investigación**: la API puede cambiar y no hay garantías de
  soporte a largo plazo.
- Ideal para **experimentación** con generación de texto no autorregresiva y para
  reproducir los resultados del paper.

## 3. Mapas Cognitivos Neuronales (Neural Cognitive Maps)

No existe una librería única y estandarizada con el nombre "Neural Cognitive
Maps". El concepto es un **área de investigación activa** que se implementa en
repositorios específicos para cada estudio. Los repositorios siguientes se
comprobaron individualmente; los que no existen en la ruta indicada se declaran
como no verificables.

### 3.1. `sgalella/CognitiveMaps`

**No verificable (2026-10-26):** la ruta `github.com/sgalella/CognitiveMaps`
devuelve **HTTP 404**. No se incluye como recomendación hasta disponer de una URL
válida; la descripción de partida (scripts para analizar mapas cognitivos con
fMRI y modelos de deep learning) no se pudo contrastar con el repositorio.

### 3.2. `POWER-KI/GCML-PWK-Neuromorfico-04` (Generative Cognitive Map Learner)

Implementación nativa en **POWER-KI** del **Generative Cognitive Map Learner
(GCML)**, un marco para la planificación y la imaginación dirigida a objetivos
mediante el muestreo neural de mapas cognitivos.

**Características destacadas:**

- Basado en el paper **"Neural sampling from cognitive maps enables
  goal-directed imagination and planning"** (Lin et al., *Nature Machine
  Intelligence*, 2026; DOI `10.1038/s42256-026-01254-4`).
- Utiliza **reglas sinápticas locales** y **no requiere backpropagation ni redes
  profundas**, lo que lo hace adecuado para hardware neuromórfico y de bajo
  consumo energético.
- Implementa tres dominios: **espacial** (laberinto 2D), **grafos abstractos**
  (32 nodos) y **compositivo** (tiling con 8 bloques y 664 acciones).
- **Licencia del repositorio:** MIT (comprobada en GitHub). El paper se publica
  en abierto con **CC BY 4.0**; son licencias distintas y conviene no
  confundirlas.
- Código original de los autores: `github.com/LH-cbicr/GCML` (MIT).

### 3.3. `tristanstoeber/gradCSCG`

Contiene la implementación del pipeline **gradCSCG** (Differentiable
Clone-Structured Causal Graphs), que reformula el algoritmo CSCG como un
**módulo completamente diferenciable** y lo acopla a un **VQ-VAE** como
front-end perceptual para el aprendizaje de mapas cognitivos a partir de
secuencias de imágenes.

**Detalles técnicos:**

- El CSCG (Clone-Structured Causal Graph) es un modelo normativo del hipocampo
  que muestra cómo un mapa cognitivo interpretable puede aprenderse a partir de
  experiencias.
- gradCSCG elimina la barrera de no-diferenciabilidad del CSCG original,
  permitiendo el aprendizaje **end-to-end** desde imágenes crudas.
- Referencia: arXiv:2607.12382; licencia MIT.

### 3.4. Otras implementaciones relacionadas

- **`yadgar/cognitive_map.py`**: **no verificable (2026-10-26)**: la ruta
  `github.com/yadgar/cognitive_map` devuelve **HTTP 404**. La descripción de
  partida (Successor Representation para recuperación de memoria como navegación
  por el espacio de conceptos, basada en Stachenfeld et al., *Nature
  Neuroscience*, 2017) no se pudo contrastar con el repositorio.
- **`arminbazza/LinearRL`**: implementación en Python del modelo de **Linear
  Reinforcement Learning** de Piray and Daw (2021), relacionado con la
  representación de mapas cognitivos en RL. (La ruta `ArminBaz/LinearRL` no
  resuelve; el usuario correcto es `arminbazza`.)
- **`wsojka00/graph_navigation`**: repositorio donde agentes de RL resuelven
  laberintos y representan el proceso de aprendizaje como aprendizaje de grafos.
- **`neuralml/hcRL`**: código de simulación para el paper "Hippocampal networks
  support reinforcement learning in partially observable environments", usando
  PyTorch (MIT).

**Nota importante:** ninguno de estos repositorios es una librería
general-purpose. Son implementaciones específicas de papers. Para una base
sólida de mapas cognitivos neuronales probablemente haya que combinar conceptos
de varios de ellos o adaptar el código al problema propio.

## 4. Mapas Cognitivos Neutrosóficos (Neutrosophic Cognitive Maps)

### 4.1. `NCMPy`: el paquete dedicado

`NCMPy` es un **paquete de Python creado específicamente** para la construcción,
análisis y visualización de Mapas Cognitivos Neutrosóficos. Fue presentado en el
paper **"NCMPy: A Modelling Software for Neutrosophic Cognitive Maps based on
Python Package"** (Kandasamy et al., *Neutrosophic Systems with Applications*,
Vol. 13, 2024; DOI `10.61356/j.nswa.2024.114`).

**Funcionalidades principales:**

- Modelado de la **indeterminación** (el concepto 'I'), que es la diferencia clave
  de los NCMs frente a los Fuzzy Cognitive Maps (FCMs).
- Visualización de los NCMs como **grafos dirigidos con signo** (directed signed
  neutrosophic graphs).
- Construcción, análisis y visualización de NCMs de extremo a extremo.
- Incluye un caso de estudio de ejemplo.

**Licencia y disponibilidad:** el paper está publicado en abierto y el paquete se
distribuye como software de modelado. **No está en PyPI con ese nombre**: en
PyPI, `ncmpy` es un cliente de música para la terminal. La referencia canónica
para obtenerlo es el paper.

### 4.2. Advertencia sobre el nombre

**`ncmpy` en PyPI es un cliente de música para la terminal** (versión 1.5.7 en la
comprobación del 2026-10-26), no relacionado con la IA. Para encontrar el paquete
correcto, hay que buscar por el paper asociado o por el nombre completo
**"NCMPy: A Modelling Software for Neutrosophic Cognitive Maps based on Python
Package"**.

### 4.3. Ecosistema más amplio de lógica neutrosófica

Si el interés va más allá de los mapas cognitivos y se quiere trabajar con
**conjuntos y lógica neutrosófica** en Python, hay varias librerías open source
en PyPI (versiones comprobadas el 2026-10-26):

| Librería | Descripción | Instalación |
| :--- | :--- | :--- |
| **`neutrosophics`** (0.0.4) | Operaciones aritméticas, algebraicas, multiplicación escalar y operaciones lógicas sobre conjuntos neutrosóficos | `pip install neutrosophics` |
| **`rnel`** (0.4.0) | Lógica evidencial neutrosófica refinada (Refined Neutrosophic Evidential Logic), con módulos para razonamiento credal, existencial y clustering | `pip install rnel` |
| **`adnus`** (0.2.4) | Implementación de sistemas numéricos avanzados, incluidos **números neutrosóficos** con extensiones complejas y bicomplejas; licencia **AGPL-3.0** | `pip install adnus` |
| **`thirdanswer`** (0.3.0) | Toolkit de lógica neutrosófica para evaluar incertidumbre en IA con tres dimensiones: T (Truth), I (Indeterminacy), F (Falsity); licencia **MIT** | `pip install thirdanswer` |

### 4.4. Relación con Fuzzy Cognitive Maps: `FCMpy`

Los **Fuzzy Cognitive Maps (FCMs)** son el precursor directo de los NCMs. Si el
trabajo no requiere modelar indeterminación explícita, **`FCMpy`** es una
librería open source madura y bien documentada para construir y analizar FCMs en
Python.

**Funcionalidades de `FCMpy`:**

- Generación automática de pesos causales a partir de **datos cualitativos**
  mediante lógica difusa.
- Optimización de la matriz de conexión del FCM mediante **algoritmos de Machine
  Learning**.
- Simulación de escenarios **what-if**.
- Es el **primer módulo open source** que contiene todas las funcionalidades
  necesarias para proyectos orientados a FCM.

**Instalación:** `pip install fcmpy` (no `fcm`: ese nombre en PyPI corresponde a
herramientas de citometría de flujo). Repositorio: `SamvelMK/FCMpy` (MIT; versión
0.0.21 en la comprobación del 2026-10-26).

## 5. Media de Clase Más Cercana (Nearest Class Mean – NCM)

Esta es la acepción con **mayor soporte en librerías de Python establecidas**,
especialmente en **aprendizaje continuo** (*Continual Learning*). El clasificador
NCM es ampliamente preferido en **Class-Incremental Learning (CIL)** por su
**superior resistencia al olvido catastrófico** en comparación con las capas
fully connected.

### 5.1. `Avalanche` — la opción de referencia

**`Avalanche`** es una librería de referencia para el aprendizaje continuo en
PyTorch, desarrollada por ContinualAI. Incluye una implementación robusta del
clasificador NCM a través de la clase **`NCMClassifier`** (en
`avalanche.models.ncm_classifier`).

**Características técnicas del `NCMClassifier`** (comprobadas en el código
fuente):

- Realiza clasificación **nearest class mean** midiendo la distancia entre el
  tensor de entrada y los vectores medios almacenados en `self.class_means`.
- Antes de usarse para inferencia, debe actualizarse con un **vector medio por
  clase** llamando a `update_class_means_dict`.
- Registra un **buffer `class_means`** que almacena las medias en un único tensor
  de forma `[max_class_id_seen, feature_size]`.
- Soporta **normalización L2** opcional de la entrada antes de calcular la
  distancia.
- La actualización de las medias puede hacerse con **momentum** para promediar
  incrementalmente.

**Integración con plugins:** Avalanche proporciona el plugin `update_ncm` (en
`avalanche.training.plugins.update_ncm`) que facilita la actualización automática
de las medias de clase durante el entrenamiento continuo.

**Instalación:** `pip install avalanche-lib` (versión 0.6.0 en PyPI el
2026-10-26).

**Licencia:** MIT.

**Madurez:** la propia documentación de Avalanche se declara en **Beta**; es la
opción más mantenida del conjunto, pero no conviene presentarla como "lista para
producción" sin matizar.

### 5.2. `CapyMOA` — aprendizaje sobre flujos de datos

**`CapyMOA`** es una librería open source especializada en **machine learning
sobre data streams** y **online continual learning**. Proporciona una
implementación de NCM como estrategia de clasificación en
`capymoa.ocl.strategy.NCM` (archivo `_ncm.py`, clase `NCM`).

**Características:**

- El NCM en CapyMOA es un **clasificador basado en prototipos** que usa la media
  de cada clase como prototipo y asigna la clase con la media más cercana.
- Integra **MOA** (Massive Online Analysis), **scikit-learn** y **PyTorch**,
  permitiendo combinar algoritmos online de alto rendimiento con técnicas de deep
  learning modernas.
- Soporta escenarios de **task-incremental** y **class-incremental** con control
  explícito sobre los límites de tarea y los flujos de datos.
- Ejemplo de uso con `TinySplitMNIST` incluido en la documentación.

**Instalación:** `pip install capymoa` (versión 0.15.1 el 2026-10-26).

**Licencia:** BSD-3-Clause.

### 5.3. `HC-SOINN` — más allá del prototipo único

**`HC-SOINN`** es un repositorio de GitHub (`yhyet/HC_SOINN`) que contiene la
implementación oficial en PyTorch de un clasificador jerárquico que **"revisita"**
el clasificador NCM para el aprendizaje incremental de clases (CIL). El README
del repositorio lo presenta como aceptado en **ICML 2026**.

**Propuesta clave:** en lugar de asumir que cada clase colapsa en un **único
prototipo** (como hace el NCM estándar), HC-SOINN representa cada clase como una
**variedad topológica** (*topology-aware manifold*) compuesta por
**sub-prototipos locales** y un **centro global**.

**Componentes:**

- **STAR** (Structure-Topology Alignment via Residuals): mecanismo de seguimiento
  de trayectorias puntuales que adapta la topología aprendida al **feature drift
  no lineal** entre tareas incrementales.
- Entorno declarado: Python 3.10.19, PyTorch 2.0.1, torchvision, timm, numpy,
  scipy, scikit-learn, matplotlib.
- Datasets soportados: Split CIFAR-100, Split CUB-200, Split ImageNet-R.
- Configuraciones para métodos como SimpleCIL, DualPrompt, CODA-Prompt, SEMA,
  CLLoRA, etc.

**Licencia:** MIT (comprobada en GitHub).

**Naturaleza:** no es una librería general, sino el código de un paper
específico. Útil para reproducir resultados o como base para investigaciones
avanzadas en CIL.

### 5.4. Otras librerías de aprendizaje continuo relevantes

El ecosistema de continual learning en Python ha crecido. Además de Avalanche y
CapyMOA, existen otras opciones open source que pueden complementar el uso de
NCM. En la tabla se distingue lo que está publicado en PyPI de lo que solo se
distribuye como repositorio:

| Librería | Descripción | Disponibilidad |
| :--- | :--- | :--- |
| **`mammoth`** | Framework de PyTorch para benchmarking de continual learning. **Ojo:** el paquete `mammoth` de PyPI (1.13.0) es un conversor de DOCX a HTML/Markdown, no el framework; este se distribuye desde su repositorio | Repositorio (nombre de PyPI ocupado por otro proyecto) |
| **`continuum`** (1.2.7) | Librería limpia y simple para Continual Learning en PyTorch, con enfoque en data loading | `pip install continuum` |
| **`clearn-ai`** (0.3.0) | "Wrap once. Train forever." Envuelve cualquier modelo PyTorch y entrena en tareas secuenciales con una línea de código | `pip install clearn-ai` |
| **`isage-sias`** (0.1.0) | Algoritmos de selección de muestras y coresets para continual learning | `pip install isage-sias` |
| **`C3Box`** | Toolbox de Class-Incremental Learning basado en CLIP, usando NumPy y SciPy | **No localizado en PyPI con ese nombre** (2026-10-26) |

## 6. Comparativa técnica y recomendaciones

### 6.1. Tabla comparativa detallada

| Criterio | `HazyResearch/ncm` | `NCMPy` | `Avalanche` (NCM) | `CapyMOA` (NCM) | `HC-SOINN` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Concepto** | Next-Concept Modeling | Neutrosophic Cognitive Maps | Nearest Class Mean | Nearest Class Mean | NCM avanzado (CIL) |
| **Licencia** | MIT | Open source (paper) | MIT | BSD-3-Clause | MIT |
| **Empaquetado PyPI** | No | No (paper) | Sí (`avalanche-lib`) | Sí (`capymoa`) | No |
| **Madurez** | Release de investigación | Paper + software | Beta activa | Activa (0.x) | Paper (ICML 2026, según su README) |
| **Dependencias** | PyTorch, CUDA, Python 3.10+ | Python básico | PyTorch | PyTorch, MOA, scikit-learn | PyTorch, timm, scipy |
| **Documentación** | README + paper + blog | Paper | Extensa (API docs) | Buena (arXiv + docs) | README detallado |
| **Comunidad** | Stanford Hazy Research | Autores del paper | ContinualAI (grande) | Grupo MOA | Autores del paper |
| **Caso de uso** | Generación de texto paralela | Modelado de indeterminación | Clasificación incremental | Data streams online | CIL con topología |

### 6.2. Recomendaciones según el perfil

**Si el interés es el aprendizaje continuo (Continual Learning):**
la opción más madura y mantenida es **`Avalanche`**. Su `NCMClassifier` está bien
documentado, integrado en un ecosistema amplio de plugins y estrategias, y tiene
una comunidad activa. Para escenarios de **data streams** y **online learning**,
**`CapyMOA`** es la alternativa especializada. Si se necesita ir más allá del
prototipo único y trabajar con clases que no colapsan en un solo punto,
**`HC-SOINN`** ofrece una implementación avanzada basada en ICML 2026.

**Si se busca experimentar con generación de texto rápida (Next-Concept
Modeling):** el repositorio de **`HazyResearch/ncm`** es el punto de partida
indispensable. Los checkpoints en Hugging Face permiten probar los modelos sin
reentrenar. Es un release de investigación: hay que esperar iterar con el código
y adaptarlo.

**Si el interés son los mapas cognitivos:**

- Para **Neural Cognitive Maps**, las opciones son específicas y dependen del
  enfoque exacto. Si se busca planificación e imaginación dirigida a objetivos,
  **`POWER-KI/GCML`** es la implementación más completa y directamente
  reproducible. Si se busca aprendizaje de mapas desde imágenes, **gradCSCG** es
  el pipeline adecuado.
- Para **Neutrosophic Cognitive Maps**, **`NCMPy`** es la única librería
  dedicada, aunque su nombre ambiguo requiere precaución al buscarla. Si no se
  necesita modelar indeterminación, **`FCMpy`** es una alternativa madura y bien
  mantenida para Fuzzy Cognitive Maps.
- Para **lógica neutrosófica general**, las librerías `neutrosophics`, `rnel`,
  `adnus` y `thirdanswer` amplían el ecosistema más allá de los mapas cognitivos.

### 6.3. Cómo empezar rápidamente con cada una

**Avalanche (NCM para continual learning):**

```python
from avalanche.models import NCMClassifier

# Crear el clasificador NCM
ncm = NCMClassifier(normalize=True)

# Durante el entrenamiento, actualizar las medias de clase
# (normalmente a través del plugin update_ncm o manualmente)
ncm.update_class_means_dict({0: mean_vector_class0, 1: mean_vector_class1})
```

**HazyResearch/ncm (Next-Concept Modeling):**

```bash
git clone https://github.com/HazyResearch/ncm.git
cd ncm
pip install -r requirements.txt
# Descargar checkpoints desde Hugging Face (hazyresearch/ncm-checkpoints)
```

**CapyMOA (NCM para data streams):**

```python
from capymoa.ocl.strategy import NCM
# La documentación oficial incluye ejemplos con TinySplitMNIST
```

**NCMPy (Neutrosophic Cognitive Maps):**
consultar el paper **"NCMPy: A Modelling Software for Neutrosophic Cognitive
Maps based on Python Package"** para obtener el código y las instrucciones de
instalación. Evitar buscar únicamente por "ncmpy" en PyPI: el nombre está ocupado
por un cliente de música.

## 7. Conclusión

El ecosistema open source de Python para las distintas acepciones de **NCM** es
heterogéneo pero rico. Mientras que **Nearest Class Mean** cuenta con librerías
maduras y mantenidas como **Avalanche** y **CapyMOA**, las otras tres acepciones
(**Next-Concept Modeling**, **Neural Cognitive Maps** y **Neutrosophic Cognitive
Maps**) se encuentran en una fase más temprana, dominada por repositorios de
investigación y paquetes específicos de papers.

La elección de la herramienta correcta depende del objetivo:

- **Aprendizaje continuo** → `Avalanche` (beta activa, la más madura).
- **Experimentación con generación de texto paralela** → `HazyResearch/ncm`.
- **Investigación en mapas cognitivos neuronales** → `POWER-KI/GCML`,
  `gradCSCG` o repositorios específicos.
- **Modelado de indeterminación** → `NCMPy` (o `FCMpy` si no se necesita
  indeterminación).

Todas las opciones presentadas son **open source**, lo que permite reproducir,
auditar y adaptar el código. La recomendación final es **empezar por la librería
más madura del dominio de interés** (Avalanche para continual learning,
HazyResearch/ncm para generación de texto) y explorar los repositorios de
investigación solo cuando se necesiten capacidades que las librerías establecidas
no cubran.

## Anexo A. Verificación de fuentes (2026-10-26)

Comprobaciones realizadas con petición HTTP real a la API o al archivo primario.
"OK" significa que la fuente responde y el dato citado aparece en ella; no
implica que el software funcione en este equipo (no se instaló nada para esta
guía).

| Fuente | Comprobación | Resultado |
| :--- | :--- | :--- |
| arXiv:2610.14162 | API de arXiv | OK: "Next-Concept Modeling: Fast, Parallel Coarse-to-Fine Text Generation", 2026-10-09 |
| Blog de Hazy Research | HTTP | OK (200): `hazyresearch.stanford.edu/blog/2026-10-12-ncm` |
| `HazyResearch/ncm` | API de GitHub | OK: MIT, creado 2026-10-11, ~1.078 estrellas en la fecha |
| `hazyresearch/ncm-checkpoints` | Model card de HF | OK: MIT; xsum, wmt14, sudoku, lm1b, tinystories, owt |
| `hazyresearch/ncm-datasets` | API de HF | OK: dataset asociado |
| README de `HazyResearch/ncm` | Raw de GitHub | OK: Python 3.10+ y CUDA recomendados |
| `avalanche-lib` | PyPI | OK: 0.6.0, MIT |
| `NCMClassifier` | Código fuente | OK: clase, `class_means`, `update_class_means_dict(..., momentum=0.5)` |
| Plugin `update_ncm` | Código fuente | OK: exportado en `avalanche.training.plugins` |
| `capymoa` | PyPI + GitHub | OK: 0.15.1; `src/capymoa/ocl/strategy/_ncm.py`, clase `NCM`, exportada en `capymoa.ocl.strategy`; licencia BSD-3-Clause |
| `NCMPy` (paper) | Crossref | OK: DOI `10.61356/j.nswa.2024.114`, Vol. 13 (2024), Kandasamy et al. |
| `ncmpy` (PyPI) | PyPI | OK: 1.5.7, cliente de música; **no** es el paquete de NCM |
| `fcmpy` | PyPI + GitHub | OK: 0.0.21; `SamvelMK/FCMpy`, MIT |
| `neutrosophics` | PyPI | OK: 0.0.4 |
| `rnel` | PyPI | OK: 0.4.0 |
| `adnus` | PyPI | OK: 0.2.4, AGPL-3.0 |
| `thirdanswer` | PyPI | OK: 0.3.0, MIT |
| `POWER-KI/GCML-PWK-Neuromorfico-04` | API de GitHub | OK: MIT; 2 estrellas |
| Paper GCML | Crossref | OK: *Nature Machine Intelligence*, DOI `10.1038/s42256-026-01254-4`, 2026-07-21, Lin et al. |
| `LH-cbicr/GCML` | API de GitHub | OK: MIT |
| `tristanstoeber/gradCSCG` | API de GitHub | OK: MIT; la ruta del documento original estaba mal formada |
| arXiv:2607.12382 | API de arXiv | OK: "Differentiable Clone-Structured Causal Graphs...", 2026-07-14 |
| `yhyet/HC_SOINN` | API de GitHub | OK: MIT (el documento original decía "no especificada") |
| `arminbazza/LinearRL` | API de GitHub | OK; la ruta `ArminBaz/LinearRL` no resuelve |
| `wsojka00/graph_navigation` | API de GitHub | OK |
| `neuralml/hcRL` | API de GitHub | OK: MIT |
| `sgalella/CognitiveMaps` | API de GitHub | **404**: no verificable |
| `yadgar/cognitive_map` | API de GitHub | **404**: no verificable |
| `mammoth` | PyPI | **Colisión de nombre**: 1.13.0 es un conversor de DOCX, no el framework de CL |
| `continuum` | PyPI | OK: 1.2.7 |
| `clearn-ai` | PyPI | OK: 0.3.0 |
| `isage-sias` | PyPI | OK: 0.1.0 |
| `C3Box` | PyPI | **404**: no localizado en PyPI |

**Límites de esta verificación:** se comprobó existencia, licencia declarada,
versión publicada y, en dos casos (Avalanche y CapyMOA), el código de la clase
NCM. No se ejecutó ninguna de las librerías, no se midieron sus rendimientos y no
se validaron las cifras del paper de NCM en este equipo.

## Anexo B. Encaje en thinker

Este documento **no es una dependencia** de thinker. Se incorpora como
referencia verificada para trabajo futuro, con el mismo criterio que
`docs/REFERENCIAS-IA.md`: una idea solo se adopta si resuelve un defecto
reproducible o un requisito explícito y se mide con el benchmark propio. La
única parte que se ejecuta es el modo opt-in descrito abajo; el resto son
fuentes y contexto.

- **Next-Concept Modeling:** existen dos alcances complementarios y declarados.
  `informe_coarse_to_fine` conserva el modo original esquema→secciones.
  `informe_ncm_residual` añade la jerarquía **esquema global→secciones→
  refinamientos residuales de evidencia**, con hashes padre/hijo, detección de
  duplicados, reconstrucción en orden y paralelismo acotado dentro de cada
  nivel (`concept_ncm.py`). No es el tokenizer VQ ni el transformer entrenado
  del paper: los códigos son hashes de trazabilidad y el residuo son claims no
  cubiertos. Si el esquema o todas las secciones fallan, se registra y se vuelve
  a pasada única; las citas se validan y los fallos se aíslan.
  Además, `neural_concepts.ResidualVectorQuantizer` implementa VQ residual real
  con codebooks discretos y reconstrucción nivel a nivel en el extra opt-in
  `ml`. Es un banco de validación CPU, no un generador NCM de producción ni una
  prueba de calidad/velocidad comparable con el paper. Uso:

  ```python
  from deep_research_system import ResearchOrchestrator

  orquestador = ResearchOrchestrator(
      llm, search, informe_ncm_residual=True, max_workers=2)
  informe, contexto = orquestador.research("...")
  ```

  Validación: 6 tests de jerarquía/paralelismo/residuo/errores y 7 tests
  neurales (incluida equivalencia greedy del speculative decoding y
  reconstrucción VQ), sin afirmar ahorro ni calidad general.
- **Nearest Class Mean (Avalanche/CapyMOA):** thinker no hace clasificación
  incremental ni entrena clasificadores; no aplica.
- **Neural/Neutrosophic Cognitive Maps:** no hay solapamiento con el pipeline de
  investigación profunda; no aplica.
- **Qué sí se integra:** el modo `informe_coarse_to_fine` (opt-in, sin
  dependencias nuevas) y la guía en `docs/GUIA-NCM.md`, enlazada desde el índice
  del `README.md` y desde `docs/REFERENCIAS-IA.md`, con la lista de fuentes
  verificadas del anexo A. Eso evita que una futura tarea de investigación
  repita búsquedas y, sobre todo, que cite como válidas rutas que hoy devuelven
  404.

---

*Documento actualizado a octubre de 2026. Las fuentes y sus comprobaciones están
en el anexo A; lo no verificado se declara en el texto y no se presenta como
hecho.*
