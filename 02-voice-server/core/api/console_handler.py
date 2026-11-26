"""控制台控制接口（最小实现）：网页文字转语音、播放网络音频、停止播放。

挂在语音服务的 HTTP 端口（默认 8003）：
- GET  /api/console/status   在线连接状态
- GET  /api/console/actions  动作面板目录（固件预设 + 服务端手势）
- POST /api/console/action   {"action": "handshake"} 走手势引擎，其余走 self.dog_action
- POST /api/console/say      {"text": "..."}  合成并推给设备
- POST /api/console/play     {"url": "..."}   播放网络音频
- POST /api/console/stop     {}               停止当前播放
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from aiohttp import web

from core.api.base_handler import BaseHandler

TAG = __name__


MUSIC_EMOTION = "music"        # 享受音乐的表情
DEFAULT_EMOTION = "neutral"   # 恢复用


async def _set_emotion(conn, emotion: str, timeout: float = 5.0):
    """切换设备表情：走控制台硬件接口（已验证可用），失败不影响播放。"""
    import os as _os

    import httpx as _httpx

    base = _os.getenv("CONSOLE_URL", "http://127.0.0.1:8080").rstrip("/")
    token = ""
    try:
        with _httpx.Client(timeout=timeout) as c:
            devs = c.get(base + "/api/hardware/devices",
                         headers={"X-Hardware-Token": token}).json().get("devices") or []
            if not devs:
                return
            did = devs[0]["id"]
            c.post(
                f"{base}/api/hardware/devices/{did}/commands",
                headers={"X-Hardware-Token": token},
                json={"type": "emotion", "params": {"emotion": emotion}},
            )
        try:
            conn.logger.bind(tag="Play").info(f"表情切换: {emotion}")
        except Exception:
            pass
    except Exception as e:
        try:
            conn.logger.bind(tag="Play").warning(f"表情切换失败: {e}")
        except Exception:
            pass


class ConsoleActionHandler(BaseHandler):
    def __init__(self, config: dict, ws_server=None):
        super().__init__(config)
        self.ws_server = ws_server

    # ------------------------------------------------------------ 基础

    def _connections(self) -> List[Any]:
        if self.ws_server is None:
            return []
        return list(getattr(self.ws_server, "active_connections", []) or [])

    async def _pick_connection(self, device_id: str = "") -> Optional[Any]:
        wanted = (device_id or "").strip().lower()
        candidates = []
        for conn in self._connections():
            client = getattr(conn, "mcp_client", None)
            if client is None:
                continue
            if wanted and (getattr(conn, "device_id", "") or "").lower() != wanted:
                continue
            try:
                if not await client.is_ready():
                    continue
            except Exception:
                continue
            candidates.append(conn)
        if not candidates:
            return None
        candidates.sort(
            key=lambda c: float(getattr(c, "last_activity_time", 0) or 0),
            reverse=True,
        )
        return candidates[0]

    def _respond(self, data: Dict[str, Any], status: int = 200) -> web.Response:
        resp = web.Response(
            text=json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            content_type="application/json",
            status=status,
        )
        self._add_cors_headers(resp)
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resp

    # ------------------------------------------------------------ 路由

    async def handle_options(self, request):
        resp = web.Response(status=204)
        self._add_cors_headers(resp)
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resp

    async def handle_status(self, request):
        devices = []
        for conn in self._connections():
            client = getattr(conn, "mcp_client", None)
            ready = False
            try:
                ready = bool(client and await client.is_ready())
            except Exception:
                ready = False
            devices.append(
                {
                    "device_id": getattr(conn, "device_id", "") or "",
                    "mcp_ready": ready,
                }
            )
        return self._respond(
            {"ok": True, "count": len(devices), "devices": devices}
        )

    async def handle_say(self, request):
        """把文字合成成语音推给设备（edge-tts → ffmpeg PCM → Opus）。"""
        import os as _os
        import tempfile as _tf

        import edge_tts
        import imageio_ffmpeg
        import opuslib_next as opus
        import subprocess as _sp

        try:
            body = await request.json()
        except Exception:
            return self._respond({"ok": False, "error": "请求体不是合法 JSON"}, 400)

        text = str((body or {}).get("text") or "").strip()
        if not text:
            return self._respond({"ok": False, "error": "缺少 text"}, 400)

        conn = await self._pick_connection(str((body or {}).get("device_id") or ""))
        if conn is None:
            return self._respond({"ok": False, "error": "设备当前不在线"}, 409)

        from core.handle.sendAudioHandle import sendAudioMessage, send_tts_message
        from core.providers.tts.dto.dto import SentenceType

        voice, rate, pitch = "", "+0%", "+0Hz"
        # 音色/语速/音调以控制台「语音设置」为准，和主对话链路保持一致
        try:
            from core.utils.voice_settings import load as _load_vs

            vs = _load_vs()
            voice = str(vs.get("voice") or "")
            rate = vs.get("rate") or "+0%"
            pitch = vs.get("pitch_hz") or "+0Hz"
        except Exception:
            pass
        for attr in ("voice", "voice_name"):
            voice = voice or str(getattr(conn, attr, "") or "")
        tts_obj = getattr(conn, "tts", None)
        if not voice and tts_obj is not None:
            voice = str(getattr(tts_obj, "voice", "") or "")
        voice = voice or "zh-CN-XiaoyiNeural"

        mp3 = wav = None
        try:
            # 走统一合成入口：带缓存、12s 硬超时、熔断与兜底，避免这里成为绕过保护的长尾
            from core.providers.tts import edge as _edge

            data = await _edge.synthesize_bytes(text, voice, rate, pitch)
            if not data:
                return self._respond({"ok": False, "error": "合成结果为空"}, 500)
            f1 = _tf.NamedTemporaryFile(suffix=".mp3", delete=False)
            f1.write(data)
            f1.close()
            mp3 = f1.name

            wav = mp3 + ".wav"
            _sp.run(
                [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-i", mp3,
                 "-f", "s16le", "-acodec", "pcm_s16le", "-ar", "24000", "-ac", "1", wav],
                check=True, timeout=90,
            )
            pcm = open(wav, "rb").read()
            if not pcm:
                return self._respond({"ok": False, "error": "合成结果为空"}, 500)

            encoder = opus.Encoder(24000, 1, opus.APPLICATION_AUDIO)
            encoder.bitrate = 24000
            frame = 1440
            stride = frame * 2
            packets = []
            for i in range(0, len(pcm), stride):
                chunk = pcm[i:i + stride]
                if len(chunk) < stride:
                    chunk = chunk + b"\x00" * (stride - len(chunk))
                packets.append(encoder.encode(chunk, frame))

            conn.client_abort = False
            await send_tts_message(conn, "start")
            await sendAudioMessage(conn, SentenceType.FIRST, packets[:2], text)
            for i in range(2, len(packets)):
                await sendAudioMessage(conn, SentenceType.MIDDLE, [packets[i]], None)
                await asyncio.sleep(0.055)
            await sendAudioMessage(conn, SentenceType.LAST, [], None)
            await send_tts_message(conn, "stop")
            return self._respond({"ok": True, "spoken": True, "packets": len(packets), "voice": voice})
        except Exception as e:
            return self._respond({"ok": False, "error": f"播报失败: {e}"}, 500)
        finally:
            for p in (mp3, wav):
                try:
                    if p and _os.path.exists(p):
                        _os.unlink(p)
                except Exception:
                    pass



    async def handle_actions(self, request):
        """GET /api/console/actions：控制台动作面板的数据源（固件预设 + 服务端手势）。"""
        try:
            from core.utils.console_actions import action_catalog

            items = action_catalog()
        except Exception as e:
            return self._respond({"ok": False, "error": str(e)}, 500)
        return self._respond({"ok": True, "count": len(items), "actions": items})

    async def handle_action(self, request):
        """调用设备 MCP 工具（动作/舵机/灯珠），走 WebSocket 即时执行。"""
        import time as _t

        try:
            body = await request.json()
        except Exception:
            return self._respond({"ok": False, "error": "请求体不是合法 JSON"}, 400)

        body = body or {}
        tool = str(body.get("tool") or "").strip()
        action = str(body.get("action") or "").strip()
        arguments = body.get("arguments") or {}

        # 只给 action 时：先规范别名，再决定走手势引擎还是固件动作工具
        if not tool and action:
            from core.utils import gestures as _gestures
            from core.utils.console_actions import normalize_action

            action = normalize_action(action) or action
            if _gestures.is_gesture(action):
                conn = await self._pick_connection(str(body.get("device_id") or ""))
                if conn is None:
                    return self._respond({"ok": False, "error": "设备当前不在线"}, 409)
                started_g = _t.perf_counter()
                result = await _gestures.play(conn, action)
                latency_g = int((_t.perf_counter() - started_g) * 1000)
                if not result.get("ok"):
                    return self._respond(
                        {"ok": False, "action": action, "error": result.get("error"),
                         "latency_ms": latency_g}, 500
                    )
                return self._respond(
                    {"ok": True, "action": action, "kind": "gesture",
                     "label": result.get("label"), "frames": result.get("frames"),
                     "latency_ms": latency_g}
                )
            tool = "self.dog_action"
            arguments = {"action": action}
        if not tool:
            return self._respond({"ok": False, "error": "缺少 tool 或 action"}, 400)

        conn = await self._pick_connection(str(body.get("device_id") or ""))
        if conn is None:
            return self._respond({"ok": False, "error": "设备当前不在线"}, 409)

        started = _t.perf_counter()
        try:
            from core.providers.tools.device_mcp import call_mcp_tool
            from core.utils.util import sanitize_tool_name

            result = await asyncio.wait_for(
                call_mcp_tool(
                    conn,
                    conn.mcp_client,
                    sanitize_tool_name(tool),
                    json.dumps(arguments, ensure_ascii=False),
                    timeout=8,
                ),
                timeout=10,
            )
        except Exception as e:
            return self._respond({"ok": False, "error": f"调用失败: {e}"}, 500)

        latency = int((_t.perf_counter() - started) * 1000)
        return self._respond(
            {"ok": True, "tool": tool, "arguments": arguments,
             "latency_ms": latency, "result": result}
        )

    async def handle_play(self, request):
        """播放网络音频（音乐）。"""
        import httpx
        import opuslib_next as opus

        try:
            body = await request.json()
        except Exception:
            return self._respond({"ok": False, "error": "请求体不是合法 JSON"}, 400)

        url = str((body or {}).get("url") or "").strip()
        if not url.startswith("http"):
            return self._respond({"ok": False, "error": "缺少合法的 url"}, 400)

        conn = await self._pick_connection(str((body or {}).get("device_id") or ""))
        if conn is None:
            return self._respond({"ok": False, "error": "设备当前不在线"}, 409)

        from core.handle.sendAudioHandle import sendAudioMessage, send_tts_message
        from core.providers.tts.dto.dto import SentenceType

        ffmpeg = "ffmpeg"
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass

        async def _stream():
            from core.handle.receiveAudioHandle import _audio_lock_for, _interrupt_speaking

            lock = await _audio_lock_for(conn)
            async with lock:
                await _interrupt_speaking(conn)
                await _stream_locked()

        async def _stream_locked():
            sent = 0
            tmp = None
            try:
                async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as hc:
                    resp = await hc.get(url)
                    resp.raise_for_status()
                    data = resp.content

                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
                    fp.write(data)
                    tmp = fp.name

                loop = asyncio.get_running_loop()
                proc = await loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        [
                            ffmpeg, "-v", "error", "-nostdin", "-i", tmp,
                            "-f", "s16le", "-acodec", "pcm_s16le",
                            "-ar", "24000", "-ac", "1", "pipe:1",
                        ],
                        capture_output=True,
                        timeout=90,
                    ),
                )
                pcm = proc.stdout or b""
                if not pcm:
                    conn.logger.bind(tag=TAG).warning("解码无输出")
                    return
                conn.logger.bind(tag=TAG).info(f"已解码 {len(pcm)} 字节 PCM")

                encoder = opus.Encoder(24000, 1, opus.APPLICATION_AUDIO)
                encoder.bitrate = 24000
                frame = 1440
                stride = frame * 2
                packets = []
                for i in range(0, len(pcm), stride):
                    chunk = pcm[i : i + stride]
                    if len(chunk) < stride:
                        chunk = chunk + b"\x00" * (stride - len(chunk))
                    packets.append(encoder.encode(chunk, frame))

                conn.client_abort = False
                # 播放前：切到「享受音乐」表情
                await _set_emotion(conn, MUSIC_EMOTION)
                await send_tts_message(conn, "start")
                await sendAudioMessage(conn, SentenceType.FIRST, packets[:3], "")
                await asyncio.sleep(0.05)

                i = 3
                while i < len(packets):
                    if getattr(conn, "client_abort", False):
                        break
                    await sendAudioMessage(
                        conn, SentenceType.MIDDLE, packets[i : i + 1], None
                    )
                    i += 1
                    await asyncio.sleep(0.055)
                sent = i

                try:
                    await sendAudioMessage(conn, SentenceType.LAST, [], None)
                    await send_tts_message(conn, "stop")
                except Exception:
                    pass
            except Exception as e:
                conn.logger.bind(tag=TAG).warning(f"播放失败: {e}")
            finally:
                # 播放结束（含被打断）：恢复默认表情
                await _set_emotion(conn, DEFAULT_EMOTION)
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception:
                    pass
                conn.logger.bind(tag=TAG).info(f"播放结束：{sent} 帧")

        asyncio.create_task(_stream())
        return self._respond({"ok": True, "async": True, "stream": True})

    async def handle_stop(self, request):
        """停止当前播放。"""
        try:
            body = await request.json()
        except Exception:
            body = {}
        conn = await self._pick_connection(str((body or {}).get("device_id") or ""))
        if conn is None:
            return self._respond({"ok": False, "error": "设备当前不在线"}, 409)
        try:
            conn.client_abort = True
        except Exception:
            pass
        try:
            from core.handle.sendAudioHandle import send_tts_message

            await send_tts_message(conn, "stop")
        except Exception:
            pass
        return self._respond({"ok": True, "stopped": True})


    async def handle_sequence(self, request):
        """HTTP 入口：控制台「试播」→ 逐帧下发姿态。"""
        try:
            body = await request.json()
        except Exception:
            return self._respond({"ok": False, "error": "请求体不是合法 JSON"}, 400)

        steps = (body or {}).get("steps") or []
        if not isinstance(steps, list) or not steps:
            return self._respond({"ok": False, "error": "缺少 steps"}, 400)
        try:
            loops = int((body or {}).get("loops") or 1)
        except Exception:
            loops = 1

        conn = await self._pick_connection(str((body or {}).get("device_id") or ""))
        if conn is None:
            return self._respond({"ok": False, "error": "设备当前不在线"}, 409)

        try:
            result = await self._play_sequence(conn, steps, loops)
        except Exception as e:
            return self._respond({"ok": False, "error": f"播放失败: {e}"}, 500)
        return self._respond(result)

    async def _play_sequence(self, conn, steps, loops=1):
        """逐帧播放动作序列（调用固件 self.set_pose）。"""
        import asyncio as _aio
        import json as _json

        from core.providers.tools.device_mcp import call_mcp_tool

        total = 0
        failed = 0
        last_err = ""
        for _ in range(max(1, min(int(loops or 1), 20))):
            for step in steps or []:
                angles = str(step.get("angles") or "").strip()
                if not angles:
                    continue
                ms = int(step.get("ms") or 250)
                try:
                    await call_mcp_tool(conn, conn.mcp_client, "self.set_pose",
                                        _json.dumps({"angles": angles}), timeout=3)
                    total += 1
                except Exception as e:
                    # 单帧失败不中断整段编排（以前这里引用了不存在的 self._log，
                    # 直接 500，整段动作一个都不播）
                    failed += 1
                    last_err = f"{type(e).__name__}: {e}"
                    try:
                        self.logger.bind(tag="sequence").warning(
                            f"序列步骤失败 angles={angles}: {last_err}"
                        )
                    except Exception:
                        pass
                await _aio.sleep(max(0.05, ms / 1000.0))
        return {"ok": True, "frames": total, "failed": failed, "last_error": last_err}
