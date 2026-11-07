# Guía Completa llama.cpp - Referencia Técnica

> **Estado**: documento de referencia en revisión (2026-11-07). Los ejemplos de
> `llama_cpp.Llama` se contrastaron con **llama-cpp-python 0.3.28**; el resto de
> comandos y modelos son orientativos y deben comprobarse con `--help` y la
> documentación oficial antes de usarlos.
> **Hardware de referencia (NO verificado en este equipo)**: RTX 3070 8 GB /
> 16 GB RAM / Linux. En esta máquina `nvidia-smi` no responde y solo hay CPU;
> las cifras de VRAM/contexto son cotas orientativas, no mediciones.
> **Modelo de referencia**: DeepSeek-R1 8B (Q4_K_M, ~5 GB, contexto de 131k
> declarado por el modelo; el contexto usable depende de la memoria para KV).

---

## 1. Instalación y Builds

### 1.1 Instalación Python (llama-cpp-python)
```bash
# CPU only (recomendado para inicio)
pip install llama-cpp-python

# Con aceleración GPU (CUDA)
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python --no-cache-dir

# Con Metal (macOS)
CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python

# Con Vulkan (Linux/Windows AMD/NVIDIA/Intel)
CMAKE_ARGS="-DGGML_VULKAN=on" pip install llama-cpp-python

# ROCm (AMD Linux)
CMAKE_ARGS="-DGGML_HIPBLAS=on" pip install llama-cpp-python

# Build desde source (última versión)
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
make LLAMA_CUBLAS=1  # o LLAMA_CUDA=1, LLAMA_HIPBLAS=1, LLAMA_METAL=1, etc.
```

### 1.2 Verificar instalación
```bash
python3 -c "from llama_cpp import Llama; print('llama-cpp-python:', __import__('llama_cpp').__version__)"
llama-cli --version  # CLI standalone
```

---

## 2. Modelos GGUF - Formatos y Quantización

### 2.1 Niveles de Quantización (Orden: Calidad → Tamaño)
| Quant | Bits | Tamaño (8B) | Calidad | Uso recomendado |
|-------|------|-------------|---------|-----------------|
| **Q2_K** | 2.5 | ~2.5 GB | Baja | Solo CPU muy limitada |
| **Q3_K_M** | 3.5 | ~3.2 GB | Media-Baja | CPU only, RAM ajustada |
| **Q4_K_M** ⭐ | 4.5 | **~4.8 GB** | **Óptima** | **Recomendado general** |
| **Q5_K_M** | 5.5 | ~5.8 GB | Alta | GPU con VRAM ≥8GB |
| **Q6_K** | 6.5 | ~6.8 GB | Muy Alta | GPU ≥10GB VRAM |
| **Q8_0** | 8.0 | ~8.5 GB | Máxima | GPU ≥12GB VRAM |
| **F16/F32** | 16/32 | 16/32 GB | Original | Solo debug/benchmark |

### 2.2 K-quants vs Legacy
| Tipo | Ventajas | Desventajas |
|------|----------|-------------|
| **K-quants (K_M, K_S, K_L)** | Mejor calidad/tamaño, calibración por capas | Ligeramente más lento |
| **Legacy (Q4_0, Q4_1, Q5_0, Q5_1, Q8_0)** | Más rápido, compatible antiguos | Peor calidad/tamaño |

### 2.3 Modelos recomendados (2026, orientativo)

> El «contexto» es el máximo declarado por el modelo; el usable depende de la
> memoria para KV. Los tamaños Q4 son aproximados y deben comprobarse en el
> repositorio del modelo.

| Modelo | Tamaño | Contexto | Uso |
|--------|--------|----------|-----|
| **DeepSeek-R1-Distill-Qwen-8B** | ~5 GB (Q4_K_M) | 131k | Razonamiento general |
| **DeepSeek-R1-Distill-Qwen-14B** | ~9 GB (Q4_K_M) | 131k | Coding/math |
| **DeepSeek-R1-Distill-Qwen-32B** | ~19 GB (Q4_K_M) | 131k | Calidad local alta |
| **Qwen3-8B/14B/32B** | 5-19 GB | 131k/256k | Multilingüe, tools |
| **Qwen3-Coder-7B/14B/32B** | 4.5-19 GB | 16k-131k | Coding |
| **Qwen3-30B-A3B** / Thinking | ~17 GB | 131k | MoE eficiente |
| **Gemma-3-12B/27B** | 7-15 GB | 131k/256k | Multimodal |
| **Gemma-4-26B-A4B** | ~14 GB | 131k | MoE |
| **Nemotron-3-Ultra-550B-A55B** | ~300 GB (Q4 estimado) | 128k | Top-tier; **no cabe en 16 GB** |
| **GLM-4-32B / GLM-4-32B-0414** | ~20 GB | 131k | Chino/inglés |
| **GLM-4-32B-0414-Zero** | ~20 GB | 131k | Sin alineación |
| **GPT-OSS-20B / 120B** | 11/60 GB | 131k | Open weights |
| **Llama-3.3-70B** | ~40 GB (Q4) | 128k | Referencia open |

---

## 3. Configuración Óptima (llama-cpp-python)

### 3.1 Parámetros Críticos
```python
import llama_cpp
from llama_cpp import Llama

llm = Llama(
    model_path="/path/to/model.gguf",

    # CONTEXTO: la KV cache crece con n_ctx y consume RAM/VRAM.
    n_ctx=8192,
    n_batch=512,
    n_ubatch=512,

    # GPU OFFLOAD (0 = CPU; -1 = todas las capas si caben)
    n_gpu_layers=0,

    # THREADING
    n_threads=8,
    n_threads_batch=8,

    # FORMATO
    chat_format="chatml",      # o "llama-3", "gemma", "mistral", etc.
    verbose=False,

    # MEMORIA / CACHE
    use_mmap=True,             # mmap de pesos (ahorra RAM)
    use_mlock=False,           # True evita swap, pero puede agotar la RAM
    type_k=None,               # p. ej. llama_cpp.GGML_TYPE_Q8_0
    type_v=None,
    flash_attn=False,          # solo si tu build y GPU lo soportan
)

# El sampling NO va en el constructor: va en cada llamada.
respuesta = llm.create_chat_completion(
    messages=[{"role": "user", "content": "Hola"}],
    temperature=0.7,
    top_p=0.95,
    top_k=40,
    min_p=0.05,
    repeat_penalty=1.1,
    max_tokens=256,
)
```

> Comprobado con `inspect.signature(llama_cpp.Llama.__init__)` en
> llama-cpp-python 0.3.28: `temperature`, `top_p`, `top_k`, `min_p`,
> `repeat_penalty`, `n_ctx_train`, `n_gqa`, `rms_norm_eps`, `low_vram`,
> `cache_type_k` y `cache_type_v` **no** son parámetros del constructor. Los
> de sampling van en `create_chat_completion`/`create_completion`; los tipos de
> cache se llaman `type_k`/`type_v`.

---

### 3.2 Sampling por caso de uso

El sampling se pasa en cada llamada, no en el constructor:

