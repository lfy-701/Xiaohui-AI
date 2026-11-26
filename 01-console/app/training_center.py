"""训练数据审查中心：读取 review_queue.jsonl + review_state.sqlite3。

数据目录通过 XIAOHUI_LLM_ROOT 指定，默认 D:\\AI-Companion-shared\\Xiaohui-LLM，
审核数据在 <ROOT>\\datasets\\review 下。数据缺失时返回空态而不是报错。
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/training-center", tags=["training-center"])

DEFAULT_ROOT = Path(r"D:\AI-Companion-shared\Xiaohui-LLM")


def _review_dir() -> Path:
    root = os.getenv("XIAOHUI_LLM_ROOT")
    base = Path(root) if root else DEFAULT_ROOT
    return base / "datasets" / "review"


def _queue_file() -> Path:
    return _review_dir() / "review_queue.jsonl"


def _state_file() -> Path:
    return _review_dir() / "review_state.sqlite3"


def _load_samples() -> List[Dict[str, Any]]:
    f = _queue_file()
    if not f.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with f.open("r", encoding="utf-8") as fp:
            for i, line in enumerate(fp):
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                item.setdefault("id", item.get("sample_id") or f"s{i}")
                out.append(item)
    except Exception:
        return []
    return out


def _load_state() -> Dict[str, Dict[str, Any]]:
    """从 sqlite 读审核状态，返回 {sample_id: row}。"""
    f = _state_file()
    if not f.exists():
        return {}
    try:
        conn = sqlite3.connect(f"file:{f}?mode=ro", uri=True, timeout=3)
    except Exception:
        return {}
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        target = None
        for t in tables:
            cols = [c[1] for c in conn.execute(f"PRAGMA table_info({t})")]
            if any(c in cols for c in ("sample_id", "id")) and \
               any("status" in c for c in cols):
                target = t
                break
        if not target:
            return {}
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({target})")]
        rows = conn.execute(f"SELECT * FROM {target}").fetchall()
        result: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            d = dict(zip(cols, row))
            key = str(d.get("sample_id") or d.get("id") or "")
            if key:
                result[key] = d
        return result
    except Exception:
        return {}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _merged() -> List[Dict[str, Any]]:
    samples = _load_samples()
    state = _load_state()
    for s in samples:
        key = str(s.get("id"))
        st = state.get(key) or {}
        for k in ("status", "reviewer", "reviewed_at", "note"):
            if st.get(k) is not None:
                s[k] = st[k]
        s.setdefault("status", "pending")
    return samples


@router.get("/overview")
def overview():
    rd = _review_dir()
    samples = _merged()
    status_count: Dict[str, int] = {}
    cat_count: Dict[str, int] = {}
    warn = 0
    for s in samples:
        status_count[str(s.get("status") or "pending")] = \
            status_count.get(str(s.get("status") or "pending"), 0) + 1
        c = str(s.get("category") or s.get("kind") or "未分类")
        cat_count[c] = cat_count.get(c, 0) + 1
        if s.get("safety_warnings") or s.get("warnings"):
            warn += 1

    return {
        "ok": True,
        "ready": _queue_file().exists(),
        "review_dir": str(rd),
        "queue_exists": _queue_file().exists(),
        "state_exists": _state_file().exists(),
        "summary": {
            "total": len(samples),
            "status": status_count,
            "categories": cat_count,
            "safety_warnings": warn,
        },
    }


@router.get("/samples")
def samples(status: Optional[str] = None,
            category: Optional[str] = None,
            q: Optional[str] = None,
            limit: int = Query(100, ge=1, le=500)):
    items = _merged()
    if status:
        items = [s for s in items if str(s.get("status")) == status]
    if category:
        items = [s for s in items if str(s.get("category") or s.get("kind")) == category]
    if q:
        kw = q.lower()
        items = [s for s in items
                 if kw in json.dumps(s, ensure_ascii=False).lower()]
    return {"ok": True, "total": len(items), "items": items[:limit]}


@router.get("/sources")
def sources():
    items = _merged()
    agg: Dict[str, int] = {}
    for s in items:
        src = str(s.get("source") or s.get("from") or "未知来源")
        agg[src] = agg.get(src, 0) + 1
    return {"ok": True,
            "sources": [{"name": k, "count": v}
                        for k, v in sorted(agg.items(), key=lambda x: -x[1])]}


@router.get("/backups")
def backups():
    d = _review_dir()
    out = []
    if d.exists():
        for p in sorted(d.glob("*.sqlite3*"), key=lambda x: -x.stat().st_mtime)[:20]:
            st = p.stat()
            out.append({"name": p.name,
                        "size": st.st_size,
                        "at": time.strftime("%Y-%m-%d %H:%M:%S",
                                            time.localtime(st.st_mtime))})
    return {"ok": True, "backups": out}


@router.post("/backup")
def make_backup():
    src = _state_file()
    if not src.exists():
        raise HTTPException(503, "审核数据库不存在，无法备份")
    dst = src.with_name(
        f"review_state.{time.strftime('%Y%m%d-%H%M%S')}.sqlite3")
    try:
        shutil.copy2(src, dst)
    except Exception as e:
        raise HTTPException(500, f"备份失败：{e}")
    return {"ok": True, "file": dst.name}

# ---------------- 审核操作 ----------------

def _rw_connect():
    f = _state_file()
    if not f.exists():
        raise HTTPException(503, "审核数据库不存在")
    try:
        conn = sqlite3.connect(str(f), timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    except Exception as e:
        raise HTTPException(503, f"无法打开审核数据库：{e}")


@router.get("/sample/{sample_id}")
def sample_detail(sample_id: str):
    for s in _merged():
        if str(s.get("id")) == sample_id:
            return {"ok": True, "sample": s}
    raise HTTPException(404, "样本不存在")


@router.post("/review")
async def review_sample(request: Request):
    """审核一条样本：{"sample_id": "...", "status": "approved", "note": "..."}"""
    import json as _json
    import time as _time

    body = await request.json()
    sid = str(body.get("sample_id") or "").strip()
    status = str(body.get("status") or "").strip()
    note = str(body.get("note") or "").strip()
    reviewer = str(body.get("reviewer") or "控制台").strip()

    if not sid:
        raise HTTPException(400, "缺少 sample_id")
    if status not in ("pending", "approved", "rejected", "flagged"):
        raise HTTPException(400, "status 只能是 pending/approved/rejected/flagged")

    conn = _rw_connect()
    try:
        cur = conn.cursor()
        cols = [c[1] for c in cur.execute("PRAGMA table_info(samples)")]
        sets = ["status=?"]
        vals = [status]
        if "reviewer" in cols:
            sets.append("reviewer=?")
            vals.append(reviewer)
        if "reviewed_at" in cols:
            sets.append("reviewed_at=?")
            vals.append(_time.strftime("%Y-%m-%d %H:%M:%S"))
        if "reviewer_notes" in cols and note:
            sets.append("reviewer_notes=?")
            vals.append(note)
        if "updated_at" in cols:
            sets.append("updated_at=?")
            vals.append(_time.strftime("%Y-%m-%d %H:%M:%S"))
        vals.append(sid)
        cur.execute(f"UPDATE samples SET {', '.join(sets)} WHERE sample_id=?", vals)
        changed = cur.rowcount
        if not changed:
            conn.rollback()
            raise HTTPException(404, f"数据库里没有样本 {sid}")

        # 记一条修订历史
        try:
            rcols = [c[1] for c in cur.execute("PRAGMA table_info(revisions)")]
            if rcols:
                payload = {}
                if "sample_id" in rcols:
                    payload["sample_id"] = sid
                if "created_at" in rcols:
                    payload["created_at"] = _time.strftime("%Y-%m-%d %H:%M:%S")
                if "action" in rcols:
                    payload["action"] = status
                if "reason" in rcols:
                    payload["reason"] = note
                if "reviewer" in rcols:
                    payload["reviewer"] = reviewer
                if "new_values_json" in rcols:
                    payload["new_values_json"] = _json.dumps(
                        {"status": status}, ensure_ascii=False)
                keys = ",".join(payload.keys())
                marks = ",".join("?" * len(payload))
                cur.execute(f"INSERT INTO revisions ({keys}) VALUES ({marks})",
                            list(payload.values()))
        except Exception:
            pass

        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return {"ok": True, "sample_id": sid, "status": status}


@router.get("/export")
def export_samples(status: str = "approved"):
    """导出指定状态的样本为 JSONL（给训练用）。"""
    items = [s for s in _merged() if str(s.get("status")) == status]
    if not items:
        raise HTTPException(404, f"没有状态为 {status} 的样本")
    lines = []
    for s in items:
        row = {
            "sample_id": s.get("id"),
            "category": s.get("category"),
            "source": s.get("source"),
            "messages": s.get("messages"),
            "text": s.get("text"),
        }
        lines.append(json.dumps(row, ensure_ascii=False))
    body = "\n".join(lines)
    from fastapi.responses import Response
    name = f"review-{status}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    return Response(content=body, media_type="application/jsonl",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})

@router.post("/review-batch")
async def review_batch(request: Request):
    """批量审核：{"sample_ids": [...], "status": "approved", "note": ""}"""
    import json as _json
    import time as _time

    body = await request.json()
    ids = body.get("sample_ids") or []
    status = str(body.get("status") or "").strip()
    note = str(body.get("note") or "").strip()
    reviewer = str(body.get("reviewer") or "控制台").strip()

    if not isinstance(ids, list) or not ids:
        raise HTTPException(400, "缺少 sample_ids")
    if status not in ("pending", "approved", "rejected", "flagged"):
        raise HTTPException(400, "status 只能是 pending/approved/rejected/flagged")

    conn = _rw_connect()
    ok = 0
    failed = []
    try:
        cur = conn.cursor()
        cols = [c[1] for c in cur.execute("PRAGMA table_info(samples)")]
        now = _time.strftime("%Y-%m-%d %H:%M:%S")
        for sid in ids:
            sid = str(sid).strip()
            if not sid:
                continue
            sets = ["status=?"]
            vals = [status]
            if "reviewer" in cols:
                sets.append("reviewer=?")
                vals.append(reviewer)
            if "reviewed_at" in cols:
                sets.append("reviewed_at=?")
                vals.append(now)
            if "reviewer_notes" in cols and note:
                sets.append("reviewer_notes=?")
                vals.append(note)
            if "updated_at" in cols:
                sets.append("updated_at=?")
                vals.append(now)
            vals.append(sid)
            try:
                cur.execute(f"UPDATE samples SET {', '.join(sets)} WHERE sample_id=?", vals)
                if cur.rowcount:
                    ok += 1
                else:
                    failed.append(sid)
            except Exception:
                failed.append(sid)

        # 批量修订记录
        try:
            rcols = [c[1] for c in cur.execute("PRAGMA table_info(revisions)")]
            if rcols:
                for sid in ids[:ok]:
                    payload = {}
                    if "sample_id" in rcols:
                        payload["sample_id"] = str(sid)
                    if "created_at" in rcols:
                        payload["created_at"] = now
                    if "action" in rcols:
                        payload["action"] = status
                    if "reason" in rcols:
                        payload["reason"] = note
                    if "reviewer" in rcols:
                        payload["reviewer"] = reviewer
                    if "new_values_json" in rcols:
                        payload["new_values_json"] = _json.dumps(
                            {"status": status, "batch": True}, ensure_ascii=False)
                    keys = ",".join(payload.keys())
                    marks = ",".join("?" * len(payload))
                    cur.execute(f"INSERT INTO revisions ({keys}) VALUES ({marks})",
                                list(payload.values()))
        except Exception:
            pass

        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return {"ok": True, "updated": ok, "failed": failed, "status": status}
