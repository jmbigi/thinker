#!/usr/bin/env python3
"""Subsistema opt-in de optimización neural con PyTorch.

Modelos pequeños para validar mecánica, no para prometer calidad de producción.
Incluye destilación, LoRA, cuantización, poda, MoE, speculative decoding y VQ.
"""

import math
from typing import Any, Dict, Iterable, List

import torch
from torch import nn


class TinyAutoregressiveModel(nn.Module):
    """Transformer causal diminuto para pruebas reproducibles en CPU."""

    def __init__(self, vocab_size: int = 32, d_model: int = 16, max_len: int = 32):
        super().__init__()
        self.vocab_size = vocab_size
        self.max_len = max_len
        self.token = nn.Embedding(vocab_size, d_model)
        self.position = nn.Embedding(max_len, d_model)
        self.block = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=2, dim_feedforward=32,
            dropout=0.0, batch_first=True, norm_first=True)
        self.norm = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size)

    def forward(self, tokens):
        if tokens.ndim != 2 or tokens.size(1) > self.max_len:
            raise ValueError("Se esperaba [batch, seq] dentro de max_len")
        posiciones = torch.arange(tokens.size(1), device=tokens.device)
        x = self.token(tokens) + self.position(posiciones).unsqueeze(0)
        mascara = torch.triu(torch.full(
            (tokens.size(1), tokens.size(1)), float("-inf"), device=tokens.device), 1)
        return self.head(self.norm(self.block(x, src_mask=mascara)))


def sequences_from_lists(items: Iterable[Iterable[int]], vocab_size: int = 32) -> torch.Tensor:
    secuencias = [list(item) for item in items]
    if not secuencias or any(len(item) < 2 for item in secuencias):
        raise ValueError("Cada secuencia necesita al menos dos tokens")
    if any(token < 0 or token >= vocab_size for item in secuencias for token in item):
        raise ValueError("Token fuera del vocabulario")
    longitud = max(len(item) for item in secuencias)
    return torch.tensor([item + [0] * (longitud - len(item)) for item in secuencias],
                        dtype=torch.long)


def distill_teacher_student(teacher: TinyAutoregressiveModel,
                            student: TinyAutoregressiveModel,
                            sequences: torch.Tensor, epochs: int = 2,
                            lr: float = 0.001) -> List[float]:
    """Destilación real con distribuciones blandas del profesor."""
    if epochs < 1 or lr <= 0:
        raise ValueError("epochs/lr inválidos")
    optimizer = torch.optim.Adam(student.parameters(), lr=lr)
    history = []
    for _ in range(epochs):
        with torch.no_grad():
            teacher_probs = torch.softmax(teacher(sequences)[:, :-1, :], dim=-1)
        student_log_probs = torch.log_softmax(student(sequences)[:, :-1, :], dim=-1)
        loss = -(teacher_probs * student_log_probs).sum(dim=-1).mean()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        history.append(float(loss.detach()))
    return history


class LoRALinear(nn.Module):
    """Lineal congelado + adaptador A/B de bajo rango."""

    def __init__(self, base: nn.Linear, rank: int = 2, alpha: float = 1.0):
        super().__init__()
        if rank < 1 or alpha <= 0:
            raise ValueError("rank/alpha inválidos")
        self.base = base
        self.rank = rank
        self.alpha = alpha
        for param in self.base.parameters():
            param.requires_grad = False
        self.lora_a = nn.Parameter(torch.empty(rank, base.in_features))
        self.lora_b = nn.Parameter(torch.zeros(base.out_features, rank))
        nn.init.kaiming_uniform_(self.lora_a, a=math.sqrt(5))

    def forward(self, x):
        return self.base(x) + (x @ self.lora_a.T @ self.lora_b.T) * (self.alpha / self.rank)