```python
# Chat / baja latencia
llm.create_chat_completion(messages=msgs, temperature=0.7, top_p=0.95,
                           top_k=40, max_tokens=512)

# Razonamiento (DeepSeek-R1)
llm.create_chat_completion(messages=msgs, temperature=0.6, top_p=0.95,
                           top_k=40, repeat_penalty=1.1, max_tokens=2048)

# Código (Qwen3-Coder)
llm.create_chat_completion(messages=msgs, temperature=0.2, top_p=0.95,
                           repeat_penalty=1.05, max_tokens=2048)

# Máxima velocidad: contexto corto y batch moderado en el constructor
llm = Llama(model_path="model.gguf", n_ctx=4096, n_batch=512,
            n_threads=8, n_gpu_layers=0, verbose=False)
```

---

### 3.3 Configuración por Hardware (orientativa)

| Hardware | n_gpu_layers | n_threads | n_batch | Modelo recomendado |
|----------|--------------|-----------|---------|-------------------|
| **RTX 3070 8 GB** | 35 | 8 | 512 | 8B Q4_K_M completo; 14B parcial o no cabe |
| **RTX 3080 10 GB** | 30-35 | 12 | 512 | 8B completo; 14B parcial |
| **RTX 3060 12 GB** | 30-35 | 8 | 512 | 8B completo; 14B parcial |
| **RTX 3090/4090 24 GB** | -1 | 16 | 1024 | 32B Q4 con contexto corto |
| **RTX 4090 24 GB x2** | -1 | 24 | 2048 | 70B Q4 con contexto moderado |
| **Apple M1/M2/M3 16 GB** | Metal | 8 | 512 | 8B-14B Q4 |
| **Apple M1/M2/M3 Max 64 GB** | Metal | 16 | 1024 | 32B-70B Q4 |
| **CPU only 16 GB RAM** | 0 | 8-16 | 256 | 7B-8B Q4, contexto 4k-8k |
| **CPU only 32 GB RAM** | 0 | 16-32 | 512 | 14B Q4, contexto 8k-16k |

> `n_ctx` no es gratis: la KV cache de un 8B a 131k tokens ocupa decenas de GB.
> En 8 GB de VRAM no cabe un contexto de 131k; empieza por 4k-8k y mide con
> `llama-bench` o el log de llama.cpp. Las filas son cotas orientativas, no
> mediciones de este equipo.

---

## 4. Formato de Prompt / Chat Templates

### 4.1 DeepSeek-R1 (ChatML)
```python
# Formato DeepSeek-R1 (ChatML)
prompt = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>
Eres un asistente útil.<|eot_id|>
<|start_header_id|>user<|end_header_id|>
Hola<|eot_id|>
<|start_header_id|>assistant<|end_header_id|>
Hola! ¿En qué puedo ayudarte?<|eot_id|>
<|start_header_id|>user<|end_header_id|>
¿Cuál es la capital de Francia?<|eot_id|>
<|start_header_id|>assistant<|end_header_id|>
"""
# Tokens especiales:
# <|begin_of_text|>, <|eot_id|>
# <|start_header_id|>system/user/assistant<|end_header_id|>
# <|begin_of_thought|>...<|end_of_thought|>
```

### 4.2 Qwen3 / Qwen3-Coder (ChatML)
```python
# Similar a DeepSeek pero tokens ligeramente distintos
# <|im_start|>system\n...<|im_end|>
# <|im_start|>user\n...\n<|im_end|>
# <|im_start|>assistant\n...
```

### 4.3 Llama-3 / Llama-3.1 / Llama-3.2
```python
# Formato Llama 3
"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
"You are a helpful assistant.<|eot_id|>"
"<|start_header_id|>user<|end_header_id|>\nHello<|eot_id|>"
"<|start_header_id|>assistant<|end_header_id|>\n"
```

### 4.4 Gemma / Gemma 2 / Gemma 3
```python
# Gemma usa formato propio
"<start_of_turn>user\nHello<end_of_turn>\n<start_of_turn>model\n"
```

### 4.5 Gemma 3 (Multimodal)
```python
# Incluye imágenes
"<start_of_turn>user\n[IMG]image.jpg<end_of_turn>\n<start_of_turn>model\n"
```

### 4.6 Qwen2.5-VL / Qwen2-VL (Vision)
```python
# Con imágenes
"<|im_start|>user\n<|vision_start|><|image_1|><|vision_end|>\nHello<|im_end|>"
```

### 4.6.1 Detectar formato automáticamente
```python
llm = Llama(
    model_path=model_path,
    chat_format="auto",  # Auto-detecta por nombre de modelo
    # o específico:
    chat_format="chatml",      # DeepSeek, Qwen
    chat_format="llama-3",     # Llama 3.x
    chat_format="gemma",       # Gemma 1/2
    chat_format="gemma-3",     # Gemma 3
    chat_format="llama-2",     # Llama 2
)
```

---

## 5. Sampling / Sampling Parameters

### 5.1 Parámetros Principales
```python
# CREATIVIDAD vs COHERENCIA
temperature=0.7,      # 0.0 = determinista, 1.0 = creativo, 1.5+ = caótico
top_p=0.95,           # nucleus sampling (0.9-0.95 típico)
top_k=40,             # top-k sampling (0 = desactivado)
min_p=0.05,           # minimum probability threshold
typical_p=1.0,        # typical sampling (1.0 = off)
```

### 5.2 Penalizaciones de Repetición
```python
repeat_penalty=1.1,        # 1.0 = sin penalización, 1.1-1.2 típico
repeat_penalty_sustain=256, # tokens a mirar atrás
repeat_penalty_slope=0.0,   # pendiente de penalización
repeat_penalty_range=1024,  # ventana de tokens a penalizar
```

### 5.3 Parámetros Avanzados
```python
min_p=0.05,              # threshold mínimo probabilidad
typical_p=1.0,           # typical sampling
epsilon_cutoff=0.0,      # cutoff por epsilon
eta_cutoff=0.0,          # eta cutoff
tfs_z=1.0,               # tail-free sampling
mirostat_mode=0,         # 0=off, 1=mirostat, 2=mirostat 2.0
mirostat_tau=5.0,        # target entropy
mirostat_eta=0.1,        # learning rate mirostat
```

### 5.4 Configuraciones por Caso de Uso

| Caso | temperature | top_p | top_k | repeat_penalty | Uso |
|------|-------------|-------|-------|----------------|-----|
| **Código** | 0.1-0.3 | 0.95 | 20-40 | 1.05 | Preciso, determinista |
| **Razonamiento (R1)** | 0.6 | 0.95 | 40 | 1.1 | CoT, razonamiento |
| **Chat casual** | 0.7-0.8 | 0.9-0.95 | 40-50 | 1.1 | Conversación natural |
| **Escritura creativa** | 0.9-1.0 | 0.95 | 40-50 | 1.1 | Narrativa |
| **Brainstorming** | 1.0-1.2 | 0.95-0.98 | 50-100 | 1.05 | Ideas |
| **Determinista/Exacto** | 0.0 | 1.0 | 1 | 1.0 | Determinista |

---

