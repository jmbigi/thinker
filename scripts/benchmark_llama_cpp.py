#!/usr/bin/env python3
"""
Benchmark de llama.cpp: prefill vs generación, OpenBLAS, GPU offload.

Mide:
- Prefill latency (tokens/seg procesando prompt)
- Generation throughput (tokens/seg generando)
- Latencia primera token (TTFT)
- Uso de memoria VRAM/RAM

Uso:
    python3 scripts/benchmark_llama_cpp.py --model PATH --backend llama-cpp
    python3 scripts/benchmark_llama_cpp.py --model PATH --backend ollama
    python3 scripts/benchmark_llama_cpp.py --model PATH --backend olla
"""

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


@dataclass
class BenchmarkResult:
    backend: str
    model: str
    config: Dict[str, Any]

    # Prefill metrics
    prefill_tokens: int = 0
    prefill_time_sec: float = 0.0
    prefill_tps: float = 0.0

    # Generation metrics
    gen_tokens: int = 0
    gen_time_sec: float = 0.0
    gen_tps: float = 0.0

    # Latency
    ttft_ms: float = 0.0  # Time to first token

    # Memory (si disponible)
    vram_mb: Optional[float] = None
    ram_mb: Optional[float] = None

    # Raw measurements
    raw_times: List[float] = None

    def to_dict(self) -> Dict:
        d = asdict(self)
        if self.raw_times is not None:
            d["raw_times"] = self.raw_times
        return d


class LlamaCppBench:
    """Benchmark para llama.cpp server."""

    def __init__(self, server_bin: str = "llama-server"):
        self.server_bin = server_bin
        self.process = None
        self.port = 11436

    def start_server(self, model: str, args: List[str]) -> bool:
        """Inicia llama-server con el modelo y args dados."""
        if self.process:
            self.stop_server()

        self.model_path = model  # Guardar para el benchmark
        cmd = [self.server_bin, "-m", model, "--port", str(self.port)] + args
        print(f"Iniciando: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Esperar a que el servidor esté listo
        for _ in range(30):
            try:
                import urllib.request
                urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=1)
                print("Servidor listo")
                return True
            except Exception:
                time.sleep(1)
        print("Timeout esperando servidor")
        return False

    def stop_server(self):
        """Detiene solo el servidor que inició este objeto."""
        if not self.process:
            return
        proceso = self.process
        self.process = None
        proceso.terminate()
        try:
            proceso.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proceso.kill()
            proceso.wait(timeout=5)

    def benchmark(self, prompt: str, max_tokens: int = 128, n_runs: int = 5) -> BenchmarkResult:
        """Ejecuta benchmark contra el servidor."""
        import urllib.request

        results = []
        for run in range(n_runs):
            # Completions endpoint
            url = f"http://127.0.0.1:{self.port}/completion"
            data = json.dumps({
                "prompt": prompt,
                "n_predict": max_tokens,
                "temperature": 0.7,
                "stream": False,
            }).encode()

            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}
            )

            start = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode())
                elapsed = time.perf_counter() - start
                results.append((elapsed, result))
            except Exception as e:
                print(f"Error en run {run}: {e}")
                continue

        if not results:
            raise RuntimeError("No se obtuvieron resultados válidos")

        # Analizar resultados
        # llama.cpp devuelve timing en result['timings']
        prefill_times = []
        gen_times = []
        gen_tps_list = []
        ttft_list = []

        for elapsed, result in results:
            timings = result.get("timings", {})
            # Prompt eval = prefill
            if "prompt_n" in timings and "prompt_ms" in timings:
                prefill_ms = timings["prompt_ms"]
                prefill_times.append(prefill_ms / 1000.0)

            # Generation
            if "predicted_n" in timings and "predicted_ms" in timings:
                gen_tokens = timings["predicted_n"]
                gen_ms = timings["predicted_ms"]
                gen_times.append(gen_ms / 1000.0)
                if gen_ms > 0:
                    gen_tps_list.append(gen_tokens / (gen_ms / 1000.0))

            # TTFT (aprox: primer token = prefill + primer predicted)
            # No hay métrica directa, usar prefill time como proxy
            if "prompt_ms" in timings:
                ttft_list.append(timings["prompt_ms"])

        # Calcular promedios
        avg_prefill_tps = 0
        if prefill_times:
            # Usar el último result para obtener prompt_n
            last_timings = results[-1][1].get("timings", {})
            prompt_n = last_timings.get("prompt_n", 0)
            avg_prefill_tps = statistics.mean(
                [prompt_n / t for t in prefill_times if t > 0]
            ) if prompt_n > 0 else 0

        avg_gen_tps = statistics.mean(gen_tps_list) if gen_tps_list else 0
        avg_ttft = statistics.mean(ttft_list) if ttft_list else 0

        return BenchmarkResult(
            backend="llama-cpp",
            model=os.path.basename(self.model_path) if isinstance(self.model_path, str) else "unknown",
            config={},
            prefill_tokens=results[0][1].get("timings", {}).get("prompt_n", 0),
            prefill_time_sec=statistics.mean(prefill_times) if prefill_times else 0,
            prefill_tps=avg_prefill_tps,
            gen_tokens=results[0][1].get("timings", {}).get("predicted_n", 0),
            gen_time_sec=statistics.mean(gen_times) if gen_times else 0,
            gen_tps=avg_gen_tps,
            ttft_ms=avg_ttft,
            raw_times=[r[0] for r in results],
        )