def train_lora(model: TinyAutoregressiveModel, sequences: torch.Tensor,
               rank: int = 2, epochs: int = 2, lr: float = 0.01) -> Dict[str, Any]:
    """Entrena solo un adaptador LoRA de la cabeza de salida."""
    model.head = LoRALinear(model.head, rank=rank)
    for param in model.parameters():
        param.requires_grad = False
    for param in (model.head.lora_a, model.head.lora_b):
        param.requires_grad = True
    optimizer = torch.optim.Adam((model.head.lora_a, model.head.lora_b), lr=lr)
    history = []
    for _ in range(epochs):
        logits = model(sequences)
        loss = nn.functional.cross_entropy(
            logits[:, :-1, :].reshape(-1, model.vocab_size),
            sequences[:, 1:].reshape(-1))
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        history.append(float(loss.detach()))
    return {"history": history, "rank": rank,
            "adapter": {"a": model.head.lora_a.detach().clone(),
                        "b": model.head.lora_b.detach().clone()}}


class QuantizedLinear(nn.Module):
    """Pesos enteros simétricos INT8/INT4 con escala por matriz."""

    def __init__(self, base: nn.Linear, bits: int = 8):
        super().__init__()
        if bits not in (4, 8):
            raise ValueError("bits debe ser 4 u 8")
        self.bits = bits
        self.limite = 7 if bits == 4 else 127
        pesos = base.weight.detach()
        self.register_buffer("scale", pesos.abs().max().clamp_min(1e-12))
        self.register_buffer("weight_q", torch.round(
            pesos / self.scale * self.limite).clamp(-self.limite, self.limite).to(torch.int8))
        self.register_buffer("bias", base.bias.detach().clone() if base.bias is not None else None)

    def forward(self, x):
        pesos = self.weight_q.float() / self.limite * self.scale
        return x @ pesos.T + (self.bias if self.bias is not None else 0)

    def memory_bytes(self) -> Dict[str, float]:
        original = self.weight_q.numel() * 4
        comprimido = self.weight_q.numel() if self.bits == 8 else (self.weight_q.numel() + 1) // 2
        return {"float32": original, "compressed": comprimido,
                "savings_ratio": 1 - comprimido / original}


def quantize_linear(linear: nn.Linear, bits: int = 8) -> QuantizedLinear:
    return QuantizedLinear(linear, bits)


def prune_linear(linear: nn.Linear, amount: float = 0.2) -> nn.Linear:
    """Poda L1 real de pesos de una capa lineal."""
    if not 0 < amount < 1:
        raise ValueError("amount debe estar entre 0 y 1")
    from torch.nn.utils import prune
    prune.l1_unstructured(linear, name="weight", amount=amount)
    return linear


def sparsity(module: nn.Module) -> float:
    total = 0
    ceros = 0
    for child in module.modules():
        if isinstance(child, nn.Linear):
            total += child.weight.numel()
            ceros += int((child.weight.detach() == 0).sum())
    return ceros / total if total else 0.0


class TinyMixtureOfExperts(nn.Module):
    """MoE real: router top-1 por token, con dos expertos."""

    def __init__(self, d_model: int = 8, hidden: int = 16):
        super().__init__()
        self.experts = nn.ModuleList([
            nn.Sequential(nn.Linear(d_model, hidden), nn.ReLU(), nn.Linear(hidden, d_model))
            for _ in range(2)
        ])
        self.router = nn.Linear(d_model, 2)

    def forward(self, x):
        router_logits = self.router(x)
        probabilidades = torch.softmax(router_logits, dim=-1)
        indices = router_logits.argmax(dim=-1)
        salidas = torch.stack([expert(x) for expert in self.experts], dim=0)
        mascara = nn.functional.one_hot(indices, 2).permute(2, 0, 1).unsqueeze(-1)
        pesos = probabilidades.gather(-1, indices.unsqueeze(-1)).permute(2, 0, 1).unsqueeze(-1)
        elegida = (salidas * mascara * pesos).sum(dim=0)
        return elegida, indices, probabilidades


def _next_greedy(model, tokens: torch.Tensor) -> int:
    with torch.no_grad():
        return int(model(tokens)[0, -1].argmax())