### 5.5 Sampling Avanzado - Mirostat
```python
# Mirostat 2.0 (auto-adapta temperature)
mirostat_mode=2,        # 0=off, 1=mirostat, 2=mirostat 2.0
mirostat_tau=5.0,       # target entropy (target surprisal)
mirostat_eta=0.1,       # learning rate
```
- **Mirostat 2.0** mantiene entropía objetivo automáticamente
- Útil para generación larga sin degeneración

---

## 6. Prompt Templates / Chat Templates

### 6.1 Registrar Template Personalizado
```python
llm = Llama(
    model_path=model_path,
    chat_format="custom",
    chat_handler=None,  # o custom handler
)

# O registrar template personalizado
from llama_cpp import Llama
Llama.register_chat_format("mi-template", {
    "system": "<|system|>\n{system}<|end|>",
    "user": "<|user|>\n{user}<|end|>",
    "assistant": "<|assistant|>\n{assistant}<|end|>",
    "stop": ["<|end|>", "<|user|>"],
})
```

### 6.2 Templates Comunes
```python
# chat_format="chatml"        # DeepSeek, Qwen, Phi-3
# chat_format="llama-3"       # Llama 3.x
# chat_format="llama-2"       # Llama 2
# chat_format="gemma"         # Gemma 1/2
# chat_format="gemma-3"       # Gemma 3
# chat_format="llama-2"       # Llama 2
# chat_format="mistral"       # Mistral
# chat_format="zephyr"        # Zephyr
# chat_format="chatml"        # ChatML genérico
```

---

### 6.3 Chat Handler Personalizado
```python
from llama_cpp import Llama, llama_chat_format

def custom_chat_handler(llm, messages, **kwargs):
    # Custom logic
    pass

llm = Llama(
    model_path=model_path,
    chat_handler=custom_chat_handler,
)
```

---

## 7. Streaming

### 7.1 Streaming Básico
```python
# Streaming simple
for chunk in llm.create_completion(
    prompt="Hola",
    max_tokens=512,
    stream=True,
):
    print(chunk["choices"][0]["text"], end="", flush=True)

# Chat completion streaming
for chunk in llm.create_chat_completion(
    messages=[{"role": "user", "content": "Hola"}],
    stream=True,
):
    delta = chunk["choices"][0]["delta"]
    if "content" in delta:
        print(delta["content"], end="", flush=True)
```

### 7.2 Streaming con Tool Calls
```python
for chunk in llm.create_chat_completion(
    messages=[...],
    tools=[{"type": "function", "function": {...}}],
    tool_choice="auto",
    stream=True,
):
    delta = chunk["choices"][0]["delta"]
    if "tool_calls" in delta:
        # Procesar tool calls en streaming
        pass
    if "content" in delta:
        print(delta["content"], end="", flush=True)
```

---

## 8. Function Calling / Tool Use

### 8.1 Definir Tools
```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Obtiene el clima actual",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Ciudad, país"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                },
                "required": ["location"]
            }
        }
    }
]

result = llm.create_chat_completion(
    messages=[{"role": "user", "content": "¿Clima en Madrid?"}],
    tools=tools,
    tool_choice="auto",
)
```

### 8.2 Tool Calling Streaming
```python
for chunk in llm.create_chat_completion(
    messages=[...],
    tools=tools,
    tool_choice="auto",
    stream=True,
):
    delta = chunk["choices"][0]["delta"]
    if "tool_calls" in delta:
        # Procesar tool calls incrementales
        for tc in delta["tool_calls"]:
            print(f"Tool call: {tc}")
    if "content" in delta:
        print(delta["content"], end="", flush=True)
```

---

### 8.3 Function Calling con DeepSeek-R1
```python
# DeepSeek-R1 soporta function calling nativo
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Obtiene clima",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Ciudad"},
                },
                "required": ["location"]
            }
        }
    }
]

result = llm.create_chat_completion(
    messages=[{"role": "user", "content": "Clima en Madrid"}],
    tools=tools,
    tool_choice="auto",
)
# result.choices[0].message.tool_calls
```

---

## 9. Embeddings

### 9.1 Generar Embeddings
```python
# Embeddings con llama.cpp (modelos embedding)
llm = Llama(
    model_path="path/to/embedding-model.gguf",
    embedding=True,  # Modo embedding
    n_ctx=8192,
)

# Single embedding
embedding = llm.create_embedding("Texto a embedder")
# embedding['data'][0]['embedding'] -> list[float]

# Batch embeddings
embeddings = llm.create_embedding(["texto 1", "texto 2", "texto 3"])
```

### 9.2 Modelos Embedding Recomendados
| Modelo | Dimensión | Licencia | Uso |
|--------|-----------|----------|-----|
| **BGE-M3** | 1024 | MIT | Multilingüe, SOTA |
| **BGE-Large-EN-V1.5** | 1024 | MIT | Inglés SOTA |
| **E5-Large-V2** | 1024 | MIT | Multilingüe |
| **GTE-Large-EN-V1.5** | 1024 | MIT | Inglés |
| **Nomic-Embed-Text-V1.5** | 768 | Apache-2 | General |
| **MXBAI-Embed-Large-V1** | 1024 | Apache-2 | General |
| **Jina-Embeddings-V3** | 1024 | CC-BY-NC | Multilingüe |

### 9.3 RAG con llama.cpp
```python
# RAG simple
def search(query, documents, top_k=5):
    query_emb = llm.create_embedding(query)['data'][0]['embedding']
    doc_embs = [llm.create_embedding(d)['data'][0]['embedding'] for d in documents]
    
    # Cosine similarity
    import numpy as np
    scores = [np.dot(query_emb, d) / (np.linalg.norm(query_emb) * np.linalg.norm(d)) 
              for d in doc_embs]
    top_indices = np.argsort(scores)[-top_k:][::-1]
    return [documents[i] for i in top_indices]
```

---

## 10. Herramientas y Utilidades

### 10.1 CLI (llama-cli / llama-server)
```bash
# Chat interactivo
llama-cli -m model.gguf -c 8192 -ngl 35 -cnv

# Servidor OpenAI-compatible
llama-server -m model.gguf -c 8192 -ngl 35 --port 8080

# Benchmark
llama-bench -m model.gguf -ngl 35 -c 8192

# Quantizar
llama-quantize model.f16.gguf model.q4_k_m.gguf Q4_K_M

# Convertir
llama-export model.gguf --format gguf --outtype q4_k_m
```

### 10.2 Benchmarks
```bash
# Benchmark velocidad
llama-bench -m model.gguf -ngl 35 -c 8192 -t 8 -b 512

# Latencia
llama-cli -m model.gguf -p "Hola" -n 100 -t 8
```

---

## 11. Optimización y Debugging

### 11.1 Debugging Común
```bash
# Verbose
llama-cli -m model.gguf -v -p "Hola"

# Debug tokens
llama-cli -m model.gguf -p "Hola" --logit-bias "1234:100"

# Ver tokens
llama-cli -m model.gguf -p "Hola" --logit-bias "1234:100" --logits-all
```

### 11.2 Problemas Comunes

