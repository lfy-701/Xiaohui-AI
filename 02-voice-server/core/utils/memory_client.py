"""把语音对话写进长期记忆（知识库服务的 /memory/turn）。

背景：控制台「记忆」页读的是知识库的 facts，而 facts 只有控制台「试聊」
在写；设备上的语音对话从来没进过记忆。这里补上语音这一路，
并在 turns 表里标 source=voice，和试聊区分开。

调用是后台线程 + 短超时，失败只丢这一轮记忆，绝不阻塞或影响播报。
"""
import os
import threading

import httpx

_DEFAULT_KB = "http://127.0.0.1:8077"


def kb_url() -> str:
    return (os.getenv("KB_URL") or _DEFAULT_KB).rstrip("/")


def memory_user_id() -> str:
    return (os.getenv("MEMORY_USER_ID") or "default").strip() or "default"


def fetch_memory_prompt(timeout: float = 5.0) -> str:
    """取「你记得用户什么」的提示词片段；失败返回空串。"""
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(f"{kb_url()}/memory/{memory_user_id()}/prompt")
            if r.status_code == 200:
                return (r.json().get("prompt") or "").strip()
    except Exception:
        pass
    return ""


def record_turn(user_text: str, assistant_text: str, source: str = "voice") -> None:
    """异步写一轮对话；不抛异常、不阻塞。"""
    user_text = (user_text or "").strip()
    assistant_text = (assistant_text or "").strip()
    if not user_text:
        return

    payload = {
        "user_id": memory_user_id(),
        "user": user_text,
        "assistant": assistant_text,
        "source": source,
    }
    url = kb_url() + "/memory/turn"

    def _run():
        try:
            with httpx.Client(timeout=8.0) as c:
                c.post(url, json=payload)
        except Exception:
            pass

    threading.Thread(target=_run, name="memory-turn", daemon=True).start()
