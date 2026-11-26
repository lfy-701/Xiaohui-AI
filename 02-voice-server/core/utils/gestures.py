"""软件侧手势编排（Gesture Engine）。

为什么要这一层：
    固件里的预设动作只有 12 个（站立/坐下/前进/后退/左右转/跳舞/趴下/睡觉/
    起身/摇尾巴/摇头），想再加「握手 / 开心 / 伸懒腰 / 转圈」就得重烧固件。
    当前策略是不烧固件：把这些新动作做成「服务端逐帧下发 6 路角度」，
    固件只负责执行 self.set_pose，动作表留在服务端，改角度不用重烧。

角度坐标系（与固件 self.set_pose 完全一致）：
    [左前 LF, 左后 LB, 右前 RF, 右后 RB, 竖直 VE, 头部 HO]
    参考固件预设：Stand=[90,90,90,90,90,90]
                  Sit=[90,50,90,121,90,90]
                  Lie=[50,50,121,121,90,90]
                  TurnLeft=[60,60,120,120,90,90] / TurnRight=[120,120,60,60,90,90]
                  Dance=[70,70,110,110,90,60]
    摇尾巴 = HO 60~120，摇头 = VE 65~115。

微调方式（不用改代码、不用重启）：
    在同目录上层 data/gestures.json 里覆盖任意手势即可，例如
        {"handshake": {"interval_ms": 160, "frames": [[90,90,140,90,90,100]]}}
    该文件按 mtime 热加载；框架字段缺省时沿用内置值。
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

# data/gestures.json（xiaozhi-server/data/）
_OVERRIDE_PATH = Path(__file__).resolve().parents[2] / "data" / "gestures.json"

STAND: List[int] = [90, 90, 90, 90, 90, 90]
MAX_FRAMES = 120

# 内置手势表：code -> {label, interval_ms, frames, reply}
BUILTIN_GESTURES: Dict[str, Dict[str, Any]] = {
    "handshake": {
        "label": "握手",
        "interval_ms": 150,
        "reply": "好呀，握个手。",
        "frames": [
            [90, 90, 120, 90, 92, 102],   # 预备：右前腿内收、头微抬
            [90, 90, 150, 90, 86, 112],   # 抬爪
            [90, 90, 138, 90, 86, 104],   # 上下点一次
            [90, 90, 152, 90, 86, 114],
            [90, 90, 138, 90, 86, 104],
            [90, 90, 150, 90, 86, 112],   # 收爪
            STAND,
        ],
    },
    "happy": {
        "label": "开心",
        "interval_ms": 260,
        "reply": "嘿嘿，开心～",
        # 每次只动两条腿，别让 4 路同时拉电流（本机舵机供电弱，会掉电重启）
        "frames": [
            [75, 90, 105, 90, 90, 70],    # 左摆身 + 尾巴垂下
            [90, 90, 90, 90, 90, 115],    # 回正 + 尾巴翘起
            [105, 90, 75, 90, 90, 70],    # 右摆身
            [90, 90, 90, 90, 90, 115],
            [75, 90, 105, 90, 90, 70],
            [90, 90, 90, 90, 90, 115],
            STAND,
        ],
    },
    "stretch": {
        "label": "伸懒腰",
        "interval_ms": 230,
        "reply": "嗯——伸个懒腰。",
        "frames": [
            [50, 50, 121, 121, 90, 70],   # 前腿压低伸出去
            [55, 45, 125, 115, 88, 60],   # 左右腿错开一点，像真的在伸
            [45, 55, 118, 122, 92, 78],
            [50, 50, 121, 121, 90, 70],
            [70, 70, 100, 100, 90, 85],
            STAND,
        ],
    },
    "spin": {
        "label": "转个圈",
        "interval_ms": 300,
        "reply": "看好啦，转个圈。",
        # 两段式对角差速：一次只抬两条腿，幅度也只取 ±20
        "frames": [
            [70, 90, 110, 90, 90, 90],
            [90, 70, 90, 110, 90, 90],
            [110, 90, 70, 90, 90, 90],
            [90, 110, 90, 70, 90, 90],
            [70, 90, 110, 90, 90, 90],
            [90, 70, 90, 110, 90, 90],
            [110, 90, 70, 90, 90, 90],
            [90, 110, 90, 70, 90, 90],
            STAND,
        ],
    },
}

# mtime 热加载缓存
_override_cache: Dict[str, Any] = {"mtime": None, "gestures": BUILTIN_GESTURES}


def _normalize_frames(raw: Any) -> Optional[List[List[int]]]:
    """把外部帧数据清洗成 [[int]*6]；不合法返回 None。"""
    if not isinstance(raw, list) or not raw:
        return None
    frames: List[List[int]] = []
    for item in raw[:MAX_FRAMES]:
        if not isinstance(item, (list, tuple)) or len(item) != 6:
            return None
        try:
            frame = [max(0, min(180, int(round(float(x))))) for x in item]
        except (TypeError, ValueError):
            return None
        frames.append(frame)
    return frames


def _load_overrides() -> Dict[str, Any]:
    """读 data/gestures.json（按 mtime 缓存），与内置表合并。"""
    try:
        mtime = _OVERRIDE_PATH.stat().st_mtime
    except OSError:
        _override_cache["mtime"] = None
        _override_cache["gestures"] = BUILTIN_GESTURES
        return BUILTIN_GESTURES

    if _override_cache["mtime"] == mtime:
        return _override_cache["gestures"]

    merged: Dict[str, Dict[str, Any]] = {k: dict(v) for k, v in BUILTIN_GESTURES.items()}
    try:
        data = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # 文件写坏了不要让动作全挂掉
        logger.bind(tag=TAG).warning(f"gestures.json 解析失败，用内置手势：{exc}")
        data = {}

    if isinstance(data, dict):
        for code, patch in data.items():
            if not isinstance(patch, dict):
                continue
            base = merged.get(code, {"label": code, "interval_ms": 150, "frames": []})
            item = dict(base)
            if isinstance(patch.get("label"), str) and patch["label"].strip():
                item["label"] = patch["label"].strip()
            if isinstance(patch.get("reply"), str) and patch["reply"].strip():
                item["reply"] = patch["reply"].strip()
            try:
                interval = int(patch.get("interval_ms", item.get("interval_ms", 150)))
                item["interval_ms"] = max(40, min(2000, interval))
            except (TypeError, ValueError):
                pass
            if "frames" in patch:
                frames = _normalize_frames(patch["frames"])
                if frames:
                    item["frames"] = frames
                else:
                    logger.bind(tag=TAG).warning(f"gestures.json 里 {code} 的 frames 不合法，忽略")
            if item.get("frames"):
                merged[code] = item

    _override_cache["mtime"] = mtime
    _override_cache["gestures"] = merged
    return merged


def gestures() -> Dict[str, Dict[str, Any]]:
    return _load_overrides()


def is_gesture(code: str) -> bool:
    return (code or "").strip() in gestures()


def gesture_reply(code: str) -> Optional[str]:
    g = gestures().get(code or "")
    return g.get("reply") if g else None


def catalog() -> List[Dict[str, Any]]:
    """给控制台/文档用的手势清单（不含帧数据，避免响应过大）。"""
    out: List[Dict[str, Any]] = []
    for code, g in gestures().items():
        out.append(
            {
                "action": code,
                "label": g.get("label", code),
                "kind": "gesture",
                "interval_ms": g.get("interval_ms", 150),
                "frames": len(g.get("frames") or []),
            }
        )
    return out


async def _tool_name(client, preferred: str = "self_set_pose") -> str:
    """MCP 工具名按 sanitize 后的形式存（self.set_pose -> self_set_pose）。"""
    try:
        from core.utils.util import sanitize_tool_name

        for name in (preferred, preferred.replace("_", ".", 1)):
            if client.has_tool(name):
                return name
        return sanitize_tool_name(preferred.replace("_", ".", 1))
    except Exception:
        return preferred


async def play(conn, code: str, timeout: float = 3.0) -> Dict[str, Any]:
    """逐帧回放一个手势，结束后回到站立姿态。"""
    from core.providers.tools.device_mcp import call_mcp_tool

    g = gestures().get((code or "").strip())
    if not g:
        return {"ok": False, "error": f"未知手势: {code}"}

    client = getattr(conn, "mcp_client", None)
    if client is None:
        return {"ok": False, "error": "设备 MCP 未连接"}
    try:
        if not await client.is_ready():
            return {"ok": False, "error": "设备 MCP 未就绪"}
    except Exception as exc:
        return {"ok": False, "error": f"设备 MCP 不可用: {exc}"}

    tool = await _tool_name(client)
    if not client.has_tool(tool):
        return {"ok": False, "error": "固件缺少 self.set_pose，无法播放手势"}

    frames: List[List[int]] = g.get("frames") or []
    interval = max(40, min(2000, int(g.get("interval_ms", 150)))) / 1000.0
    sent = 0
    consecutive_fail = 0
    last_error: Optional[str] = None
    try:
        for index, frame in enumerate(frames, start=1):
            angles = ",".join(str(int(x)) for x in frame)
            ok = False
            for attempt in (1, 2):          # 单帧超时重试一次（设备偶尔漏帧）
                try:
                    await call_mcp_tool(conn, client, tool, json.dumps({"angles": angles}),
                                        timeout=timeout)
                    ok = True
                    break
                except Exception as exc:
                    last_error = str(exc)
                    if attempt == 1:
                        await asyncio.sleep(0.15)
            if ok:
                sent += 1
                consecutive_fail = 0
            else:
                consecutive_fail += 1
                logger.bind(tag=TAG).warning(
                    f"手势 {code} 第 {index} 帧失败（连续 {consecutive_fail} 次）：{last_error}"
                )
                # 连续两帧失败基本就是设备掉线/重启了，别再空推帧
                if consecutive_fail >= 2:
                    return {"ok": False, "error": f"手势执行中断: {last_error}", "frames": sent}
                continue
            await asyncio.sleep(interval)
    except Exception as exc:
        logger.bind(tag=TAG).warning(f"手势 {code} 异常中断：{exc}")
        return {"ok": False, "error": f"手势执行中断: {exc}", "frames": sent}
    finally:
        # 无论成功失败都回站立，避免停在一个奇怪姿势上
        try:
            await call_mcp_tool(
                conn, client, tool, json.dumps({"angles": ",".join(str(x) for x in STAND)}),
                timeout=timeout,
            )
        except Exception:
            pass

    return {"ok": True, "gesture": code, "label": g.get("label", code), "frames": sent}
