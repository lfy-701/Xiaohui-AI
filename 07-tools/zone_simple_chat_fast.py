"""专区：简单闲聊跳过工具决策（少一次 API 往返，明显更快）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\xiaohui-large-zone\app\api\chat.py")
t = P.read_text(encoding="utf-8")

if "SIMPLE_CHAT" not in t:
    old = """    # 带工具调用：先让模型决定是否调工具，最多 3 轮
    result = None"""
    new = """    # 简单闲聊直接回答：跳过工具决策，省一次 API 往返
    _TOOL_WORDS = ("新闻", "天气", "几号", "星期", "气温", "温度", "搜", "查")
    _text = (payload.message or "").strip()
    SIMPLE_CHAT = len(_text) <= 14 and not any(w in _text for w in _TOOL_WORDS)

    result = None
    if SIMPLE_CHAT:
        try:
            result = await client.chat(
                messages,
                thinking=thinking,
                reasoning_effort=payload.reasoning_effort,
                max_tokens=payload.max_tokens,
                user_id=payload.device_id,
            )
        except Exception as _e:
            logger.warning("简单模式失败，改走工具循环: %s", _e)
            result = None"""
    if old in t:
        t = t.replace(old, new, 1)
        # 工具循环只在非简单模式执行
        t = t.replace("""    try:
        result = await client.call_with_tools(""",
                      """    try:
        if result is not None:
            raise _SkipTools()
        result = await client.call_with_tools(""", 1)
        # 定义跳过异常
        t = t.replace("from app.schemas import ChatRequest, ChatResponse, Usage",
                      "from app.schemas import ChatRequest, ChatResponse, Usage\n\n\nclass _SkipTools(Exception):\n    pass", 1)
        P.write_text(t, encoding="utf-8")
        ast.parse(t)
        print("专区：简单闲聊已跳过工具决策")
    else:
        print("未匹配")
else:
    print("已存在")
