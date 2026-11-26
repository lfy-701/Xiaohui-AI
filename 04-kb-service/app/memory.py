"""长期记忆：自动提取 → 分类 → 冲突消解 → 语义检索。

存储：SQLite
  facts          当前有效事实（active=1）
  fact_history   事实变更历史（谁被谁取代）
  turns          原始对话轮次（供语义检索 / 摘要）
"""
from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx

from .config import settings
from .embed import embedder
from .store import db, init_db, vector_store

MEM_PREFIX = "mem"

# ---------------------------------------------------------------- 表结构

def init_memory() -> None:
    init_db()
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS facts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                slot TEXT NOT NULL,
                value TEXT NOT NULL,
                kind TEXT DEFAULT 'other',
                confidence REAL DEFAULT 0.6,
                source_turn TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                active INTEGER DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_facts_user ON facts(user_id, active);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_facts_slot
                ON facts(user_id, slot) WHERE active = 1;

            CREATE TABLE IF NOT EXISTS fact_history (
                id TEXT PRIMARY KEY,
                fact_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                slot TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                reason TEXT,
                at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS turns (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                user_text TEXT,
                assistant_text TEXT,
                source TEXT DEFAULT 'chat',
                at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_turns_user ON turns(user_id, at);
            """
        )
        # 老库补列：事实本身也记来源（turns 被清空后仍能看出是不是语音来的）
        fcols = [r[1] for r in conn.execute("PRAGMA table_info(facts)").fetchall()]
        if "source" not in fcols:
            conn.execute("ALTER TABLE facts ADD COLUMN source TEXT DEFAULT 'chat'")
        # 老库补列：source 用来区分「语音对话」和「控制台试聊」
        cols = [r[1] for r in conn.execute("PRAGMA table_info(turns)").fetchall()]
        if "source" not in cols:
            conn.execute("ALTER TABLE turns ADD COLUMN source TEXT DEFAULT 'chat'")


# ---------------------------------------------------------------- 抽取

# 槽位规则：(正则, slot 模板, kind, 置信度)
_RULES = [
    (r"我(?:的名字)?叫\s*([^\s，。,.！!？?]{1,12})", "name", "identity", 0.95),
    (r"我的名字是\s*([^\s，。,.！!？?]{1,12})", "name", "identity", 0.95),
    (r"我(?:今年)?\s*(\d{1,2})\s*岁", "age", "identity", 0.9),
    (r"我住在\s*([^\s，。,.！!？?]{1,20})", "location", "location", 0.85),
    (r"我(?:已经)?搬(?:家)?到\s*([^\s，。,.！!？?了]{1,20})", "location", "location", 0.9),
    (r"我现在(?:住|人在)\s*([^\s，。,.！!？?]{1,20})", "location", "location", 0.88),
    (r"我(?:在|是)\s*([^\s，。,.！!？?]{2,20})\s*(?:上班|工作|读书)", "workplace", "identity", 0.8),
    (r"我(?:很)?喜欢\s*([^\s，。,.！!？?]{1,20})", "preference:{0}", "preference", 0.8),
    (r"我(?:很)?讨厌\s*([^\s，。,.！!？?]{1,20})", "dislike:{0}", "preference", 0.8),
    (r"我(?:养了|有一只)\s*([^\s，。,.！!？?]{1,12})", "pet", "identity", 0.8),
    (r"我(?:的)?生日(?:是)?\s*([0-9]{1,2}\s*月\s*[0-9]{1,2}\s*日?)", "birthday", "identity", 0.9),
    (r"记住[：:，,]?\s*(.{2,60})", "note:{0}", "note", 0.7),
]


_QUESTION_WORDS = ("什么", "啥", "谁", "哪", "怎么", "多少", "几", "吗", "呢", "是不是")


def extract_facts(text: str) -> List[Dict[str, Any]]:
    """规则抽取；同时尝试用 LLM 抽取（配置了 LLM_CHAT_URL 才走）。"""
    facts: List[Dict[str, Any]] = []
    seen = set()

    for pattern, slot_tpl, kind, conf in _RULES:
        for m in re.finditer(pattern, text):
            value = m.group(1).strip()
            if not value:
                continue
            # 「我叫什么名字？」这类疑问句不是事实，不能入库——
            # 否则会抽出 name=什么名字，把真实的「小明」覆盖掉。
            if any(q in value for q in _QUESTION_WORDS):
                continue
            if m.group(0).rstrip().endswith(("？", "?")):
                continue
            slot = slot_tpl.format(value) if "{" in slot_tpl else slot_tpl
            key = (slot, value)
            if key in seen:
                continue
            seen.add(key)
            facts.append({
                "slot": slot,
                "value": value,
                "kind": kind,
                "confidence": conf,
                "evidence": m.group(0),
            })

    llm_facts = _extract_with_llm(text)
    for f in llm_facts:
        key = (f["slot"], f["value"])
        if key in seen:
            continue
        seen.add(key)
        facts.append(f)

    return facts


def _extract_with_llm(text: str) -> List[Dict[str, Any]]:
    if not settings.llm_chat_url:
        return []
    prompt = (
        "从下面这句话里抽取关于说话人本人的长期事实。只输出 JSON 数组，"
        '元素格式 {"slot":"name|age|location|pet|preference:xx|note:xx","value":"...","confidence":0.0-1.0}。'
        "没有就输出 []。\n\n句子：" + text
    )
    try:
        with httpx.Client(timeout=settings.llm_timeout) as client:
            r = client.post(settings.llm_chat_url, json={
                "session_id": "memory-extract",
                "text": prompt,
                "system": "你是一个只输出 JSON 的信息抽取器。",
            })
            r.raise_for_status()
            raw = r.text
        m = re.search(r"\[.*\]", raw, re.S)
        if not m:
            return []
        arr = json.loads(m.group(0))
        out = []
        for it in arr:
            if not isinstance(it, dict) or "slot" not in it or "value" not in it:
                continue
            out.append({
                "slot": str(it["slot"]),
                "value": str(it["value"]),
                "kind": str(it.get("kind", "other")),
                "confidence": float(it.get("confidence", 0.7)),
                "evidence": "llm",
            })
        return out
    except Exception:
        return []


# ---------------------------------------------------------------- 冲突消解

def upsert_fact(user_id: str, fact: Dict[str, Any], source_turn: str,
                source: str = "chat") -> Dict[str, Any]:
    """同槽位已有值：新值更高置信度 → 取代；否则忽略并记历史。"""
    now = time.time()
    slot = fact["slot"]
    value = fact["value"]
    conf = float(fact.get("confidence", 0.6))

    with db() as conn:
        row = conn.execute(
            "SELECT * FROM facts WHERE user_id=? AND slot=? AND active=1",
            (user_id, slot),
        ).fetchone()

        if row is None:
            fid = uuid.uuid4().hex[:16]
            conn.execute(
                "INSERT INTO facts(id,user_id,slot,value,kind,confidence,source_turn,source,created_at,updated_at,active)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,1)",
                (fid, user_id, slot, value, fact.get("kind", "other"), conf, source_turn, source, now, now),
            )
            return {"action": "added", "fact_id": fid, "slot": slot, "value": value}

        if row["value"] == value:
            conn.execute(
                "UPDATE facts SET confidence=MAX(confidence,?), updated_at=? WHERE id=?",
                (conf, now, row["id"]),
            )
            return {"action": "confirmed", "fact_id": row["id"], "slot": slot, "value": value}

        if conf >= float(row["confidence"]):
            conn.execute("UPDATE facts SET active=0, updated_at=? WHERE id=?", (now, row["id"]))
            fid = uuid.uuid4().hex[:16]
            conn.execute(
                "INSERT INTO facts(id,user_id,slot,value,kind,confidence,source_turn,source,created_at,updated_at,active)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,1)",
                (fid, user_id, slot, value, fact.get("kind", "other"), conf, source_turn, source, now, now),
            )
            conn.execute(
                "INSERT INTO fact_history(id,fact_id,user_id,slot,old_value,new_value,reason,at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex[:16], row["id"], user_id, slot, row["value"], value, "superseded", now),
            )
            return {"action": "superseded", "fact_id": fid, "slot": slot,
                    "old_value": row["value"], "value": value}

        conn.execute(
            "INSERT INTO fact_history(id,fact_id,user_id,slot,old_value,new_value,reason,at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (uuid.uuid4().hex[:16], row["id"], user_id, slot, row["value"], value, "rejected_lower_confidence", now),
        )
        return {"action": "ignored", "fact_id": row["id"], "slot": slot, "value": row["value"]}


# ---------------------------------------------------------------- 对外接口

def remember_turn(user_id: str, user_text: str, assistant_text: str = "",
                  source: str = "chat") -> Dict[str, Any]:
    turn_id = uuid.uuid4().hex[:16]
    now = time.time()
    source = (source or "chat").strip().lower()
    with db() as conn:
        conn.execute(
            "INSERT INTO turns(id,user_id,user_text,assistant_text,source,at) VALUES (?,?,?,?,?,?)",
            (turn_id, user_id, user_text, assistant_text, source, now),
        )

    results = []
    if user_text:
        for f in extract_facts(user_text):
            results.append(upsert_fact(user_id, f, turn_id, source=source))

    # 对话轮次也进向量库，便于"我上次说过什么"这类检索
    try:
        vec = embedder.encode([f"{user_text}\n{assistant_text}"])[0]
        vector_store.upsert(
            ids=[f"{MEM_PREFIX}:{turn_id}"],
            vectors=[vec],
            payloads=[{"kind": "turn", "user_id": user_id, "turn_id": turn_id}],
        )
    except Exception:
        pass

    return {"turn_id": turn_id, "facts": results}


def get_memory(user_id: str, limit: int = 50, recent: int = 20) -> Dict[str, Any]:
    with db() as conn:
        facts = conn.execute(
            "SELECT f.slot, f.value, f.kind, f.confidence, f.updated_at, "
            "       COALESCE(f.source, 'chat') AS source "
            "FROM facts f "
            "WHERE f.user_id=? AND f.active=1 ORDER BY f.updated_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        turns = conn.execute(
            "SELECT id, user_text, assistant_text, source, at FROM turns "
            "WHERE user_id=? ORDER BY at DESC LIMIT ?",
            (user_id, recent),
        ).fetchall()
        by_source = conn.execute(
            "SELECT COALESCE(source,'chat') AS source, COUNT(*) AS n FROM turns "
            "WHERE user_id=? GROUP BY COALESCE(source,'chat')",
            (user_id,),
        ).fetchall()
    return {
        "user_id": user_id,
        "facts": [dict(f) for f in facts],
        "recent_turns": [dict(t) for t in turns],
        "turn_count": sum(int(r["n"]) for r in by_source) if by_source else 0,
        "turn_by_source": {r["source"]: int(r["n"]) for r in by_source},
    }


def clear_facts(user_id: str = "") -> int:
    """清空长期事实（含变更历史）；对话轮次不动。"""
    with db() as conn:
        if user_id:
            n = conn.execute(
                "SELECT COUNT(*) FROM facts WHERE user_id=?", (user_id,)
            ).fetchone()[0]
            conn.execute("DELETE FROM fact_history WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM facts WHERE user_id=?", (user_id,))
        else:
            n = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
            conn.execute("DELETE FROM fact_history")
            conn.execute("DELETE FROM facts")
        return int(n or 0)


def clear_turns(user_id: str = "") -> int:
    """清空对话轮次（可只清某个用户）；长期事实 facts 不动。"""
    with db() as conn:
        if user_id:
            cur = conn.execute("DELETE FROM turns WHERE user_id=?", (user_id,))
        else:
            cur = conn.execute("DELETE FROM turns")
        return cur.rowcount or 0


def list_memory(limit: int = 100) -> Dict[str, Any]:
    """控制台「记忆」页用：最近的事实 + 最近的对话轮次（带来源）。"""
    with db() as conn:
        facts = conn.execute(
            "SELECT f.slot, f.value, f.kind, f.confidence, f.updated_at, "
            "       COALESCE(f.source,'chat') AS source "
            "FROM facts f "
            "WHERE f.active=1 ORDER BY f.updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        turns = conn.execute(
            "SELECT id, user_id, user_text, assistant_text, source, at FROM turns "
            "ORDER BY at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return {"facts": [dict(f) for f in facts], "turns": [dict(t) for t in turns]}


def search_memory(user_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    vec = embedder.encode([query])[0]
    hits = vector_store.search(vec, top_k * 3)
    out = []
    for id_, score in hits:
        if not id_.startswith(f"{MEM_PREFIX}:"):
            continue
        turn_id = id_.split(":", 1)[1]
        with db() as conn:
            row = conn.execute(
                "SELECT user_text, assistant_text, at FROM turns WHERE id=? AND user_id=?",
                (turn_id, user_id),
            ).fetchone()
        if row:
            out.append({
                "text": row["user_text"],
                "assistant": row["assistant_text"],
                "at": row["at"],
                "score": score,
            })
        if len(out) >= top_k:
            break
    return out


def build_memory_prompt(user_id: str) -> str:
    """给 LLM 拼一段“你记得用户什么”的上下文。"""
    mem = get_memory(user_id)
    if not mem["facts"]:
        return ""
    lines = ["【已知的用户信息】"]
    for f in mem["facts"]:
        lines.append(f"- {f['slot']}: {f['value']}")
    return "\n".join(lines)