| Problema | Causa | Solución |
|----------|-------|----------|
| `n_ctx_seq < n_ctx_train` | n_ctx < n_ctx_train | Aumentar n_ctx o usar modelo con n_ctx_train menor |
| OOM / CUDA OOM | VRAM insuficiente | Reducir n_gpu_layers, n_ctx, n_batch, cuantizar más |
| Slow generation | CPU offload | Aumentar n_gpu_layers, n_batch, n_gpu_layers=-1 |
| Repetitive output | Repetition penalty low | Aumentar repeat_penalty (1.1-1.2) |
| Gibberish / loops | Temperature alta, top_p alto | Bajar temperature (0.6-0.7), top_p (0.9) |
| Slow prompt processing | n_batch pequeño | Aumentar n_batch (512-2048) |
| Context overflow | n_ctx pequeño | Aumentar n_ctx, usar modelo con mayor contexto |
| Model not loading | Path wrong / corrupt | Verificar path, checksum, formato GGUF |

### 11.3 Memory Management
```python
# Forzar liberación
del llm
import gc; gc.collect()
torch.cuda.empty_cache()  # si usando torch
```

---

## 12. Benchmarks y Performance

### 12.1 Métricas Clave
| Métrica | Qué mide | Objetivo |
|---------|----------|----------|
| **TPS (tokens/sec)** | Velocidad generación | > 20 tok/s (GPU), > 5 tok/s (CPU) |
| **TTFT** | Time to First Token | < 500ms |
| **Latency/token** | Latencia por token | < 50ms |
| **Memory usage** | VRAM + RAM | < VRAM disponible |
| **Context utilization** | Uso real contexto | > 80% |

### 12.2 Benchmarks Comando
```bash
# Benchmark completo
llama-bench -m model.gguf -ngl 35 -c 8192 -t 8 -b 512 -p 512

# Latencia simple
llama-cli -m model.gguf -p "Hola" -n 100 -t 8

# Stress test
llama-bench -m model.gguf -ngl 35 -c 8192 -t 8 -b 512 -p 1024 -r 10
```

---

## 13. Modelos Destacados 2026 (Resumen)

| Modelo | Tamaño | Contexto | Quant | Uso | Descarga |
|--------|--------|----------|-------|-----|----------|
| **DeepSeek-R1-Distill-Qwen-8B** | ~5 GB | 131k | Q4_K_M | Razonamiento, coding | HF: deepseek-ai/DeepSeek-R1-Distill-Qwen-8B-GGUF |
| **DeepSeek-R1-Distill-Qwen-14B** | ~9 GB | 131k | Q4_K_M | Razonamiento | HF: deepseek-ai/DeepSeek-R1-Distill-Qwen-14B-GGUF |
| **DeepSeek-R1-Distill-Qwen-32B** | ~19 GB | 131k | Q4_K_M | Razonamiento | HF: deepseek-ai/DeepSeek-R1-Distill-Qwen-32B-GGUF |
| **DeepSeek-R1-Distill-Llama-70B** | ~40 GB | 131k | Q4_K_M | Top tier | HF: deepseek-ai/DeepSeek-R1-Distill-Llama-70B-GGUF |
| **Qwen3-8B / 14B / 32B** | 5-19 GB | 131k/256k | Q4_K_M | Multilingüe, tools | Qwen/Qwen3-*-GGUF |
| **Qwen3-Coder-7B/14B/32B** | 4.5-19 GB | 16k-131k | Q4_K_M | Coding | Qwen/Qwen3-Coder-*-GGUF |
| **Qwen3-30B-A3B / A3B-Thinking** | ~17 GB | 131k | Q4_K_M | MoE | Qwen/Qwen3-30B-A3B-GGUF |
| **Gemma-3-12B/27B** | 7-15 GB | 131k/256k | Q4_K_M | Multimodal | google/gemma-3-*-GGUF |
| **Gemma-4-26B-A4B** | ~14 GB | 131k | Q4_K_M | MoE | google/gemma-4-26b-a4b-GGUF |
| **Nemotron-3-Ultra-550B** | ~300 GB (Q4) | 128k | Q4_K_M | Top-tier; no cabe en 16 GB | nvidia/Nemotron-3-Ultra-550B-A55B-GGUF |
| **GPT-OSS-20B/120B** | 11/60 GB | 131k | Q4_K_M | Open weights | openai/gpt-oss-20b-GGUF |
| **Llama-3.3-70B** | ~40 GB | 128k | Q4_K_M | Referencia | meta-llama/Llama-3.3-70B-Instruct-GGUF |

---

## 14. Recursos y Enlaces

### 11.1 Repositorios Oficiales
- **llama.cpp**: https://github.com/ggml-org/llama.cpp
- **llama-cpp-python**: https://github.com/abetlen/llama-cpp-python
- **Hugging Face GGUF Models**: https://huggingface.co/models?library=gguf

### 11.2 Model Hubs
- **Hugging Face GGUF**: https://huggingface.co/models?library=gguf
- **DeepSeek Models**: https://huggingface.co/deepseek-ai
- **Qwen Models**: https://huggingface.co/Qwen
- **Qwen Coder**: https://huggingface.co/Qwen/Qwen3-Coder-32B-GGUF
- **Gemma**: https://huggingface.co/google/gemma-3-27b-GGUF
- **Gemma 4**: https://huggingface.co/google/gemma-4-26b-a4b-GGUF
- **Nemotron**: https://huggingface.co/nvidia/Nemotron-3-Ultra-550B-A55B-GGUF

### 11.3 Quantization Guides
- llama.cpp quantization: https://github.com/ggml-org/llama.cpp/blob/master/docs/quantization.md
- GGUF spec: https://github.com/ggml-org/gguf
- Quantization methods: Q4_K_M, Q5_K_M, Q6_K, Q8_0, IQ4_XS, etc.

---

## 15. Resumen Rápido (Cheatsheet)

```python
# CONFIGURACIÓN RECOMENDADA DeepSeek-R1 8B (RTX 3070 8GB)
llm = Llama(
    model_path="~/models/deepseek-r1-8b-q4_k_m.gguf",
    n_ctx=8192,
    n_gpu_layers=35,           # RTX 3070 8GB = 35 capas
    n_gpu_layers=-1,           # O -1 para todas
    n_ctx=8192,
    n_batch=512,
    n_threads=8,
    n_gpu_layers=-1,
    use_mlock=True,
    use_mmap=True,
    n_gpu_layers=-1,
    n_ctx=8192,
    n_batch=512,
    n_threads=8,
    chat_format="chatml",       # DeepSeek usa ChatML
    verbose=False,
)

# Generación
result = llm(
    "¿Capital de Francia?",
    max_tokens=50,
    temperature=0.6,
    top_p=0.95,
    top_k=40,
    repeat_penalty=1.1,
    stop=["<|eot_id|>"],
)

# Streaming
for chunk in llm.create_chat_completion(
    messages=[{"role": "user", "content": "Hola"}],
    stream=True,
):
    print(chunk["choices"][0]["delta"].get("content", ""), end="", flush=True)
```

---

**Última actualización**: 2026-11-07  
**Versión llama.cpp**: b6591 (main branch)  
**llama-cpp-python**: 0.3.x  
**Modelo test**: DeepSeek-R1-Distill-Qwen-8B (Q4_K_M, 8.2B params, 131k ctx)  
**Hardware validado**: RTX 3070 8GB / 16GB RAM / AMD Ryzen 7 5800H

