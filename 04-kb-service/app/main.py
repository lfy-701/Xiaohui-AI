"""小慧知识库 / 记忆服务 —— HTTP 接口。

给两个调用方用：
  1. 同学 A 的 LLM 服务：对话前查 /kb/search、/memory/{user_id}/prompt，对话后写 /memory/turn
  2. （可选）设备端 MCP 工具：直接 POST /kb/search
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from .chunk import parse_and_split
from .config import settings
from .embed import embedder
from .keyword import bm25_scores
from .memory import (
    build_memory_prompt,
    clear_facts,
    clear_turns,
    get_memory,
    init_memory,
    list_memory,
    remember_turn,
    search_memory,
)
from .store import (
    add_chunks,
    add_doc,
    all_chunks,
    delete_doc,
    doc_chunks,
    get_chunks,
    list_docs,
    vector_store,
)

app = FastAPI(title="小慧知识库与记忆", version="1.0.0")


# ---------------------------------------------------------------- 模型

class IngestTextReq(BaseModel):
    title: str = Field(..., description="文档标题")
    text: str = Field(..., description="正文")


class SearchReq(BaseModel):
    query: str
    top_k: int = 5


class TurnReq(BaseModel):
    user_id: str = "default"
    user: str
    assistant: str = ""
    # chat = 控制台试聊，voice = 设备语音对话
    source: str = "chat"


class MemorySearchReq(BaseModel):
    user_id: str = "default"
    query: str
    top_k: int = 5


# ---------------------------------------------------------------- 启动

@app.on_event("startup")
def _startup() -> None:
    init_memory()
    vector_store.ensure(embedder.dim)


@app.get("/health")
def health():
    return {
        "ok": True,
        "embed_backend": embedder.backend,
        "embed_dim": embedder.dim,
        "vector_backend": vector_store.backend,
        "llm_extract": bool(settings.llm_chat_url),
        "docs": len(list_docs()),
    }


# ---------------------------------------------------------------- 知识库

def _ingest(title: str, raw: bytes, filename: str) -> dict:
    _, chunks = parse_and_split(filename, raw)
    if not chunks:
        raise HTTPException(400, "没有解析出有效文本")

    doc_id = add_doc(source=filename, title=title)
    ids = add_chunks(doc_id, chunks)

    vectors = embedder.encode(chunks)
    vector_store.upsert(
        ids=ids,
        vectors=vectors,
        payloads=[{"doc_id": doc_id, "source": filename, "ord": i} for i in range(len(chunks))],
    )
    return {"doc_id": doc_id, "title": title, "chunks": len(chunks)}


@app.post("/kb/ingest")
async def ingest_file(file: UploadFile = File(...), title: Optional[str] = Form(None)):
    raw = await file.read()
    return _ingest(title or file.filename, raw, file.filename)


@app.post("/kb/ingest_text")
def ingest_text(req: IngestTextReq):
    return _ingest(req.title, req.text.encode("utf-8"), req.title + ".txt")


@app.get("/kb/docs")
def docs():
    return {"docs": list_docs()}


@app.get("/kb/docs/{doc_id}/chunks")
def docs_chunks(doc_id: str):
    """分段预览：按顺序返回切片原文。"""
    items = doc_chunks(doc_id)
    return {"doc_id": doc_id, "count": len(items), "chunks": items}


@app.delete("/kb/docs/{doc_id}")
def remove_doc(doc_id: str):
    delete_doc(doc_id)
    return {"deleted": doc_id}


@app.post("/kb/search")
def kb_search(req: SearchReq):
    """混合检索：向量 + 关键词（BM25）。

    - embedding 退化为 hash 时只用关键词（hash 相似度基本是噪声）
    - 真实 embedding 时两者加权融合
    """
    if not req.query.strip():
        return {"hits": []}

    kw = bm25_scores(req.query, all_chunks())
    vec: dict = {}
    if embedder.backend != "hash":
        vec_list = embedder.encode([req.query])[0]
        for cid, score in vector_store.search(vec_list, req.top_k * 3):
            if not cid.startswith("mem:"):
                vec[cid] = score

    if vec:
        merged = {cid: 0.7 * vec.get(cid, 0.0) + 0.3 * kw.get(cid, 0.0)
                  for cid in set(vec) | set(kw)}
    else:
        merged = kw

    ranked = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)[: max(req.top_k, 1)]
    rows = get_chunks([cid for cid, _ in ranked])
    hits = []
    for cid, score in ranked:
        r = rows.get(cid)
        if not r:
            continue
        hits.append({
            "text": r["text"],
            "score": round(float(score), 4),
            "doc_id": r["doc_id"],
            "source": r["source"],
            "title": r["title"],
            "ord": r["ord"],
        })
    return {"query": req.query, "hits": hits}


# ---------------------------------------------------------------- 记忆

@app.post("/memory/turn")
def memory_turn(req: TurnReq):
    return remember_turn(req.user_id, req.user, req.assistant, source=req.source)


@app.get("/memory/list")
def memory_list(limit: int = 100):
    """控制台记忆页：最近事实 + 最近对话（含语音/试聊来源）。"""
    return list_memory(limit)


@app.post("/memory/facts/clear")
def memory_facts_clear(user_id: str = ""):
    """清空长期记忆（facts）；对话轮次保留。"""
    return {"ok": True, "removed": clear_facts(user_id)}


@app.post("/memory/turns/clear")
def memory_turns_clear(user_id: str = ""):
    """清空「最近对话」列表；长期事实保留。"""
    n = clear_turns(user_id)
    return {"ok": True, "removed": n}


@app.get("/memory/{user_id}")
def memory_get(user_id: str):
    return get_memory(user_id)


@app.get("/memory/{user_id}/prompt")
def memory_prompt(user_id: str):
    return {"user_id": user_id, "prompt": build_memory_prompt(user_id)}


@app.post("/memory/search")
def memory_search(req: MemorySearchReq):
    return {"hits": search_memory(req.user_id, req.query, req.top_k)}
