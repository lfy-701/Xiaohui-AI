"""存储层：SQLite 存文本（权威），Qdrant 存向量（可降级为本地暴力检索）。"""
from __future__ import annotations

import json
import sqlite3
import struct
import time
import uuid
from array import array
from typing import Any, Dict, List, Optional, Tuple

from .config import settings


# ---------------------------------------------------------------- SQLite

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS docs (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                title TEXT,
                created_at REAL NOT NULL,
                chunks INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                ord INTEGER NOT NULL,
                text TEXT NOT NULL,
                meta TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
            CREATE TABLE IF NOT EXISTS vectors (
                id TEXT PRIMARY KEY,
                dim INTEGER NOT NULL,
                vec BLOB NOT NULL
            );
            """
        )


def add_doc(source: str, title: str) -> str:
    doc_id = uuid.uuid4().hex[:16]
    with db() as conn:
        conn.execute(
            "INSERT INTO docs(id, source, title, created_at, chunks) VALUES (?,?,?,?,0)",
            (doc_id, source, title, time.time()),
        )
    return doc_id


def add_chunks(doc_id: str, texts: List[str], metas: Optional[List[dict]] = None) -> List[str]:
    ids: List[str] = []
    metas = metas or [{} for _ in texts]
    with db() as conn:
        for i, (t, m) in enumerate(zip(texts, metas)):
            cid = f"{doc_id}-{i}"
            conn.execute(
                "INSERT OR REPLACE INTO chunks(id, doc_id, ord, text, meta) VALUES (?,?,?,?,?)",
                (cid, doc_id, i, t, json.dumps(m, ensure_ascii=False)),
            )
            ids.append(cid)
        conn.execute("UPDATE docs SET chunks = ? WHERE id = ?", (len(texts), doc_id))
    return ids


def get_chunks(ids: List[str]) -> Dict[str, sqlite3.Row]:
    if not ids:
        return {}
    q = ",".join("?" * len(ids))
    with db() as conn:
        rows = conn.execute(
            f"SELECT c.*, d.source, d.title FROM chunks c JOIN docs d ON d.id = c.doc_id "
            f"WHERE c.id IN ({q})",
            ids,
        ).fetchall()
    return {r["id"]: r for r in rows}


def list_docs() -> List[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM docs ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def doc_chunks(doc_id: str) -> List[dict]:
    """按顺序返回一篇文档的所有切片，用于分段预览。"""
    with db() as conn:
        rows = conn.execute(
            "SELECT ord, text FROM chunks WHERE doc_id = ? ORDER BY ord", (doc_id,)
        ).fetchall()
    return [{"ord": r["ord"], "text": r["text"], "chars": len(r["text"] or "")} for r in rows]


def all_chunks() -> List[Tuple[str, str]]:
    """全部切片（id, 文本），关键词检索用。"""
    with db() as conn:
        rows = conn.execute("SELECT id, text FROM chunks").fetchall()
    return [(r["id"], r["text"]) for r in rows]


def delete_doc(doc_id: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM docs WHERE id = ?", (doc_id,))


# ---------------------------------------------------------------- 向量

def _pack(vec: List[float]) -> bytes:
    return array("f", vec).tobytes()


def _unpack(blob: bytes) -> List[float]:
    a = array("f")
    a.frombytes(blob)
    return a.tolist()


def _cosine(a: List[float], b: List[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return num / (na * nb) if na and nb else 0.0


class VectorStore:
    """Qdrant 优先；连不上就用 SQLite 暴力检索，保证服务永远可用。"""

    def __init__(self) -> None:
        self.backend = settings.vector_backend
        self._client = None
        self._ready = False

    def ensure(self, dim: int) -> str:
        if self._ready:
            return self.backend
        if self.backend == "qdrant":
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.http import models as qm

                self._client = QdrantClient(
                    url=settings.qdrant_url,
                    api_key=""
                    timeout=5,
                )
                if not self._client.collection_exists(settings.collection):
                    self._client.create_collection(
                        collection_name=settings.collection,
                        vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
                    )
                self._ready = True
                return self.backend
            except Exception:
                self.backend = "local"

        with db() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS vectors (id TEXT PRIMARY KEY, dim INTEGER NOT NULL, vec BLOB NOT NULL)"
            )
        self._ready = True
        return self.backend

    def upsert(self, ids: List[str], vectors: List[List[float]], payloads: List[dict]) -> None:
        self.ensure(len(vectors[0]) if vectors else 0)
        if self.backend == "qdrant":
            from qdrant_client.http import models as qm

            self._client.upsert(
                collection_name=settings.collection,
                points=[
                    qm.PointStruct(id=i, vector=v, payload=p)
                    for i, v, p in zip(ids, vectors, payloads)
                ],
            )
            return
        with db() as conn:
            for i, v in zip(ids, vectors):
                conn.execute(
                    "INSERT OR REPLACE INTO vectors(id, dim, vec) VALUES (?,?,?)",
                    (i, len(v), _pack(v)),
                )

    def search(self, vector: List[float], top_k: int) -> List[Tuple[str, float]]:
        self.ensure(len(vector))
        if self.backend == "qdrant":
            hits = self._client.search(
                collection_name=settings.collection,
                query_vector=vector,
                limit=top_k,
            )
            return [(str(h.id), float(h.score)) for h in hits]

        with db() as conn:
            rows = conn.execute("SELECT id, vec FROM vectors").fetchall()
        scored = [(r["id"], _cosine(vector, _unpack(r["vec"]))) for r in rows]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def delete(self, ids: List[str]) -> None:
        if not ids:
            return
        if self.backend == "qdrant" and self._client is not None:
            try:
                self._client.delete(
                    collection_name=settings.collection,
                    points_selector=ids,
                )
            except Exception:
                pass
            return
        with db() as conn:
            q = ",".join("?" * len(ids))
            conn.execute(f"DELETE FROM vectors WHERE id IN ({q})", ids)


vector_store = VectorStore()