def greedy_decode(model, prefix: Iterable[int], steps: int) -> List[int]:
    tokens = list(prefix)
    for _ in range(steps):
        tokens.append(_next_greedy(model, torch.tensor([tokens], dtype=torch.long)))
    return tokens


def speculative_decode(target, draft, prefix: Iterable[int], steps: int,
                       draft_k: int = 2) -> Dict[str, Any]:
    """Decodificación especulativa verificada; greedy equivale al target."""
    if steps < 1 or draft_k < 1:
        raise ValueError("steps/draft_k inválidos")
    tokens = list(prefix)
    target_calls = 0
    draft_calls = 0
    aceptados = 0
    while len(tokens) < len(prefix) + steps:
        propuestas = []
        contexto = list(tokens)
        for _ in range(draft_k):
            if len(contexto) >= len(prefix) + steps:
                break
            siguiente = _next_greedy(draft, torch.tensor([contexto], dtype=torch.long))
            draft_calls += 1
            propuestas.append(siguiente)
            contexto.append(siguiente)
        with torch.no_grad():
            logits = target(torch.tensor([contexto], dtype=torch.long))
        target_calls += 1
        base = len(tokens) - 1
        parada = False
        for indice, propuesta in enumerate(propuestas):
            objetivo = int(logits[0, base + indice].argmax())
            if objetivo == propuesta:
                tokens.append(propuesta)
                aceptados += 1
            else:
                tokens.append(objetivo)
                parada = True
                break
        if parada:
            break
    esperados = len(prefix) + steps
    return {"tokens": tokens[:esperados], "target_calls": target_calls,
            "draft_calls": draft_calls, "accepted_draft": aceptados}


class ResidualVectorQuantizer:
    """VQ residual jerárquica con codebooks discretos y reconstrucción."""

    def __init__(self, dim: int, codebook_sizes=(4, 4, 4)):
        if dim < 1 or not codebook_sizes or any(size < 1 for size in codebook_sizes):
            raise ValueError("dim/codebooks inválidos")
        self.dim = dim
        self.codebooks = []
        for size in codebook_sizes:
            self.codebooks.append(torch.zeros(size, dim))

    @staticmethod
    def _asignar(vectores, codebook):
        distancias = torch.cdist(vectores, codebook)
        indices = distancias.argmin(dim=1)
        return indices, codebook[indices]

    def fit(self, vectores: torch.Tensor, iterations: int = 5):
        if vectores.ndim != 2 or vectores.size(1) != self.dim or len(vectores) < 2:
            raise ValueError("Vectores con forma incompatible")
        residual = vectores.float().clone()
        for nivel, codebook in enumerate(self.codebooks):
            if len(codebook) > len(residual):
                raise ValueError("Codebook mayor que el número de vectores")
            indices = torch.linspace(0, len(residual) - 1, len(codebook)).long()
            codebook.copy_(residual[indices])
            for _ in range(iterations):
                asignaciones, centroides = self._asignar(residual, codebook)
                for indice in range(len(codebook)):
                    mascara = asignaciones == indice
                    if mascara.any():
                        codebook[indice] = residual[mascara].mean(dim=0)
            residual = residual - centroides
        return self

    def encode(self, vectores: torch.Tensor) -> List[torch.Tensor]:
        residual = vectores.float().clone()
        niveles = []
        for codebook in self.codebooks:
            indices, centroides = self._asignar(residual, codebook)
            niveles.append(indices)
            residual = residual - centroides
        return niveles

    def decode(self, niveles: List[torch.Tensor]) -> torch.Tensor:
        if len(niveles) != len(self.codebooks):
            raise ValueError("Número de niveles incorrecto")
        return sum((codebook[indices] for codebook, indices in zip(self.codebooks, niveles)),
                   torch.zeros(niveles[0].size(0), self.dim))

    def mse(self, vectores: torch.Tensor) -> float:
        return float((vectores - self.decode(self.encode(vectores))).pow(2).mean())