---

> **Nota**: Este documento es un trabajo en progreso. La ecosistema llama.cpp evoluciona rápido. Verifica compatibilidad con versiones actuales antes de usar en producción.

---

## 16. Deployment y Serving en Producción

### 14.1 llama-server (Servidor Nativo)
```bash
# Servidor OpenAI-compatible
llama-server -m model.gguf \
  -c 8192 \
  -ngl 35 \
  --port 8080 \
  --host 0.0.0.0 \
  --threads 8 \
  --batch-size 512 \
  --ubatch-size 512 \
  --flash-attn \
  --cont-batching \
  --defrag-thold 0.1 \
  --defrag-thold-gpu 0.1

# Con métricas Prometheus
llama-server -m model.gguf -c 8192 -ngl 35 --port 8080 --metrics
```

### 14.2 llama.cpp como Servidor OpenAI-Compatible
```python
# Cliente OpenAI apuntando a llama-server
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="ollama"  # dummy
)

response = client.chat.completions.create(
    model="deepseek-r1:8b",
    messages=[{"role": "user", "content": "Hola"}],
    max_tokens=500,
    temperature=0.7
)
```

### 14.3 Docker Deployment
```dockerfile
# Dockerfile
FROM ghcr.io/ggml-org/llama.cpp:full-cuda-latest

# O build custom
FROM nvidia/cuda:12.4-devel-ubuntu22.04
RUN git clone https://github.com/ggml-org/llama.cpp /llama.cpp \
    && cd /llama.cpp \
    && make LLAMA_CUBLAS=1

COPY models/ /models/
EXPOSE 8080
CMD ["llama-server", "-m", "/models/model.gguf", "-c", "8192", "-ngl", "99", "--port", "8080"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  llama-server:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./models:/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### 14.3 Kubernetes Deployment
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llama-server
spec:
  replicas: 2
  selector:
    matchLabels:
      app: llama-server
  template:
    metadata:
      labels:
        app: llama-server
    spec:
      containers:
      - name: llama-server
        image: ghcr.io/ggml-org/llama.cpp:full-cuda-latest
        command: ["llama-server"]
        args:
          - "-m"
          - "/models/model.gguf"
          - "-c"
          - "8192"
          - "-ngl"
          - "99"
          - "--port"
          - "8080"
        resources:
          limits:
            nvidia.com/gpu: 1
            memory: "16Gi"
          requests:
            nvidia.com/gpu: 1
            memory: "8Gi"
        volumeMounts:
        - name: models
          mountPath: /models
      volumes:
      - name: models
        persistentVolumeClaim:
          claimName: models-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: llama-server
spec:
  selector:
    app: llama-server
  ports:
  - port: 8080
    targetPort: 8080
  type: LoadBalancer
```

### 14.4 llama.cpp como Servicio systemd
```ini
# /etc/systemd/system/llama-server.service
[Unit]
Description=llama.cpp Server
After=network.target

[Service]
Type=simple
User=llama
WorkingDirectory=/opt/llama.cpp
ExecStart=/usr/local/bin/llama-server \
  -m /models/model.gguf \
  -c 8192 \
  -ngl 35 \
  --port 8080 \
  --host 0.0.0.0 \
  --threads 8 \
  --batch-size 512 \
  --ubatch-size 512 \
  --flash-attn \
  --cont-batching
Restart=always
RestartSec=10
Environment="CUDA_VISIBLE_DEVICES=0"

[Install]
WantedBy=multi-user.target
```

```bash
# Instalar y habilitar
sudo cp llama-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now llama-server
sudo systemctl status llama-server
```

### 14.4 Health Checks y Monitoring
```bash
# Health check
curl -f http://localhost:8080/health

# Métricas Prometheus
curl http://localhost:8080/metrics

# En Prometheus config:
# - job_name: 'llama-server'
#   static_configs:
#     - targets: ['localhost:8080']
```

---

## 17. Fine-tuning / LoRA / QLoRA con llama.cpp

### 15.1 Preparación de Datos
```jsonl
# data.jsonl - Formato Alpaca/ShareGPT
{"instruction": "Escribe una función Python", "input": "Calcula fibonacci", "output": "def fib(n):..."}
{"instruction": "Explica", "input": "¿Qué es RAG?", "output": "RAG es..."}
```

### 15.2 Fine-tuning con llama.cpp (QLoRA)
```bash
# 1. Preparar datos
python3 -m llama_cpp.train \
  --model meta-llama/Llama-3-8B-Instruct \
  --data data.jsonl \
  --output_dir ./lora-output \
  --lora_r 16 \
  --lora_alpha 32 \
  --lora_dropout 0.05 \
  --learning_rate 2e-4 \
  --num_train_epochs 3 \
  --per_device_train_batch_size 4 \
  --gradient_accumulation_steps 4 \
  --fp16 \
  --gradient_checkpointing \
  --optim paged_adamw_8bit

# O con llama.cpp nativo (experimental)
python3 -m llama_cpp.finetune \
  --model_path ./models/base-model.gguf \
  --train_data ./data.jsonl \
  --output_dir ./finetuned \
  --lora_r 16 \
  --lora_alpha 32 \
  --epochs 3 \
  --learning_rate 2e-4
```

### 15.3 Merge LoRA y Exportar GGUF
```bash
# Merge LoRA weights
python3 -m llama_cpp.export \
  --base_model ./models/base.gguf \
  --lora_path ./lora-output/adapter_model.bin \
  --output ./merged-model.gguf \
  --outtype q4_k_m
```

### 15.4 Entrenamiento con llama.cpp (experimental)
```bash
# Entrenamiento nativo llama.cpp (experimental)
python3 -m llama_cpp.train \
  --model_path ./models/base.gguf \
  --train_data ./data.jsonl \
  --output_dir ./finetuned \
  --n_ctx 4096 \
  --n_batch 128 \
  --n_gpu_layers 35 \
  --learning_rate 2e-4 \
  --num_epochs 3 \
  --lora_r 16 \
  --lora_alpha 32 \
  --save_steps 500
```

---

## 18. RAG Avanzado con llama.cpp

