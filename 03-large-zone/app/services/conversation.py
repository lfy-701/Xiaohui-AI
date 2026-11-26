"""对话输入组装：历史裁剪、长度上限、system prompt 注入。

安全要点：客户端传来的历史只允许 user/assistant，system 角色不可被覆盖。
"""

from __future__ import annotations

from typing import Any, Sequence

from app.config import Settings

# 历史部分的总字符预算，防止长对话把 token 成本推高
HISTORY_CHAR_BUDGET = 8_000


def build_messages(
    settings: Settings,
    user_message: str,
    history: Sequence[Any] | None = None,
) -> list[dict[str, str]]:
    """组装发给 DeepSeek 的 messages。

    - 历史按最近 N 条裁剪，单条按 max_message_chars 截断
    - 历史总字符超出预算时，从最旧的消息开始丢弃
    - 永远以服务端配置的 system prompt 开头，客户端无法覆盖
    """
    cleaned: list[dict[str, str]] = []

    for item in (history or [])[-settings.max_history_messages :]:
        role = getattr(item, "role", None)
        content = (getattr(item, "content", None) or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        if len(content) > settings.max_message_chars:
            content = content[: settings.max_message_chars]
        cleaned.append({"role": role, "content": content})

    while cleaned and sum(len(m["content"]) for m in cleaned) > HISTORY_CHAR_BUDGET:
        cleaned.pop(0)

    text = user_message.strip()
    if len(text) > settings.max_message_chars:
        text = text[: settings.max_message_chars]

    return [{"role": "system", "content": settings.system_prompt}, *cleaned, {"role": "user", "content": text}]
