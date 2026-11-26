"""一轮对话的分阶段打点（V1.2 阶段零）。

设计目标：一条链路上「用户说完 → 设备出声」拆成 T0~T8，每轮打一行 JSON，
后续所有优化都用同一口径对比，不靠感觉。

指标口径（与方案文档一致）：
    T0 最后一帧上行语音     T1 VAD 判停        T2 ASR 出文本
    T3 LLM 请求发出         T4 LLM 首 token    T5 首个可朗读句子
    T6 TTS 首个音频块       T7 服务端首帧发送  T8 设备实际出声（暂无回执，置 null）
    A = T0 → T8（起播，核心）；B = T6 → 末句发完（多句总时长，次要）

用法（全部容错，绝不因为打点抛错影响对话）：
    from core.utils import latency
    latency.mark(conn, "t0")     # 也可以 begin() 复位
    latency.mark(conn, "t2", text="今天天气")
    latency.flush(conn, route="zone")   # 本轮结束，输出 JSON 并复位
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from config.logger import setup_logging

TAG = "latency"
logger = setup_logging()

_KEYS = ("t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8")


def begin(conn) -> None:
    """开始新一轮：清空上一轮的时间点。

    注意：设备在一轮里可能连发多次 `listen start`（实测 17:54 一轮里就发了两次），
    如果每次 start 都重置，会把已经记下的 T1/T2/T3 抹掉（表现为全是 null）。
    所以只有「当前没有进行中的一轮」时才初始化。
    """
    try:
        if isinstance(getattr(conn, "_lat", None), dict):
            return
        conn._lat = {"conv_id": f"{int(time.time() * 1000) % 1000000}", "seq": 0}
    except Exception:
        pass


def _state(conn) -> Optional[Dict[str, Any]]:
    st = getattr(conn, "_lat", None)
    if not isinstance(st, dict):
        begin(conn)
        st = getattr(conn, "_lat", None)
    return st if isinstance(st, dict) else None


def mark(conn, key: str, **extra) -> None:
    """记录一个时间点（同一个 key 只记第一次，避免多帧覆盖）。"""
    try:
        st = _state(conn)
        if st is None or key not in _KEYS:
            return
        if key not in st:
            st[key] = time.time()
        for k, v in extra.items():
            st.setdefault(k, v)
    except Exception:
        pass


def frame(conn) -> None:
    """每收到一帧上行音频调用：刷新 T0（= 最后一帧到达时间）。

    VAD 判停（T1）之后设备可能还在补发/重连发的帧，这时不能再动 T0，
    否则 T0 会跑到 T1 之后，算出负数区间（实测出现过 server_a_ms = -43）。
    """
    try:
        st = _state(conn)
        if st is not None and "t1" not in st:
            st["t0"] = time.time()
    except Exception:
        pass


def sentence(conn) -> None:
    """每产出一句待合成文本调用：T5 取第一句的时间。"""
    try:
        st = _state(conn)
        if st is None:
            return
        st["seq"] = int(st.get("seq", 0)) + 1
        if "t5" not in st:
            st["t5"] = time.time()
    except Exception:
        pass


def flush(conn, route: str = "", model: str = "", note: str = "") -> None:
    """本轮结束：输出一行 JSON（毫秒差值），然后复位。"""
    try:
        st = _state(conn)
        if not st:
            return

        def delta(a: str, b: str) -> Optional[int]:
            ta, tb = st.get(a), st.get(b)
            if ta is None or tb is None:
                return None
            return int(round((tb - ta) * 1000))

        payload = {
            "conv_id": st.get("conv_id"),
            "sentences": int(st.get("seq", 0)),
            "route": route,
            "model": model,
            # 各阶段绝对时间（秒，便于对齐设备日志）
            **{k: (round(st[k], 3) if k in st else None) for k in _KEYS},
            # 关键区间（毫秒）
            "a_play_ms": None,            # T0→T8 暂无设备回执
            "b_total_ms": None,           # T6→末句，由调用方补
            "asr_ms": delta("t1", "t2"),
            "llm_ms": delta("t3", "t4"),
            "llm_total_ms": delta("t3", "t5"),
            "tts_first_ms": delta("t5", "t6"),
            "first_frame_ms": delta("t5", "t7"),
            "server_a_ms": delta("t0", "t7"),   # 服务端口径的"到首帧"
            "note": note,
        }
        logger.bind(tag=TAG).info(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass
    finally:
        try:
            conn._lat = None
        except Exception:
            pass