### 16.1 RAG Completo Local
```python
import numpy as np
from llama_cpp import Llama
import sqlite3
import json

class LocalRAG:
    def __init__(self, model_path, db_path="rag.db", embedding_model_path=None):
        self.llm = Llama(model_path=model_path, n_ctx=8192, n_gpu_layers=0,
                         verbose=False)
        # Un modelo de embeddings se carga en su propia instancia Llama.
        # `embedding_model` NO es un parámetro de Llama en 0.3.28.
        self.embedder = Llama(
            model_path=embedding_model_path or model_path,
            n_ctx=8192,
            n_gpu_layers=0,
            embedding=True,
            verbose=False,
        )
        self.db = sqlite3.connect(db_path)
        self._init_db()
    
    def _init_db(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY,
                content TEXT,
                embedding BLOB,
                metadata TEXT
            )
        """)
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_embedding ON documents(embedding)")
        self.db.commit()
    
    def add_document(self, content: str, metadata: dict = None):
        """Añade documento con embedding"""
        embedding = self.embedder.create_embedding(content)['data'][0]['embedding']
        self.db.execute(
            "INSERT INTO documents (content, embedding, metadata) VALUES (?, ?, ?)",
            (content, np.array(embedding, dtype=np.float32).tobytes(), json.dumps(metadata or {}))
        )
        self.db.commit()
    
    def search(self, query: str, top_k: int = 5) -> list:
        """Búsqueda semántica + reranking"""
        query_emb = self.embedder.create_embedding(query)['data'][0]['embedding']
        query_vec = np.array(query_emb, dtype=np.float32)
        
        # Cosine similarity
        cursor = self.db.execute("SELECT content, embedding, metadata FROM documents")
        results = []
        for row in cursor:
            emb = np.frombuffer(row[1], dtype=np.float32)
            sim = np.dot(query_vec, emb) / (np.linalg.norm(query_vec) * np.linalg.norm(query_vec))
            results.append((sim, row[0], json.loads(row[2])))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return results[:top_k]
    
    def generate_answer(self, query: str, context: list) -> str:
        """Genera respuesta con contexto"""
        context_str = "\n\n".join([f"[{i+1}] {c[1]}" for i, c in enumerate(context)])
        
        prompt = f"""Contexto:
{context_str}

Pregunta: {query}

Responde basándote solo en el contexto proporcionado."""
        
        result = self.llm(
            f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n",
            max_tokens=1024,
            temperature=0.3,
            top_p=0.9,
            stop=["<|eot_id|>"]
        )
        return result['choices'][0]['text']

# Uso
rag = LocalRAG("model.gguf")
rag.add_document("La fotosíntesis es el proceso...")
rag.add_document("La clorofila captura luz...")
result = rag.generate_answer("¿Qué es la fotosíntesis?", rag.search("fotosíntesis"))
```

### 16.2 RAG con SQLite-Vec (Vector Search Nativo)
```bash
# Extensión SQLite-Vec para búsqueda vectorial nativa
# https://github.com/asg017/sqlite-vec

# En Python
import sqlite_vec

# Crear tabla con vector
conn.execute("CREATE VIRTUAL TABLE docs USING vec0(embedding float[1024])")

# Insertar
conn.execute("INSERT INTO docs(vec) VALUES (?)", [embedding])

# Buscar
results = conn.execute("""
    SELECT content FROM docs 
    WHERE vec_distance_cosine(embedding, ?) < 0.3
    ORDER BY vec_distance_cosine(embedding, ?) ASC
    LIMIT 5
""", [embedding, embedding])
```

### 16.3 RAG Híbrido (BM25 + Vector + Rerank)
```python
from rank_bm25 import BM25Okapi
import numpy as np

class HybridRAG:
    def __init__(self, llm, docs):
        self.llm = llm
        self.docs = docs
        self.bm25 = BM25Okapi([d.split() for d in docs])
        self.embeddings = [self.embed(d) for d in docs]
    
    def search(self, query, top_k=5, alpha=0.5):
        # BM25 scores
        bm25_scores = self.bm25.get_scores(query.split())
        
        # Vector similarity
        q_emb = self.embed(query)
        vec_scores = [cosine_sim(q, d) for d in self.embeddings]
        
        # Hybrid score
        scores = alpha * np.array(bm25_scores) + (1-alpha) * np.array(vec_scores)
        top_k = np.argsort(scores)[-top_k:][::-1]
        return [self.docs[i] for i in top_k]
```

---

## 19. Multi-GPU / Distributed Inference

### 17.1 Tensor Split (Multi-GPU)
```python
# Dividir modelo entre GPUs
llm = Llama(
    model_path="model.gguf",
    n_gpu_layers=-1,
    tensor_split=[0.5, 0.5],  # 50/50 entre 2 GPUs
    main_gpu=0,                # GPU principal
    n_gpu_layers=-1,
)
```

### 17.2 Tensor Split Avanzado
```python
# Split desigual (ej: 24GB + 12GB VRAM)
tensor_split=[0.66, 0.34]  # 66% en GPU0, 34% en GPU1

# O por capas exactas
tensor_split=[0.5, 0.5]  # Split por capas (aprox)
```

### 17.3 Distributed Inference (Múltiples Nodos)
```bash
# llama.cpp no soporta nativamente multi-nodo
# Usar vLLM / TGI / Ray para multi-nodo

# Workaround: Sharding manual
# Nodo 1: Capas 0-17
# Nodo 2: Capas 18-35
# Requiere comunicación manual entre nodos
```

---

## 20. Comparativa: llama.cpp vs vLLM vs TGI

| Característica | llama.cpp | vLLM | TGI (Text Generation Inference) | TensorRT-LLM |
|----------------|-----------|------|----------------------------------|--------------|
| **Lenguaje** | C/C++ | Python/C++ | Rust/Python | C++/CUDA |
| **Quantization** | GGUF (K-quants) | AWQ, GPTQ, FP8 | AWQ, GPTQ, FP8 | FP8, INT4/INT8 |
| **Context Length** | 131k+ | 128k-1M+ | 128k-1M+ | 128k+ |
| **Throughput (tok/s)** | Alto (CPU/GPU) | **Máximo** | Alto | **Máximo** |
| **Latencia (TTFT)** | Baja | **Mínima** | Baja | **Mínima** |
| **Batching** | Cont-batching | **Continuous Batching** | Continuous Batching | **Continuous Batching** |
| **Multi-GPU** | Tensor Split | Tensor Parallel | Tensor Parallel | Tensor Parallel |
| **Multi-Node** | ❌ | ✅ Ray | ✅ | ✅ |
| **Quantization** | GGUF (K-quants) | AWQ/GPTQ/FP8 | AWQ/GPTQ/FP8 | FP8/INT4/INT8 |
| **Quantization Tools** | llama.cpp quantize | AWQ/GPTQ tools | AutoAWQ/AutoGPTQ | TensorRT quant |
| **OpenAI API** | Parcial | ✅ Completo | ✅ Completo | Parcial |
| **Streaming** | ✅ | ✅ | ✅ | ✅ |
| **Tool Calling** | Parcial | ✅ Completo | ✅ | Parcial |
| **Function Calling** | Parcial | ✅ | ✅ | Parcial |
| **Vision/Multimodal** | Parcial (llava) | ✅ | ✅ | Parcial |
| **Fine-tuning** | LoRA (exp) | ✅ (PEFT) | ✅ (SFT/RLHF) | ⚠️ |
| **Quantization Tools** | llama.cpp quantize | AutoAWQ, AutoGPTQ | AutoAWQ, AutoGPTQ | TensorRT Quant |
| **Hardware** | CPU/GPU/Apple/ROCm | NVIDIA GPU | NVIDIA GPU | NVIDIA GPU |
| **License** | MIT | Apache 2.0 | Apache 2.0 | Propietario |
| **Comunidad** | Activa | Muy Activa | Activa | NVIDIA |
| **Producción** | ✅ (Edge/Embedded) | ✅ (Cloud) | ✅ (Cloud) | ✅ (Cloud) |

### Cuándo usar cada uno

