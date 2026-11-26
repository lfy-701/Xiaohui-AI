"""控制台网页对话接入大模型专区：优先走 8013，失败自动回退本地模型。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\llm.py")
t = P.read_text(encoding="utf-8")

if "ZONE_URL" not in t:
    # 1) 顶部加配置
    t = t.replace(
        'CHAT_URL = os.getenv("LLM_CHAT_URL", "").strip()',
        'CHAT_URL = os.getenv("LLM_CHAT_URL", "").strip()\n'
        'ZONE_URL = os.getenv("ZONE_URL", "http://127.0.0.1:8013").strip().rstrip("/")\n'
        'ZONE_ON = os.getenv("ZONE_MODE", "all").strip().lower() != "off"',
        1,
    )

    # 2) 在 chat() 开头插入专区优先
    old = '''def chat(model: str, messages: List[Dict[str, str]]) -> Tuple[str, str]:
    """非流式。返回 (回复文本, 实际模型)。"""'''
    new = '''def _zone_chat(messages: List[Dict[str, str]]) -> Tuple[str, str]:
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
            print(f"[llm] 专区失败，回退本地: {e}", flush=True)'''
    if old in t:
        t = t.replace(old, new, 1)
        print("llm.py：chat() 已优先走专区")
    else:
        print("⚠ chat() 未匹配")

    P.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("语法 OK")
