"""Embedding：三种后端，优先级 ollama > sentence_transformers > hash。

hash 后端是确定性哈希向量，只为「没装模型也能跑通链路」，
真实语义检索请用 ollama 或 sentence_transformers。
"""
from __future__ import annotations

import hashlib
import math
from typing import List

import httpx

from .config import settings


class Embedder:
    def __init__(self) -> None:
        self.backend = settings.embed_backend
        self._st_model = None

        if self.backend == "sentence_transformers":
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
                self._st_model = SentenceTransformer(
                    settings.embed_model if "nomic" not in settings.embed_model
                    else "BAAI/bge-small-zh-v1.5"
                )
            except Exception:
                self.backend = "hash"

    @property
    def dim(self) -> int:
        if self.backend == "hash":
            return 256
        return settings.embed_dim

    def encode(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if self.backend == "ollama":
            try:
                return self._encode_ollama(texts)
            except Exception:
                # ollama 不可用就退化，不要让整个服务挂掉
                self.backend = "hash"
        if self.backend == "sentence_transformers" and self._st_model is not None:
            vecs = self._st_model.encode(texts, normalize_embeddings=True)
            return [v.tolist() for v in vecs]
        return [self._encode_hash(t) for t in texts]

    def _encode_ollama(self, texts: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        with httpx.Client(timeout=60.0) as client:
            for t in texts:
                r = client.post(
                    f"{settings.ollama_url}/api/embeddings",
                    json={"model": settings.embed_model, "prompt": t},
                )
                r.raise_for_status()
                out.append(r.json()["embedding"])
        return out

    @staticmethod
    def _encode_hash(text: str) -> List[float]:
        """确定性哈希向量：把词哈希到 256 维，归一化。仅用于打通链路。"""
        dim = 256
        vec = [0.0] * dim
        for token in text.lower().split():
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            vec[h % dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


embedder = Embedder()