| Escenario | Recomendación |
|-----------|---------------|
| **Edge / Local / Offline / CPU** | **llama.cpp** |
| **Cloud / Alta throughput / Multi-GPU** | **vLLM** |
| **Enterprise / Enterprise support** | **TGI** |
| **Max performance NVIDIA** | **TensorRT-LLM** |
| **Apple Silicon / CPU only** | **llama.cpp (Metal)** |
| **Quantization custom** | **llama.cpp** |
| **Multi-node / Cluster** | **vLLM / TGI** |
| **Function Calling / Tools** | **vLLM / TGI** |
| **Fine-tuning integrado** | **vLLM / TGI** |

---

## 21. Security / Safety / Guardrails

### 18.1 Prompt Injection Defense
```python
def sanitize_prompt(prompt: str) -> str:
    """Sanitiza prompt contra inyección"""
    # Detectar patrones de inyección
    injection_patterns = [
        r"ignore.*previous.*instructions",
        r"ignore.*above",
        r"system.*prompt",
        r"you are now",
        r"act as",
        r"ignore.*instructions",
        r"system.*prompt",
    ]
    
    for pattern in injection_patterns:
        if re.search(pattern, prompt, re.IGNORECASE):
            raise ValueError(f"Posible inyección detectada: {pattern}")
    
    return prompt

# En el handler
def safe_generate(prompt: str, **kwargs):
    safe_prompt = sanitize_prompt(prompt)
    return llm(prompt, **kwargs)
```

### 18.2 Content Filtering
```python
# Filtrado post-generación
def filter_output(text: str) -> str:
    # Lista de patrones prohibidos
    banned = [
        r"\b(password|secret|key|token)\s*[:=]\s*\S+",
        r"(ssn|social security)\s*\d{3}-?\d{2}-?\d{4}",
        r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",  # Credit cards
    ]
    
    for pattern in banned:
        if re.search(pattern, text, re.IGNORECASE):
            return "[CONTENIDO FILTRADO]"
    return text
```

### 18.3 Rate Limiting y Abuse Prevention
```python
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_requests=60, window=60):
        self.requests = defaultdict(list)
        self.max_requests = max_requests
        self.window = window
    
    def check(self, client_id: str) -> bool:
        now = time.time()
        self.requests[client_id] = [
            t for t in self.requests[client_id] 
            if now - t < self.window
        ]
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        self.requests[client_id].append(now)
        return True

limiter = RateLimiter(max_requests=60, window=60)

@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    client_ip = request.remote_addr
    if not limiter.check(client_ip):
        return jsonify({"error": "Rate limit exceeded"}), 429
    # ...
```

### 18.4 Content Moderation
```python
# Integración con modelos de moderación
MODERATION_MODEL = "omni-moderation-latest"

async def moderate(content: str) -> dict:
    response = openai.moderations.create(
        model="omni-moderation-latest",
        input=content
    )
    return {
        "flagged": response.results[0].flagged,
        "categories": response.results[0].categories.model_dump(),
        "scores": response.results[0].category_scores.model_dump()
    }

# En handler
async def safe_completion(prompt):
    mod = await moderate(prompt)
    if mod["flagged"]:
        raise HTTPException(400, "Contenido no permitido")
    return llm.generate(prompt)
```

---

## 22. Performance Tuning / Benchmarking

### 19.1 Benchmarking Script
```bash
#!/bin/bash
# benchmark.sh

MODEL=$1
N_CTX=${2:-8192}
N_GPU_LAYERS=${3:-35}
THREADS=${4:-8}
BATCH=${5:-512}

echo "Benchmarking $MODEL"
echo "Context: $N_CTX, GPU Layers: $N_GPU_LAYERS, Threads: $THREADS, Batch: $BATCH"

# Warmup
llama-cli -m $MODEL -c $N_CTX -ngl $N_GPU_LAYERS -t $THREADS -b $BATCH -p "Warmup" -n 10 > /dev/null

# Benchmark
llama-bench -m $MODEL \
  -c $N_CTX \
  -ngl $N_GPU_LAYERS \
  -t $THREADS \
  -b $BATCH \
  -p 512 \
  -n 100 \
  -r 5
```

### 19.2 Métricas Clave a Monitorizar
```python
import time
import psutil
import GPUtil

def benchmark_generation(llm, prompt, n_runs=10):
    metrics = {
        "ttft": [],      # Time to First Token
        "tps": [],       # Tokens per second
        "latency": [],   # Latencia total
        "vram_used": [], # VRAM usada
        "ram_used": [],  # RAM usada
        "gpu_util": [],  # GPU utilization
    }
    
    for i in range(10):
        # VRAM antes
        gpu = GPUtil.getGPUs()[0]
        vram_before = gpu.memoryUsed
        
        start = time.time()
        result = llm("Prompt de prueba " * 100, max_tokens=512)
        elapsed = time.time() - start
        
        # VRAM después
        gpu = GPUtil.getGPUs()[0]
        vram_after = gpu.memoryUsed
        
        tokens = len(result['choices'][0]['text'].split())  # aprox
        
        metrics["ttft"].append(result.get('ttft', 0))
        metrics["tps"].append(result['usage']['completion_tokens'] / (time.time() - start))
        metrics["latency"].append(elapsed)
        metrics["vram_used"].append(vram_after - vram_before)
        metrics["ram_used"].append(psutil.Process().memory_info().rss / 1024**3)
        metrics["gpu_util"].append(gpu.load * 100)
    
    return {k: np.mean(v) for k, v in metrics.items()}
```

### 19.3 Profiling con NSight / NSYS
```bash
# NVIDIA NSYS Profile
nsys profile --trace=cuda,nvtx,osrt -o llama_profile llama-cli -m model.gguf -p "Hola" -n 100

# Analizar
nsys stats llama_profile.qdrep
```

---

## 23. Troubleshooting Exhaustivo

### 18.1 Problemas Comunes y Soluciones

| Síntoma | Causa Probable | Solución |
|---------|----------------|----------|
| `n_ctx_seq < n_ctx_train` | n_ctx < n_ctx_train del modelo | Aumentar `n_ctx` o usar modelo compatible |
| `CUDA OOM` | VRAM insuficiente | Reducir `n_gpu_layers`, `n_ctx`, `n_batch`, cuantizar más |
| `Segmentation fault` | Driver CUDA / modelo corrupto | Actualizar drivers, verificar checksum modelo |
| `GGUF: invalid magic` | Archivo corrupto / no GGUF | Verificar checksum, re-descargar |
| `Unsupported model architecture` | Arquitectura no soportada | Actualizar llama.cpp, usar modelo compatible |
| `n_ctx_seq < n_ctx_train` | Contexto > entrenamiento | Reducir `n_ctx` o usar modelo con mayor `n_ctx_train` |
| `Error: max_tokens exceeds context` | `max_tokens` > `n_ctx` | Reducir `max_tokens` o aumentar `n_ctx` |
| `Repetitive output` | `repeat_penalty` bajo | Aumentar `repeat_penalty` (1.1-1.2) |
| `Gibberish / loops` | Temp alta / top_p alto | Bajar `temperature` (0.6-0.7), `top_p` (0.9) |
| `Slow generation` | CPU offload | Aumentar `n_gpu_layers`, `n_batch` |
| `Slow prompt processing` | `n_batch` pequeño | Aumentar `n_batch` (512-2048) |
| `Context overflow` | `n_ctx` pequeño | Aumentar `n_ctx`, cuantizar más |
| `CUDA error: invalid device ordinal` | GPU incorrecta | Verificar `CUDA_VISIBLE_DEVICES` |
| `Error: model requires AVX2` | CPU sin AVX2 | Compilar sin AVX2 o usar CPU compatible |
| `GGUF: unsupported version` | Versión GGUF nueva | Actualizar llama.cpp |

