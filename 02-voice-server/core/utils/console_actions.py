"""控制台动作 ↔ 设备 MCP 工具的统一映射。

两处共用：
- core/api/console_handler.py：HTTP 接口 /api/console/action
- core/handle/commandHandler.py：语音关键词兜底

只做纯数据匹配，不碰网络和连接。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# 设备端 MCP 工具名（MCPClient 内部按 sanitize 后的名字存）
DOG_ACTION_TOOL = "self_dog_action"
DOG_ACTION_TOOL_ORIGINAL = "self.dog_action"

# 动作编码 -> 中文名（也是控制台按钮的 action 值）
# 前 13 个走固件预设 self.dog_action；handshake/happy/stretch/spin 是
# 服务端手势（见 core/utils/gestures.py），不需要重烧固件。
ACTION_LABELS: Dict[str, str] = {
    "stand": "站立",
    "sit": "坐下",
    "walk": "前进",
    "back": "后退",
    "left": "左转",
    "right": "右转",
    "dance": "跳舞",
    "lie": "趴下",
    "sleep": "睡觉",
    "wake": "起身",
    "wag": "摇尾巴",
    "shake": "摇头",
    "stop": "停下",
    "handshake": "握手",
    "happy": "开心",
    "stretch": "伸懒腰",
    "spin": "转个圈",
}

# 走服务端手势引擎（多帧 set_pose）的动作，其余走固件预设
GESTURE_CODES = ("handshake", "happy", "stretch", "spin")

# 关键词命中后直接说一句，短、自然，避免大模型再介入
ACTION_REPLIES: Dict[str, str] = {
    "stand": "好呀，站好了。",
    "sit": "好呀，坐下了。",
    "walk": "好，往前走。",
    "back": "好，往后退。",
    "left": "好，左转。",
    "right": "好，右转。",
    "dance": "好呀，跳个舞。",
    "lie": "好呀，趴下了。",
    "sleep": "好，睡觉了。",
    "wake": "好，起来了。",
    "wag": "好呀，摇尾巴。",
    "shake": "好，摇摇头。",
    "stop": "好，停下了。",
    "handshake": "好呀，握个手。",
    "happy": "嘿嘿，开心～",
    "stretch": "嗯——伸个懒腰。",
    "spin": "看好啦，转个圈。",
}

# 常见英文别名，兼容旧按钮/外部调用
ACTION_ALIASES: Dict[str, str] = {
    "forward": "walk",
    "backward": "back",
    "turn_left": "left",
    "turn_right": "right",
    "liedown": "lie",
    "lay": "lie",
    "up": "wake",
    "tail": "wag",
    "head_shake": "shake",
    "halt": "stop",
    "shake_hand": "handshake",
    "hands": "handshake",
    "hand_shake": "handshake",
    "cheer": "happy",
    "glad": "happy",
    "lazy": "stretch",
    "circle": "spin",
    "turn_circle": "spin",
}

# 关键词 -> 动作。长词放前面，避免「起来」抢在「站起来」前面。
_KEYWORD_RULES: List[tuple] = [
    ("往前走", "walk"),
    ("向前走", "walk"),
    ("往前走两步", "walk"),
    ("走两步", "walk"),
    ("前进", "walk"),
    ("往后退", "back"),
    ("向后退", "back"),
    ("后退", "back"),
    ("退后", "back"),
    ("往左转", "left"),
    ("向左转", "left"),
    ("左转", "left"),
    ("往右转", "right"),
    ("向右转", "right"),
    ("右转", "right"),
    ("跳个舞", "dance"),
    ("跳一下", "dance"),
    ("跳舞", "dance"),
    ("趴下", "lie"),
    ("趴着", "lie"),
    ("趴好", "lie"),
    ("睡觉", "sleep"),
    ("睡吧", "sleep"),
    ("休息一下", "sleep"),
    ("站起来", "stand"),
    ("站好", "stand"),
    ("站立", "stand"),
    ("起立", "stand"),
    ("坐一下", "sit"),
    ("坐下", "sit"),
    ("坐好", "sit"),
    ("起身", "wake"),
    ("起床", "wake"),
    ("起来", "wake"),
    ("摇摇尾巴", "wag"),
    ("摇尾巴", "wag"),
    ("摇摇头", "shake"),
    ("摇头", "shake"),
    # —— 服务端手势（固件没有预设，靠 gestures.py 逐帧下发）——
    ("握个手", "handshake"),
    ("握握手", "handshake"),
    ("握下手", "handshake"),
    ("手给我", "handshake"),
    ("握手", "handshake"),
    ("伸个懒腰", "stretch"),
    ("伸懒腰", "stretch"),
    ("伸展一下", "stretch"),
    ("转个圈", "spin"),
    ("转一圈", "spin"),
    ("原地转圈", "spin"),
    ("转圈", "spin"),
    ("开心一点", "happy"),
    ("高兴一点", "happy"),
    ("撒个娇", "happy"),
    ("卖个萌", "happy"),
    ("不要动", "stop"),
    ("别动", "stop"),
    ("停下", "stop"),
    ("停止", "stop"),
    ("别跳了", "stop"),
    ("别走了", "stop"),
]
_KEYWORD_RULES.sort(key=lambda item: len(item[0]), reverse=True)

# 「不要坐下」这类否定句不执行
_NEGATIONS = ("不要", "别", "不用", "不许", "不准", "无需")


def normalize_action(raw: str) -> Optional[str]:
    """把外部传入的动作名规范成内部编码，未知返回 None。"""
    text = (raw or "").strip().lower()
    if not text:
        return None
    text = ACTION_ALIASES.get(text, text)
    return text if text in ACTION_LABELS else None


def action_arguments(raw: str) -> Optional[Dict[str, Any]]:
    """动作名 -> self.dog_action 的参数；未知返回 None。"""
    code = normalize_action(raw)
    if not code:
        return None
    return {"action": code}


def _is_negated(text: str, index: int) -> bool:
    prefix = text[:index]
    return any(prefix.endswith(word) for word in _NEGATIONS)


def match_voice_command(text: str) -> Optional[Dict[str, str]]:
    """从一句识别文本里匹配设备动作。

    返回 {action, keyword, reply, tool}；没命中返回 None。
    否定句（「不要坐下」）直接忽略，交给大模型正常聊天。
    """
    if not text:
        return None
    clean = re.sub(r"\s+", "", text)
    for keyword, action in _KEYWORD_RULES:
        index = clean.find(keyword)
        if index < 0:
            continue
        if _is_negated(clean, index):
            continue
        return {
            "action": action,
            "keyword": keyword,
            "reply": ACTION_REPLIES[action],
            "tool": DOG_ACTION_TOOL,
        }
    return None


def public_action_list() -> List[Dict[str, str]]:
    """给前端/文档用的动作清单。"""
    return [{"action": code, "label": label} for code, label in ACTION_LABELS.items()]


def action_catalog() -> List[Dict[str, Any]]:
    """控制台动作面板的完整清单：固件预设 + 服务端手势。

    控制台按这个渲染按钮，避免「网页 8 个按钮、固件 12 个动作、语音 17 个词」
    三处各写一份的漂移。
    """
    out: List[Dict[str, Any]] = []
    gesture_info: Dict[str, Dict[str, Any]] = {}
    try:
        from core.utils.gestures import catalog as gesture_catalog

        gesture_info = {g["action"]: g for g in gesture_catalog()}
    except Exception:
        gesture_info = {}

    for code, label in ACTION_LABELS.items():
        is_gesture = code in GESTURE_CODES
        item: Dict[str, Any] = {
            "action": code,
            "label": label,
            "kind": "gesture" if is_gesture else "preset",
        }
        if is_gesture and code in gesture_info:
            item["interval_ms"] = gesture_info[code].get("interval_ms")
            item["frames"] = gesture_info[code].get("frames")
            # 手势的中文名以 gestures.py 为准（data/gestures.json 可改名）
            item["label"] = gesture_info[code].get("label") or label
        out.append(item)
    return out
