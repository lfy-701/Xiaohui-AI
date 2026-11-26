"""在专区 chat 接口加入 function calling（工具循环）。

流程：带 tools 调 DeepSeek → 若返回 tool_calls → 本地执行 → 回填 → 再调一次（最多 3 轮）。
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\xiaohui-large-zone\app\api\chat.py")
t = P.read_text(encoding="utf-8")

if "call_with_tools" in t:
    print("已存在工具循环")
    sys.exit(0)

# 1) 导入
t = t.replace(
    "from app.services.fast_answers import fast_answer, now_context",
    "from app.services.fast_answers import fast_answer, now_context\nfrom app.services.tools import TOOLS_SPEC, execute_tool",
    1,
)

# 2) 在 result = await client.chat(...) 之前插入工具循环
old = """    result = await client.chat(
        messages,
        thinking=thinking,
        reasoning_effort=payload.reasoning_effort,
        max_tokens=payload.max_tokens,
        user_id=payload.device_id,
    )"""

new = '''    # 带工具调用：先让模型决定是否调工具，最多 3 轮
    result = None
    try:
        result = await client.call_with_tools(
            messages,
            tools=TOOLS_SPEC,
            max_tokens=payload.max_tokens,
            max_rounds=3,
        )
    except Exception as _e:
        logger.warning("工具循环失败，退回普通对话: %s", _e)
        result = None

    if result is None:
        result = await client.chat(
            messages,
            thinking=thinking,
            reasoning_effort=payload.reasoning_effort,
            max_tokens=payload.max_tokens,
            user_id=payload.device_id,
        )'''

if old in t:
    t = t.replace(old, new, 1)
    print("chat.py：已接入工具循环")
else:
    print("⚠ chat.py 未匹配 chat 调用")

P.write_text(t, encoding="utf-8")
ast.parse(t)
print("语法 OK")

# 3) 给 DeepSeekClient 加 call_with_tools
C = Path(r"D:\xiaohui-large-zone\app\services\deepseek_client.py")
c = C.read_text(encoding="utf-8")

if "call_with_tools" not in c:
    helper = '''

    async def call_with_tools(self, messages, tools, max_tokens=None, max_rounds=3):
        """带工具调用：返回与 chat() 相同结构的结果对象。"""
        import json as _json

        core = self._require_client()

        for _ in range(max(1, int(max_rounds))):
            resp = await core.chat.completions.create(
                model=self._settings.deepseek_model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=max_tokens or self._settings.max_tokens,
                temperature=self._settings.temperature,
            )
            msg = resp.choices[0].message
            calls = getattr(msg, "tool_calls", None)
            if not calls:
                text = (msg.content or "").strip()
                from app.services.deepseek_client import ChatResult  # noqa: F401
                return _LocalResult(text=text, tokens=(resp.usage.total_tokens if resp.usage else 0))

            # 把模型的工具调用意图写回历史
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in calls
                ],
            })

            from app.services.tools import execute_tool

            for tc in calls:
                try:
                    out = execute_tool(tc.function.name, tc.function.arguments)
                except Exception as e:
                    out = f"工具失败: {e}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(out)[:1500],
                })

        return _LocalResult(text="抱歉，我这边处理有点绕，你能再说一次吗？", tokens=0)

'''
    idx = c.rfind("\n", 0, len(c))
    c = c.rstrip() + "\n" + helper
    # 追加结果容器
    c += '''

class _LocalResult:
    """call_with_tools 的轻量返回结构，兼容 chat() 的字段访问。"""

    def __init__(self, text: str, tokens: int = 0):
        self.text = text
        self.reasoning = ""
        self.tokens = tokens
        self.finish_reason = "stop"
        self.request_id = None
'''
    C.write_text(c, encoding="utf-8")
    ast.parse(c)
    print("deepseek_client.py：已加 call_with_tools")