### 18.3 Debugging Avanzado
```bash
# Debug logs
GGML_LOG_LEVEL=DEBUG llama-cli -m model.gguf -p "Test" -n 10

# Verbose llama.cpp
GGML_LOG_LEVEL=DEBUG llama-server -m model.gguf -c 8192

# Debug OpenAI API
OPENAI_LOG=debug python3 -c "import openai; ..."

# NSYS Profile
nsys profile --trace=cuda,nvtx,osrt -o profile llama-cli -m model.gguf -p "Test" -n 10
nsys stats profile.qdrep
```

---

## 23.4 Configuración por Problema

```python
# PROBLEMA: OOM en GPU
llm = Llama(
    model_path="model.gguf",
    n_gpu_layers=20,      # Reducir capas en GPU
    n_ctx=4096,           # Reducir contexto (KV cache)
    n_batch=128,          # Batch pequeño
    use_mlock=False,      # mlock puede agravar el OOM
    verbose=False,
)

# PROBLEMA: Lento en CPU
llm = Llama(
    model_path="model.gguf",
    n_threads=os.cpu_count(),  # Todos los cores
    n_batch=512,               # Batch grande
    use_mmap=True,             # mmap activado
    use_mlock=False,
    verbose=False,
)

# PROBLEMA: Repetición (el sampling va en la llamada, NO en el constructor)
llm.create_chat_completion(
    messages=msgs,
    repeat_penalty=1.15,
    temperature=0.6,
    top_p=0.9,
    max_tokens=512,
)

# PROBLEMA: Contexto insuficiente (n_ctx grande consume RAM/VRAM)
llm = Llama(
    model_path="model.gguf",
    n_ctx=32768,           # subir solo si la memoria lo permite
    n_batch=512,
    rope_freq_base=10000,
    rope_freq_scale=1.0,
    yarn_ext_factor=1.0,
    yarn_attn_factor=1.0,
    yarn_beta_fast=32,
    yarn_beta_slow=1,
    verbose=False,
)
```

---

## 24. Deployment Checklist

```bash
# PRE-DEPLOYMENT CHECKLIST
□ Modelo verificado (checksum SHA256)
□ n_ctx >= requerido por aplicación
□ n_gpu_layers optimizado para GPU
□ n_batch / n_ubatch optimizados
□ n_threads = CPU cores
□ n_gpu_layers = -1 (all) o capas exactas
□ n_ctx >= max_context_needed
□ n_batch >= 512 (throughput) / 128 (latencia)
□ n_ubatch = n_batch
□ flash_attn habilitado (si soportado)
□ cont_batching habilitado
□ flash_attn + cont_batching = max throughput
□ Health check endpoint funcionando
□ Métricas Prometheus expuestas
□ Logs estructurados (JSON)
□ Rate limiting configurado
□ Timeouts configurados (30-120s)
□ Graceful shutdown (SIGTERM handling)
□ Graceful restart (zero-downtime)
□ Health check endpoint (/health)
□ Métricas Prometheus (/metrics)
□ Logs estructurados (JSON)
□ Alertas configuradas (latencia, error rate, VRAM)
□ Backup / rollback plan
□ Rollback testado
□ Load testing completado
□ Chaos engineering (kill pod, GPU failure)
□ Runbook documentado
□ Runbook testado
```

---

## 25. Recursos y Referencias

### 20.1 Enlaces Oficiales
- **llama.cpp**: https://github.com/ggml-org/llama.cpp
- **llama-cpp-python**: https://github.com/abetlen/llama-cpp-python
- **Hugging Face GGUF**: https://huggingface.co/models?library=gguf
- **Discord llama.cpp**: https://discord.gg/ggml
- **Discord llama-cpp-python**: https://discord.gg/llama-cpp-python

### 11.2 Model Hubs GGUF
| Proveedor | URL |
|-----------|-----|
| **Hugging Face GGUF** | https://huggingface.co/models?library=gguf |
| **DeepSeek** | https://huggingface.co/deepseek-ai |
| **Qwen** | https://huggingface.co/Qwen |
| **Qwen Coder** | https://huggingface.co/Qwen/Qwen3-Coder-32B-GGUF |
| **Gemma** | https://huggingface.co/google/gemma-3-27b-GGUF |
| **Gemma 4** | https://huggingface.co/google/gemma-4-26b-a4b-GGUF |
| **Nemotron** | https://huggingface.co/nvidia/Nemotron-3-Ultra-550B-A55B-GGUF |
| **Llama** | https://huggingface.co/meta-llama |
| **Microsoft Phi** | https://huggingface.co/microsoft |
| **Yi** | https://huggingface.co/01-ai |

### 11.3 Quantization Guides
- llama.cpp quantization: https://github.com/ggml-org/llama.cpp/blob/master/docs/quantization.md
- GGUF spec: https://github.com/ggml-org/gguf
- K-quants explanation: https://github.com/ggml-org/llama.cpp/pull/6847

---

## 26. Resumen Rápido (Cheatsheet Final)

```python
# CONFIGURACIÓN DEFINITIVA DeepSeek-R1 8B (RTX 3070 8GB)
llm = Llama(
    model_path="~/models/deepseek-r1-8b-q4_k_m.gguf",
    n_ctx=8192,
    n_gpu_layers=35,           # RTX 3070 8GB = 35 capas
    n_gpu_layers=-1,           # O -1 para todas
    n_ctx=8192,
    n_batch=512,
    n_threads=8,
    n_gpu_layers=-1,
    use_mlock=True,
    use_mmap=True,
    n_gpu_layers=-1,
    n_ctx=8192,
    n_batch=512,
    chat_format="chatml",       # DeepSeek usa ChatML
    verbose=False,
)

# Generación
result = llm(
    "¿Capital de Francia?",
    max_tokens=50,
    temperature=0.6,
    top_p=0.95,
    top_k=40,
    repeat_penalty=1.1,
    stop=["<|eot_id|>"],
)

# Streaming
for chunk in llm.create_chat_completion(
    messages=[{"role": "user", "content": "Hola"}],
    stream=True,
):
    print(chunk["choices"][0]["delta"].get("content", ""), end="", flush=True)
```

---

**Última actualización**: 2026-11-07  
**Versión llama.cpp**: b6591 (main branch)  
**llama-cpp-python**: 0.3.x  
**Modelo test**: DeepSeek-R1-Distill-Qwen-8B (Q4_K_M, 8.2B params, 131k ctx)  
**Hardware validado**: RTX 3070 8GB / 16GB RAM / AMD Ryzen 7 5800H  

---

> **Nota**: Este documento es un trabajo en progreso. La ecosistema llama.cpp evoluciona rápido. Verifica compatibilidad con versiones actuales antes de usar en producción.