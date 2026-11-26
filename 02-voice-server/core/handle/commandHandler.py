"""语音关键词兜底：识别文本命中动作时直接调设备 MCP，不经过大模型。

背景：
成员 A 的模型服务目前会拒绝未注册的工具（self.dog_action），大模型这条
路调不动设备。为了「说趴下就趴下」，在进大模型之前拦一道关键词：

    ASR 文本 -> 关键词匹配 -> 设备 MCP 工具 -> 回一句确认

只有设备 MCP 已经就绪才拦截；没命中、设备离线或工具报错时都放行给原流程，
保证不影响正常聊天。
"""

from __future__ import annotations

import os
import time

from config.logger import setup_logging
from core.handle.sendAudioHandle import send_stt_message
from core.providers.tools.device_mcp import call_mcp_tool
from core.providers.tts.dto.dto import ContentType
from core.utils.console_actions import match_voice_command
from core.utils.dialogue import Message

TAG = __name__
logger = setup_logging()

# 可用环境变量关掉兜底（比如设备固件自己也会本地执行关键词时，避免动两次）
ENABLED = os.getenv("VOICE_KEYWORD_FALLBACK", "1").strip().lower() not in (
    "0",
    "false",
    "off",
    "no",
)

TOOL_TIMEOUT = 8
# 同一句话在很短时间内重复识别（ASR 抖动）时不再重复执行
DEBOUNCE_SECONDS = 2.0


async def try_handle_voice_command(conn, text: str) -> bool:
    """命中关键词就执行并返回 True；否则返回 False 交给原对话流程。"""
    if not ENABLED or not text:
        return False

    command = match_voice_command(text)
    if not command:
        return False

    client = getattr(conn, "mcp_client", None)
    if client is None:
        return False
    try:
        if not await client.is_ready():
            return False
    except Exception:
        return False

    action = command["action"]
    now = time.time()
    last = getattr(conn, "_last_voice_command", None)
    if last and last[0] == action and (now - last[1]) < DEBOUNCE_SECONDS:
        conn.logger.bind(tag=TAG).info(f"关键词兜底去抖：{command['keyword']}")
        return True

    reply = command["reply"]

    # 服务端手势（握手/开心/伸懒腰/转圈）：固件没有预设，走多帧 set_pose
    from core.utils import gestures as _gestures

    if _gestures.is_gesture(action):
        result = await _gestures.play(conn, action)
        if not result.get("ok"):
            conn.logger.bind(tag=TAG).warning(
                f"关键词兜底手势失败：{command['keyword']} -> {action}：{result.get('error')}"
            )
            return False
        reply = _gestures.gesture_reply(action) or reply
    else:
        try:
            result = await call_mcp_tool(
                conn,
                client,
                command["tool"],
                {"action": action},
                timeout=TOOL_TIMEOUT,
            )
        except Exception as e:
            # 工具没注册/固件不支持/超时：交给大模型正常回复，不假装执行成功
            conn.logger.bind(tag=TAG).warning(
                f"关键词兜底执行失败：{command['keyword']} -> {action}：{e}"
            )
            return False

    conn._last_voice_command = (action, now)
    conn.logger.bind(tag=TAG).info(
        f"关键词兜底命中：{command['keyword']} -> {action}，设备返回：{result}"
    )

    # 先让屏幕显示用户说了什么，再回一句短确认
    try:
        await send_stt_message(conn, text)
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"发送 STT 失败：{e}")

    try:
        if getattr(conn, "tts", None) is not None:
            conn.tts.tts_one_sentence(conn, ContentType.TEXT, content_detail=reply)
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"关键词兜底 TTS 失败：{e}")

    try:
        conn.dialogue.put(Message(role="user", content=text))
        conn.dialogue.put(Message(role="assistant", content=reply))
    except Exception:
        pass

    return True
