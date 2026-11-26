"""大模型接入层：Ollama / OpenAI 兼容接口（含 SSE 流式）/ 未接入。

环境变量：
  LLM_PROVIDER=ollama | openai | none
  OLLAMA_URL=http://127.0.0.1:11434
  LLM_CHAT_URL=http://host:8000/v1/chat/completions   ← 完整路径
                或 http://host:8000/v1
                或 http://host:8000                   ← base URL 也认
  LLM_API_KEY=""

URL 会自动归一化，三种写法都支持（成员 A 建议里提到的兼容问题）。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Generator, List, Tuple

import httpx

PROVIDER = os.getenv("LLM_PROVIDER", "none").lower()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
CHAT_URL = os.getenv("LLM_CHAT_URL", "").strip()
ZONE_URL = os.getenv("ZONE_URL", "http://127.0.0.1:8013").strip().rstrip("/")
ZONE_ON = os.getenv("ZONE_MODE", "all").strip().lower() != "off"
API_KEY = os.getenv("LLM_API_KEY", "")
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))


# ---------------------------------------------------------------- URL 归一化

def chat_endpoint() -> str:
    """把用户填的地址补全成 /v1/chat/completions。"""
    u = CHAT_URL.rstrip("/")
    if not u:
        return ""
    if u.endswith("/chat/completions"):
        return u
    if u.endswith("/v1"):
        return u + "/chat/completions"
    # http://host:port 这种裸 base
    after_scheme = u.split("://", 1)[-1]
    if "/" not in after_scheme:
        return u + "/v1/chat/completions"
    return u + "/chat/completions"


def base_endpoint() -> str:
    """模型列表用的 base（去掉 /chat/completions）。"""
    ep = chat_endpoint()
    if ep.endswith("/chat/completions"):
        return ep[: -len("/chat/completions")]
    return ep


def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    return h


# ---------------------------------------------------------------- 状态 / 模型列表

def _zone_alive() -> bool:
    """专区是否可用（可用则网页对话就能工作，不依赖成员 A 的本地模型）。"""
    if not ZONE_ON:
        return False
    try:
        with httpx.Client(timeout=4) as c:
            return c.get(f"{ZONE_URL}/health").status_code == 200
    except Exception:
        return False


def status() -> Dict[str, Any]:
    """给前端用：当前接了谁、有哪些模型可用。"""
    if _zone_alive():
        return {"provider": "zone", "online": True, "models": [], "endpoint": ZONE_URL, "hint": ""}
    if PROVIDER == "ollama":
        models = _ollama_models()
    return {
            "provider": "ollama",
            "online": bool(models),
            "models": models,
            "endpoint": f"{OLLAMA_URL}/api/chat",
            "hint": "" if models else f"Ollama 没有响应（{OLLAMA_URL}），请确认已启动并 pull 过模型",
        }
    if PROVIDER == "openai":
        ep = chat_endpoint()
        if not ep:
            return {"provider": "openai", "online": False, "models": [],
                    "endpoint": "", "hint": "未配置 LLM_CHAT_URL"}
        models, err = _openai_models()
        return {
            "provider": "openai",
            "online": bool(models),
            "models": models,
            "endpoint": ep,
            "hint": "" if models else f"连不上 {base_endpoint()}/models：{err}",
        }
    return {
        "provider": "none",
        "online": False,
        "models": [],
        "endpoint": "",
        "hint": "尚未接入模型：设置 LLM_PROVIDER=ollama 或 openai 后重启控制台",
    }


def _ollama_models() -> List[str]:
    try:
        with httpx.Client(timeout=3.0) as c:
            r = c.get(f"{OLLAMA_URL}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def _openai_models() -> Tuple[List[str], str]:
    base = base_endpoint()
    if not base:
        return [], "未配置地址"
    try:
        with httpx.Client(timeout=5.0) as c:
            r = c.get(f"{base}/models", headers=_headers())
            if r.status_code != 200:
                return [], f"HTTP {r.status_code}"
            data = r.json()
            return [m["id"] for m in data.get("data", [])], ""
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- 对话

def _build_body(model: str, messages: List[Dict[str, str]], stream: bool) -> Dict[str, Any]:
    # max_tokens 限制回复长度：语音场景越短越快
    return {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "120")),
        "stream": stream,
    }


def _zone_chat(messages: List[Dict[str, str]]) -> Tuple[str, str]:
    """调大模型专区，返回 (回复, 模型名)；失败抛异常。"""
    last_user = ""
    history = []
    for m in messages or []:
        role = m.get("role")
        content = m.get("content") or ""
        if not content:
            continue
        if role == "user":
            last_user = content
        if role in ("user", "assistant"):
            history.append({"role": role, "content": content})
    payload = {"message": last_user, "history": history[:-1] if len(history) > 1 else []}
    with httpx.Client(timeout=40) as c:
        r = c.post(f"{ZONE_URL}/api/v1/chat", json=payload)
        if r.status_code != 200:
            raise RuntimeError(f"专区 HTTP {r.status_code}: {r.text[:150]}")
        d = r.json()
        return (d.get("reply") or "").strip(), d.get("model") or "deepseek"


def chat(model: str, messages: List[Dict[str, str]]) -> Tuple[str, str]:
    """非流式。返回 (回复文本, 实际模型)。"""
    if ZONE_ON:
        try:
            reply, used = _zone_chat(messages)
            if reply:
                return reply, used
        except Exception as e:
            print(f"[llm] 专区失败，回退本地: {e}", flush=True)
    if PROVIDER == "ollama":
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(f"{OLLAMA_URL}/api/chat", json={
                "model": model or "qwen2.5:3b",
                "stream": False,
                "messages": messages,
                "options": {"temperature": 0.7},
            })
            if r.status_code != 200:
                raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:200]}")
            data = r.json()
            return data.get("message", {}).get("content", ""), data.get("model", model)

    if PROVIDER == "openai" and chat_endpoint():
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(chat_endpoint(), headers=_headers(),
                       json=_build_body(model, messages, False))
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            data = r.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"], data.get("model", model)
            return r.text, model

    raise RuntimeError("未接入任何模型")


def chat_stream(model: str, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
    """流式：逐段 yield 文本增量。上游不支持 SSE 时自动退回整段返回。"""
    if ZONE_ON:
        try:
            reply, used = _zone_chat(messages)
            if reply:
                yield reply
                return
        except Exception as e:
            print(f"[llm] 专区流式失败，回退本地: {e}", flush=True)
    if PROVIDER == "ollama":
        with httpx.Client(timeout=TIMEOUT) as c:
            with c.stream("POST", f"{OLLAMA_URL}/api/chat", json={
                "model": model or "qwen2.5:3b",
                "stream": True,
                "messages": messages,
                "options": {"temperature": 0.7},
            }) as r:
                if r.status_code != 200:
                    raise RuntimeError(f"Ollama HTTP {r.status_code}")
                for line in r.iter_lines():
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    piece = (obj.get("message") or {}).get("content", "")
                    if piece:
                        yield piece
                    if obj.get("done"):
                        return

    elif PROVIDER == "openai" and chat_endpoint():
        with httpx.Client(timeout=TIMEOUT) as c:
            with c.stream("POST", chat_endpoint(), headers=_headers(),
                          json=_build_body(model, messages, True)) as r:
                if r.status_code != 200:
                    body = r.read().decode("utf-8", "ignore")[:300]
                    raise RuntimeError(f"HTTP {r.status_code}: {body}")

                saw_delta = False
                for line in r.iter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except Exception:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content")
                    if piece:
                        saw_delta = True
                        yield piece

                if not saw_delta:
                    # 上游忽略了 stream=true，整段返回
                    with httpx.Client(timeout=TIMEOUT) as c2:
                        r2 = c2.post(chat_endpoint(), headers=_headers(),
                                     json=_build_body(model, messages, False))
                        if r2.status_code == 200:
                            d = r2.json()
                            txt = d.get("choices", [{}])[0].get("message", {}).get("content", "")
                            if txt:
                                yield txt
    else:
        raise RuntimeError("未接入任何模型")
