import json
from core.handle.abortHandle import handleAbortMessage
from core.handle.helloHandle import handleHelloMessage
from core.providers.tools.device_mcp import handle_mcp_message
from core.utils.util import remove_punctuation_and_length, filter_sensitive_info
from core.handle.receiveAudioHandle import startToChat, handleAudioMessage
from core.handle.sendAudioHandle import send_stt_message, send_tts_message
from core.providers.tools.device_iot import handleIotDescriptors, handleIotStatus
from core.handle.reportHandle import enqueue_asr_report
import asyncio




TAG = __name__


async def handleTextMessage(conn, message):
    """处理文本消息"""
    try:
        msg_json = json.loads(message)
        if isinstance(msg_json, int):
            conn.logger.bind(tag=TAG).info(f"收到文本消息：{message}")
            await conn.websocket.send(message)
            return
        if msg_json["type"] == "hello":
            conn.logger.bind(tag=TAG).info(f"收到hello消息：{message}")
            await handleHelloMessage(conn, msg_json)
        elif msg_json["type"] == "abort":
            conn.logger.bind(tag=TAG).info(f"收到abort消息：{message}")
            await handleAbortMessage(conn)
        elif msg_json["type"] == "listen":
            conn.logger.bind(tag=TAG).info(f"收到listen消息：{message}")
            if "mode" in msg_json:
                conn.client_listen_mode = msg_json["mode"]
                conn.logger.bind(tag=TAG).debug(
                    f"客户端拾音模式：{conn.client_listen_mode}"
                )
            if msg_json["state"] == "start":
                try:
                    from core.utils import latency as _lat

                    _lat.begin(conn)          # 新一轮开始，清空上一轮打点
                except Exception:
                    pass
                conn.client_have_voice = True
                conn.client_voice_stop = False
                # 设备已回到聆听：清掉服务端残留的说话/唤醒保护状态，
                # 否则长语音播完后会「界面聆听中但听不进去」
                try:
                    if conn.client_is_speaking or getattr(conn, "just_woken_up", False):
                        conn.logger.bind(tag=TAG).info("复位说话/唤醒状态（设备已回到聆听）")
                    conn.client_is_speaking = False
                    conn.just_woken_up = False
                    conn.client_abort = False
                    conn.client_have_voice = False
                    try:
                        conn.asr_audio.clear()
                    except Exception:
                        pass
                    try:
                        conn.clearSpeakStatus()
                    except Exception:
                        pass
                except Exception:
                    pass
                # 注意：这里不要再播问候，会打断聆听（已改到会话建立时播）
                # 用户开始说话：后台预热 TTS 连接，
                # 把到语音服务商的握手耗时与识别/生成重叠掉（实测省 600~800ms）
                try:
                    from core.utils.tts_warmup import warmup_tts

                    asyncio.create_task(warmup_tts(conn))
                except Exception:
                    pass
            elif msg_json["state"] == "stop":
                try:
                    from core.utils import latency as _lat

                    _lat.mark(conn, "t1")     # VAD 判停
                except Exception:
                    pass
                conn.client_have_voice = True
                conn.client_voice_stop = True
                if len(conn.asr_audio) > 0:
                    await handleAudioMessage(conn, b"")
            elif msg_json["state"] == "detect":
                try:
                    from core.utils import latency as _lat

                    _lat.mark(conn, "t1")
                except Exception:
                    pass
                conn.client_have_voice = False
                conn.asr_audio.clear()
                if "text" in msg_json:
                    original_text = msg_json["text"]  # 保留原始文本
                    if _is_junk_text(original_text):
                        conn.logger.bind(tag=TAG).info(
                            f"忽略无效识别: {original_text!r}"
                        )
                        await send_tts_message(conn, "stop", None)
                        conn.client_is_speaking = False
                        return
                    filtered_len, filtered_text = remove_punctuation_and_length(
                        original_text
                    )

                    # 识别是否是唤醒词
                    is_wakeup_words = filtered_text in conn.config.get("wakeup_words")
                    # 是否开启唤醒词回复
                    enable_greeting = conn.config.get("enable_greeting", True)

                    if is_wakeup_words and not enable_greeting:
                        # 如果是唤醒词，且关闭了唤醒词回复，就不用回答
                        await send_stt_message(conn, original_text)
                        await send_tts_message(conn, "stop", None)
                        conn.client_is_speaking = False
                    elif is_wakeup_words:
                        conn.just_woken_up = True
                        # 问候走固定短句，播完立刻恢复正常收音
                        conn.client_abort = False
                        # 上报纯文字数据（复用ASR上报功能，但不提供音频数据）
                        # 唤醒回应不走模型：固定短句直接播，避免冷启动等待
                        try:
                            from core.handle.receiveAudioHandle import _speak_ack
                            import random as _rd
                            _greets = ("嗯，我在呢。", "在的，你说吧。", "我在呀，什么事？")
                            await _speak_ack(conn, _rd.choice(_greets))
                        except Exception:
                            enqueue_asr_report(conn, "嘿，你好呀", [])
                            await startToChat(conn, "嘿，你好呀")
                    else:
                        # 上报纯文字数据（复用ASR上报功能，但不提供音频数据）
                        enqueue_asr_report(conn, original_text, [])
                        # 否则需要LLM对文字内容进行答复
                        await startToChat(conn, original_text)
        elif msg_json["type"] == "iot":
            conn.logger.bind(tag=TAG).info(f"收到iot消息：{message}")
            if "descriptors" in msg_json:
                asyncio.create_task(handleIotDescriptors(conn, msg_json["descriptors"]))
            if "states" in msg_json:
                asyncio.create_task(handleIotStatus(conn, msg_json["states"]))
        elif msg_json["type"] == "mcp":
            conn.logger.bind(tag=TAG).info(f"收到mcp消息：{message[:100]}")
            if "payload" in msg_json:
                asyncio.create_task(
                    handle_mcp_message(conn, conn.mcp_client, msg_json["payload"])
                )
        elif msg_json["type"] == "server":
            # 记录日志时过滤敏感信息
            conn.logger.bind(tag=TAG).info(
                f"收到服务器消息：{filter_sensitive_info(msg_json)}"
            )
            # 如果配置是从API读取的，则需要验证secret
            if not conn.read_config_from_api:
                return
            # 获取post请求的secret
            post_secret = msg_json.get("content", {}).get("secret", "")
            secret = ""
            # 如果secret不匹配，则返回
            if post_secret != secret:
                await conn.websocket.send(
                    json.dumps(
                        {
                            "type": "server",
                            "status": "error",
                            "message": "服务器密钥验证失败",
                        }
                    )
                )
                return
            # 动态更新配置
            if msg_json["action"] == "update_config":
                try:
                    # 更新WebSocketServer的配置
                    if not conn.server:
                        await conn.websocket.send(
                            json.dumps(
                                {
                                    "type": "server",
                                    "status": "error",
                                    "message": "无法获取服务器实例",
                                    "content": {"action": "update_config"},
                                }
                            )
                        )
                        return

                    if not await conn.server.update_config():
                        await conn.websocket.send(
                            json.dumps(
                                {
                                    "type": "server",
                                    "status": "error",
                                    "message": "更新服务器配置失败",
                                    "content": {"action": "update_config"},
                                }
                            )
                        )
                        return

                    # 发送成功响应
                    await conn.websocket.send(
                        json.dumps(
                            {
                                "type": "server",
                                "status": "success",
                                "message": "配置更新成功",
                                "content": {"action": "update_config"},
                            }
                        )
                    )
                except Exception as e:
                    conn.logger.bind(tag=TAG).error(f"更新配置失败: {str(e)}")
                    await conn.websocket.send(
                        json.dumps(
                            {
                                "type": "server",
                                "status": "error",
                                "message": f"更新配置失败: {str(e)}",
                                "content": {"action": "update_config"},
                            }
                        )
                    )
            # 重启服务器
            elif msg_json["action"] == "restart":
                await conn.handle_restart(msg_json)
        else:
            conn.logger.bind(tag=TAG).error(f"收到未知类型消息：{message}")
    except json.JSONDecodeError:
        await conn.websocket.send(message)


_ASR_JUNK = {
    "。", "，", "？", "！", ".", ",", "嗯", "啊", "哦", "呃",
    "Yeah.", "Okay.", "はい。", "はい", "Hello.",
}


def _is_junk_text(text: str) -> bool:
    """过滤 ASR 误识别出的空/噪声结果（单字、纯标点、常见语气词）。"""
    s = (text or "").strip()
    if not s:
        return True
    if s in _ASR_JUNK:
        return True
    if all(ch in "。，？！、.,?!~～ " for ch in s):
        return True
    if len(s) == 1 and s not in "坐趴起停走灯":
        return True
    return False
