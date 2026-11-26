"""语音运行时设置（由控制台写入 data/voice_settings.json）。

控制台改完立即生效：VAD 在每通连接建立时读取，TTS 在每次合成时读取。
"""
import json
from pathlib import Path

_DEFAULT = {
    "recognize": 2,
    "speed": 2,
    "pitch": 1,
    "silence_ms": 350,
    "rate": "+25%",
    "pitch_hz": "+0Hz",
}


def _path() -> Path:
    # 本文件在 core/utils/ 下，向上两级是 xiaozhi-server 根目录
    return Path(__file__).resolve().parents[2] / "data" / "voice_settings.json"


def load() -> dict:
    out = dict(_DEFAULT)
    try:
        p = _path()
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                out.update(data)
    except Exception:
        pass
    return out
