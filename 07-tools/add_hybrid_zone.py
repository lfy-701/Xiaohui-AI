"""混合模式：难题走大模型专区（DeepSeek），闲聊走本地小模型。

判定规则（可调）：
- 命中「深度词」（为什么/怎么理解/解释/分析/原理/作业/数学/作文/推导…）
- 或文本长度 >= 18 字
命中则调专区 /api/v1/chat；失败自动回退本地模型。
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\providers\llm\openai\openai.py")
t = F.read_text(encoding="utf-8")

if "_zone_route" in t:
    print("已存在混合路由")
    sys.exit(0)

HELPER = '''

# ---------------------------------------------------------------- 混合路由
_ZONE_DEEP_WORDS = (
    "为什么", "怎么理解", "解释", "分析", "原理", "推导", "证明",
    "作业", "数学题", "解题", "作文", "写好", "区别", "比较",
    "详细说说", "深入", "科普", "原理是什么", "怎么做",
)


def _zone_route(dialogue) -> tuple:
    """返回 (是否走专区, 最后一句用户文本)。"""
    import os as _os

    last = ""
    history = []
    try:
        for m in dialogue or []:
            role = m.get("role") if isinstance(m, dict) else getattr(m, "role", "")
            content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
            if not content:
                continue
            if role == "user":
                last = str(content)
            if role in ("user", "assistant"):
                history.append({"role": role, "content": str(content)})
    except Exception:
        return False, ""

    if _os.getenv("ZONE_HYBRID", "1") != "1":
        return False, last

    text = last.strip()
    if not text:
        return False, last

    try:
        min_len = int(_os.getenv("ZONE_MIN_LEN", "18"))
    except Exception:
        min_len = 18

    hit_word = any(w in text for w in _ZONE_DEEP_WORDS)
    if hit_word or len(text) >= min_len:
        return True, last
    return False, last


def _ask_zone(question: str, history: list) -> str:
    """调大模型专区，返回纯文本回复；失败返回空串。"""
    import os as _os

    import httpx as _hx

    base = _os.getenv("ZONE_URL", "http://127.0.0.1:8013").rstrip("/")
    try:
        timeout = float(_os.getenv("ZONE_TIMEOUT", "25"))
    except Exception:
        timeout = 25.0

    payload = {"message": question, "history": history[-12:]}
    try:
        with _hx.Client(timeout=timeout) as c:
            r = c.post(base + "/api/v1/chat", json=payload)
            if r.status_code != 200:
                logger.bind(tag=TAG).warning(f"专区返回 {r.status_code}: {r.text[:120]}")
                return ""
            data = r.json()
            return (data.get("reply") or "").strip()
    except Exception as e:
        logger.bind(tag=TAG).warning(f"专区调用失败: {e}")
        return ""

'''

idx = t.find("    def response(self, session_id, dialogue, **kwargs):")
if idx < 0:
    print("⚠ 未找到 response")
    sys.exit(1)
t = t[:idx] + HELPER.strip() + "\n\n\n" + t[idx:]

# 在 response 开头插入路由判断
old_head = '''    def response(self, session_id, dialogue, **kwargs):
        # 模型支持热切换：控制台保存后下一次请求就用新模型'''
new_head = '''    def response(self, session_id, dialogue, **kwargs):
        # 混合路由：难题交给大模型专区
        try:
            _use_zone, _q = _zone_route(dialogue)
            if _use_zone:
                _hist = []
                try:
                    for m in dialogue or []:
                        role = m.get("role") if isinstance(m, dict) else getattr(m, "role", "")
                        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
                        if role in ("user", "assistant") and content:
                            _hist.append({"role": role, "content": str(content)})
                except Exception:
                    _hist = []
                _ans = _ask_zone(_q, _hist)
                if _ans:
                    logger.bind(tag=TAG).info(f"混合路由：大模型专区回答 {len(_ans)} 字")
                    yield _ans
                    return
                logger.bind(tag=TAG).warning("专区无回应，回退本地模型")
        except Exception as e:
            logger.bind(tag=TAG).warning(f"混合路由异常，回退本地: {e}")

        # 模型支持热切换：控制台保存后下一次请求就用新模型'''
if old_head in t:
    t = t.replace(old_head, new_head, 1)
    print("response：已插入混合路由")
else:
    print("⚠ 未匹配 response 开头")

F.write_text(t, encoding="utf-8")
ast.parse(t)
print("语法 OK")
