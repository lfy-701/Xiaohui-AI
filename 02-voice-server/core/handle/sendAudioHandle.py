import json
import asyncio
import time
from core.providers.tts.dto.dto import SentenceType
from core.utils.util import get_string_no_punctuation_or_emoji, analyze_emotion
from loguru import logger

TAG = __name__

emoji_map = {
    "neutral": "😶",
    "happy": "🙂",
    "laughing": "😆",
    "funny": "😂",
    "sad": "😔",
    "angry": "😠",
    "crying": "😭",
    "loving": "😍",
    "embarrassed": "😳",
    "surprised": "😲",
    "shocked": "😱",
    "thinking": "🤔",
    "winking": "😉",
    "cool": "😎",
    "relaxed": "😌",
    "delicious": "🤤",
    "kissy": "😘",
    "confident": "😏",
    "sleepy": "😴",
    "silly": "😜",
    "confused": "🙄",
}


async def sendAudioMessage(conn, sentenceType, audios, text):
    # 阶段零打点：T7 = 本轮首个 Opus 帧发出。
    # 只有本轮已经产出过句子（T5 存在）才记 T7，否则上一轮还在排队的音频帧
    # 会把 T7 记到本轮之外（实测出现过 T7 早于 T6）。
    try:
        from core.utils import latency as _lat

        _st = getattr(conn, "_lat", None)
        if isinstance(_st, dict) and "t5" in _st:
            _lat.mark(conn, "t7")
    except Exception:
        pass
    # 帧级日志会刷爆文件（实测 10 分钟 3.9MB），只在首句/末句打 INFO，中间帧降到 DEBUG
    _is_edge = str(getattr(sentenceType, "name", sentenceType)) in ("FIRST", "LAST")
    _lg = conn.logger.bind(tag=TAG)
    if _is_edge:
        _lg.info(f"发送音频消息: {sentenceType}, {text}")
    else:
        _lg.debug(f"发送音频消息: {sentenceType}, {text}")
    if text is not None:
        emotion = analyze_emotion(text)
        emoji = emoji_map.get(emotion, "🙂")  # 默认使用笑脸
        await conn.websocket.send(
            json.dumps(
                {
                    "type": "llm",
                    "text": emoji,
                    "emotion": emotion,
                    "session_id": conn.session_id,
                }
            )
        )
    pre_buffer = False
    if conn.tts.tts_audio_first_sentence and text is not None:
        conn.logger.bind(tag=TAG).info(f"发送第一段语音: {text}")
        conn.tts.tts_audio_first_sentence = False
        pre_buffer = True
        # 防御：如果这段回复开始前设备被某个 stop（看门狗 / 打断）带回聆听态，
        # 后面推的音频会被它丢掉，表现就是「有回复但没声音」。补一个 start 兜住。
        if not getattr(conn, "client_is_speaking", False):
            conn.logger.bind(tag=TAG).info("检测到说话状态已复位，补发 tts start")
            await send_tts_message(conn, "start")
            conn.client_is_speaking = True

    await send_tts_message(conn, "sentence_start", text)

    await sendAudio(conn, audios, pre_buffer)

    await send_tts_message(conn, "sentence_end", text)

    # 发送结束消息：最后一段必须无条件收尾。
    # 以前这里要求 llm_finish_task 已置位，一旦竞态（模型仍在收尾 / 被打断），
    # 这个 stop 就永远不发，设备会一直停在「说话中」回不到聆听。
    if sentenceType == SentenceType.LAST:
        # 阶段零：本轮结束，输出一行打点 JSON（打点失败不影响收尾）
        try:
            from core.utils import latency as _lat

            _lat.flush(conn, route=str(getattr(conn, "_last_route", "") or ""),
                       model=str(getattr(conn, "_last_model", "") or ""))
        except Exception:
            pass
        await send_tts_message(conn, "stop", None)
        conn.client_is_speaking = False
        if conn.close_after_chat and conn.llm_finish_task:
            await conn.close()
        else:
            asyncio.create_task(_send_tail_stop(conn))


async def _send_tail_stop(conn, delay: float = 1.2):
    """补一发 tts stop。

    设备端还有缓冲音频时，第一发 stop 可能被它自己的播放队列吃掉，
    表现出来就是「故事讲完了却一直显示说话中」。隔一会儿再补一发即可；
    若这期间已经开始了新的回复（client_is_speaking=True），说明新的
    start 已经生效，此时不能再发 stop，否则会把新回复掐掉。
    """
    try:
        await asyncio.sleep(delay)
        if getattr(conn, "client_is_speaking", False):
            return
        await send_tts_message(conn, "stop", None)
    except Exception:
        pass


# 播放音频
async def sendAudio(conn, audios, pre_buffer=True):
    if audios is None or len(audios) == 0:
        return
    # 流控参数优化
    frame_duration = 60  # 帧时长（毫秒），匹配 Opus 编码
    start_time = time.perf_counter()
    play_position = 0
    last_reset_time = time.perf_counter()  # 记录最后的重置时间

    # 仅当第一句话时执行预缓冲
    if pre_buffer:
        pre_buffer_frames = min(3, len(audios))
        for i in range(pre_buffer_frames):
            await conn.websocket.send(audios[i])
        remaining_audios = audios[pre_buffer_frames:]
    else:
        remaining_audios = audios

    # 播放剩余音频帧
    for opus_packet in remaining_audios:
        if conn.client_abort:
            break

        # 重置没有声音的状态
        conn.last_activity_time = time.time() * 1000

        # 计算预期发送时间
        expected_time = start_time + (play_position / 1000)
        current_time = time.perf_counter()
        delay = expected_time - current_time
        if delay > 0:
            await asyncio.sleep(delay)

        await conn.websocket.send(opus_packet)

        play_position += frame_duration


async def send_tts_message(conn, state, text=None):
    """发送 TTS 状态消息"""
    message = {"type": "tts", "state": state, "session_id": conn.session_id}
    if text is not None:
        message["text"] = text

    # TTS播放结束
    if state == "stop":
        # 播放提示音
        tts_notify = conn.config.get("enable_stop_tts_notify", False)
        if tts_notify:
            stop_tts_notify_voice = conn.config.get(
                "stop_tts_notify_voice", "config/assets/tts_notify.mp3"
            )
            audios, _ = conn.tts.audio_to_opus_data(stop_tts_notify_voice)
            await sendAudio(conn, audios)
        # 清除服务端讲话状态
        conn.clearSpeakStatus()

    # 发送消息到客户端
    await conn.websocket.send(json.dumps(message))



async def send_stt_message(conn, text):
    end_prompt_str = conn.config.get("end_prompt", {}).get("prompt")
    if end_prompt_str and end_prompt_str == text:
        await send_tts_message(conn, "start")
        return

    """发送 STT 状态消息"""
    stt_text = get_string_no_punctuation_or_emoji(text)
    await conn.websocket.send(
        json.dumps({"type": "stt", "text": stt_text, "session_id": conn.session_id})
    )
    conn.client_is_speaking = True
    await send_tts_message(conn, "start")