class OllamaBench:
    """Benchmark para Ollama API."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434"):
        self.base_url = base_url.rstrip("/")

    def benchmark(self, model: str, prompt: str, max_tokens: int = 128, n_runs: int = 5) -> BenchmarkResult:
        import urllib.request

        results = []
        for run in range(n_runs):
            url = f"{self.base_url}/api/generate"
            data = json.dumps({
                "model": model,
                "prompt": prompt,
                "options": {"num_predict": max_tokens, "temperature": 0.7},
                "stream": False,
            }).encode()

            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}
            )

            start = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode())
                elapsed = time.perf_counter() - start
                results.append((elapsed, result))
            except Exception as e:
                print(f"Error en run {run}: {e}")
                continue

        if not results:
            raise RuntimeError("No se obtuvieron resultados válidos de Ollama")

        # Ollama devuelve eval_count (tokens generados) y eval_duration (ns)
        gen_tps_list = []
        ttft_list = []

        for elapsed, result in results:
            eval_count = result.get("eval_count", 0)
            eval_duration = result.get("eval_duration", 0)  # nanosegundos
            if eval_duration > 0 and eval_count > 0:
                gen_tps_list.append(eval_count / (eval_duration / 1e9))

            # TTFT aproximado: total_duration - eval_duration
            total_dur = result.get("total_duration", 0)
            if total_dur > 0 and eval_duration > 0:
                ttft_list.append((total_dur - eval_duration) / 1e6)  # ms

        return BenchmarkResult(
            backend="ollama",
            model=model,
            config={},
            gen_tps=statistics.mean(gen_tps_list) if gen_tps_list else 0,
            ttft_ms=statistics.mean(ttft_list) if ttft_list else 0,
            raw_times=[r[0] for r in results],
        )


class OllaBench:
    """Benchmark para Olla proxy (ruta OpenAI real: /olla/proxy/v1)."""

    def __init__(self, base_url: str = "http://127.0.0.1:40114/olla/proxy/v1"):
        self.base_url = base_url.rstrip("/")

    def benchmark(self, model: str, prompt: str, max_tokens: int = 128, n_runs: int = 5) -> BenchmarkResult:
        import urllib.request

        results = []
        for run in range(n_runs):
            url = f"{self.base_url}/chat/completions"
            data = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.7,
                "stream": False,
            }).encode()

            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}
            )

            start = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode())
                elapsed = time.perf_counter() - start
                results.append((elapsed, result))
            except Exception as e:
                print(f"Error en run {run}: {e}")
                continue

        if not results:
            raise RuntimeError("No se obtuvieron resultados válidos de Olla")

        gen_tps_list = []
        ttft_list = []

        for elapsed, result in results:
            usage = result.get("usage", {})
            completion_tokens = usage.get("completion_tokens", 0)
            # OpenAI no da timing detallado; usar elapsed como proxy
            if completion_tokens > 0:
                gen_tps_list.append(completion_tokens / elapsed)
            ttft_list.append(elapsed * 1000)  # ms

        return BenchmarkResult(
            backend="olla",
            model=model,
            config={},
            gen_tps=statistics.mean(gen_tps_list) if gen_tps_list else 0,
            ttft_ms=statistics.mean(ttft_list) if ttft_list else 0,
            raw_times=[r[0] for r in results],
        )


def run_benchmark(
    backend: str,
    model: str,
    prompt: str = "Explica la fotosíntesis en detalle, cubriendo las fases luminosa y oscura, los pigmentos fotosintéticos, y la importancia ecológica del proceso.",
    max_tokens: int = 256,
    n_runs: int = 5,
    llama_cpp_args: Optional[List[str]] = None,
) -> BenchmarkResult:
    """Ejecuta benchmark según el backend especificado."""

    if backend == "llama-cpp":
        bench = LlamaCppBench()
        if not bench.start_server(model, llama_cpp_args or []):
            bench.stop_server()
            raise RuntimeError("No se pudo iniciar llama.cpp server")
        try:
            return bench.benchmark(prompt, max_tokens, n_runs)
        finally:
            bench.stop_server()

    elif backend == "ollama":
        bench = OllamaBench()
        return bench.benchmark(model, prompt, max_tokens, n_runs)

    elif backend == "olla":
        bench = OllaBench()
        return bench.benchmark(model, prompt, max_tokens, n_runs)

    else:
        raise ValueError(f"Backend desconocido: {backend}")


def main():
    parser = argparse.ArgumentParser(description="Benchmark llama.cpp / Ollama / Olla")
    parser.add_argument("--backend", choices=["llama-cpp", "ollama", "olla"], required=True,
                        help="Backend a benchmarkear")
    parser.add_argument("--model", required=True,
                        help="Ruta al modelo (llama-cpp) o nombre (ollama/olla)")
    parser.add_argument("--prompt", default=None, help="Prompt personalizado")
    parser.add_argument("--max-tokens", type=int, default=256, help="Tokens a generar")
    parser.add_argument("--runs", type=int, default=5, help="Número de ejecuciones")
    parser.add_argument("--output", help="Archivo JSON de salida")
    parser.add_argument("--llama-cpp-args", nargs="*", default=[],
                        help="Args adicionales para llama-server (ej: -ngl 999 -t 16)")

    args = parser.parse_args()

    prompt = args.prompt or (
        "Explica la fotosíntesis en detalle, cubriendo las fases luminosa y oscura, "
        "los pigmentos fotosintéticos, y la importancia ecológica del proceso."
    )

    print(f"=== Benchmark {args.backend} ===")
    print(f"Modelo: {args.model}")
    print(f"Prompt: {prompt[:80]}...")
    print(f"Max tokens: {args.max_tokens}")
    print(f"Runs: {args.runs}")
    print()

    try:
        result = run_benchmark(
            backend=args.backend,
            model=args.model,
            prompt=prompt,
            max_tokens=args.max_tokens,
            n_runs=args.runs,
            llama_cpp_args=args.llama_cpp_args,
        )

        print("=== RESULTADOS ===")
        print(f"Backend:      {result.backend}")
        print(f"Modelo:       {result.model}")
        print(f"Gen TPS:      {result.gen_tps:.2f} tokens/seg")
        print(f"TTFT:         {result.ttft_ms:.1f} ms")
        if result.prefill_tps > 0:
            print(f"Prefill TPS:  {result.prefill_tps:.2f} tokens/seg")
        print()

        if args.output:
            with open(args.output, "w") as f:
                json.dump(result.to_dict(), f, indent=2)
            print(f"Resultados guardados en {args.output}")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()