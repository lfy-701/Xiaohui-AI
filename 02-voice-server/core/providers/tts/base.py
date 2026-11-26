import os
import re
import queue
import uuid
import asyncio
import threading
from core.utils import p3
from datetime import datetime
from core.utils import textUtils
from abc import ABC, abstractmethod
from config.logger import setup_logging
from core.utils.util import audio_to_data, audio_bytes_to_data
from core.utils.tts import MarkdownCleaner
from core.utils.output_counter import add_device_output
from core.handle.reportHandle import enqueue_tts_report
from core.handle.sendAudioHandle import sendAudioMessage
from core.providers.tts.dto.dto import (
    TTSMessageDTO,
    SentenceType,
    ContentType,
    InterfaceType,
)

import traceback

TAG = __name__
logger = setup_logging()


class TTSProviderBase(ABC):
    def __init__(self, config, delete_audio_file):
        self.interface_type = InterfaceType.NON_STREAM
        self.conn = None
        self.tts_timeout = 10
        self.delete_audio_file = delete_audio_file
        self.audio_file_type = "wav"
        self.output_file = config.get("output_dir", "tmp/")
        self.tts_text_queue = queue.Queue()
        self.tts_audio_queue = queue.Queue()
        self.tts_audio_first_sentence = True
        self.before_stop_play_files = []

        self.tts_text_buff = []
        self.punctuations = (
            "。",
            "？",
            "?",
            "！",
            "!",
            "；",
            ";",
            "：",
        )
        self.first_sentence_punctuations = (
            "，",
            "～",
            "~",
            "、",
            ",",
            "。",
            "？",
            "?",
            "！",
            "!",
            "；",
            ";",
            "：",
        )
        self.tts_stop_request = False
        self.processed_chars = 0
        self.is_first_sentence = True

        # ---- 阶段一：多句有序并发预合成（默认关闭，TTS_CONCURRENCY=2 开启）----
        # 关闭时走原来的串行路径，保证可随时回退（V1.2 要求保留旧实现）。
        try:
            self._conc = max(1, int(os.getenv("TTS_CONCURRENCY", "1")))
        except Exception:
            self._conc = 1
        self._order = None          # OrderedSynth 实例（并发时才创建）
        self._synth_seq = 0
        self._synth_meta = {}

    def generate_filename(self, extension=".wav"):
        return os.path.join(
            self.output_file,
            f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}",
        )

    # ------------------------------------------------ 阶段一：有序并发预合成
    def _synth_one(self, text):
        """合成一句，统一返回可直接入队的 audio_datas。"""
        if self.delete_audio_file:
            data = self.to_tts(text)
        else:
            tts_file = self.to_tts(text)
            data = self._process_audio_file(tts_file) if tts_file else None
        # 阶段零打点：T6 = TTS 首个音频块就绪
        if data:
            try:
                from core.utils import latency as _lat

                _lat.mark(self.conn, "t6")
            except Exception:
                pass
        return data

    def _pipeline_reset(self):
        """每轮开始/打断时复位并发管线（取消未完成的任务）。"""
        try:
            if self._order is not None:
                self._order.cancel_all()
                self._order.shutdown()
        except Exception:
            pass
        self._order = None
        self._synth_seq = 0
        self._synth_meta.clear()
        if getattr(self, "_conc", 1) > 1:
            try:
                from core.providers.tts.ordered_synth import OrderedSynth

                self._order = OrderedSynth(self._conc)
            except Exception as e:
                logger.bind(tag=TAG).warning(f"并发合成初始化失败，回退串行：{e}")
                self._order = None

    def _synth_submit(self, text, stype) -> bool:
        """提交一句到并发管线；返回 False 表示应走原来的串行路径。"""
        if self._order is None:
            return False
        self._synth_seq += 1
        seq = self._synth_seq
        self._synth_meta[seq] = (stype, text)
        try:
            self._order.submit(seq, lambda t=text: self._synth_one(t), meta=(stype, text))
        except Exception as e:
            logger.bind(tag=TAG).warning(f"提交合成失败，改走串行：{e}")
            return False
        self._synth_drain()
        return True

    def _synth_drain(self, block_ms=0) -> int:
        """按序取出已完成的结果并入播放队列；失败项跳过但推进序号。"""
        if self._order is None:
            return 0
        emitted = 0
        try:
            for seq, ok, value, meta in self._order.take_ready(block_ms=block_ms):
                stype, text = (meta if meta else (None, ""))
                if ok and value:
                    self.tts_audio_queue.put((stype, value, text))
                    emitted += 1
                else:
                    logger.bind(tag=TAG).warning(
                        f"第 {seq} 句合成失败（跳过并继续后续）：{value}"
                    )
        except Exception as e:
            logger.bind(tag=TAG).warning(f"并发合成取结果异常：{e}")
        return emitted

    def _synth_flush(self, timeout_s: float = 60.0) -> None:
        """收尾：把剩余未发出的按序发完（超时放弃，避免卡住整轮）。"""
        if self._order is None:
            return
        import time as _t

        deadline = _t.time() + timeout_s
        while self._order.pending() > 0 and _t.time() < deadline:
            self._synth_drain(block_ms=200)

    def to_tts(self, text):
        text = MarkdownCleaner.clean_markdown(text)
        max_repeat_time = 5
        if self.delete_audio_file:
            # 需要删除文件的直接转为音频数据
            while max_repeat_time > 0:
                try:
                    audio_bytes = asyncio.run(self.text_to_speak(text, None))
                    if audio_bytes:
                        audio_datas, _ = audio_bytes_to_data(
                            audio_bytes, file_type=self.audio_file_type, is_opus=True
                        )
                        return audio_datas
                    else:
                        max_repeat_time -= 1
                except Exception as e:
                    # provider 自己已经做过超时与有限重试，这里再重试 5 轮会变成
                    # 「24 秒长尾」。TTSUnavailable 表示已彻底不可用，直接放弃本句。
                    if type(e).__name__ == "TTSUnavailable":
                        logger.bind(tag=TAG).error(f"语音服务不可用，跳过本句: {text}")
                        return None
                    logger.bind(tag=TAG).warning(
                        f"语音生成失败{5 - max_repeat_time + 1}次: {text}，错误: {e}"
                    )
                    max_repeat_time -= 1
            if max_repeat_time > 0:
                logger.bind(tag=TAG).info(
                    f"语音生成成功: {text}，重试{5 - max_repeat_time}次"
                )
            else:
                logger.bind(tag=TAG).error(
                    f"语音生成失败: {text}，请检查网络或服务是否正常"
                )
            return None
        else:
            tmp_file = self.generate_filename()
            try:
                while not os.path.exists(tmp_file) and max_repeat_time > 0:
                    try:
                        asyncio.run(self.text_to_speak(text, tmp_file))
                    except Exception as e:
                        logger.bind(tag=TAG).warning(
                            f"语音生成失败{5 - max_repeat_time + 1}次: {text}，错误: {e}"
                        )
                        # 未执行成功，删除文件
                        if os.path.exists(tmp_file):
                            os.remove(tmp_file)
                        max_repeat_time -= 1

                if max_repeat_time > 0:
                    logger.bind(tag=TAG).info(
                        f"语音生成成功: {text}:{tmp_file}，重试{5 - max_repeat_time}次"
                    )
                else:
                    logger.bind(tag=TAG).error(
                        f"语音生成失败: {text}，请检查网络或服务是否正常"
                    )

                return tmp_file
            except Exception as e:
                logger.bind(tag=TAG).error(f"Failed to generate TTS file: {e}")
                return None

    @abstractmethod
    async def text_to_speak(self, text, output_file):
        pass

    def audio_to_pcm_data(self, audio_file_path):
        """音频文件转换为PCM编码"""
        return audio_to_data(audio_file_path, is_opus=False)

    def audio_to_opus_data(self, audio_file_path):
        """音频文件转换为Opus编码"""
        return audio_to_data(audio_file_path, is_opus=True)

    def tts_one_sentence(
        self,
        conn,
        content_type,
        content_detail=None,
        content_file=None,
        sentence_id=None,
    ):
        """发送一句话"""
        if not sentence_id:
            if conn.sentence_id:
                sentence_id = conn.sentence_id
            else:
                sentence_id = str(uuid.uuid4()).replace("-", "")
                conn.sentence_id = sentence_id
        self.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=sentence_id,
                sentence_type=SentenceType.FIRST,
                content_type=ContentType.ACTION,
            )
        )
        # 对于单句的文本，进行分段处理
        segments = re.split(r"([。！？!?；;\n])", content_detail)
        for seg in segments:
            self.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=content_type,
                    content_detail=seg,
                    content_file=content_file,
                )
            )
        self.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=sentence_id,
                sentence_type=SentenceType.LAST,
                content_type=ContentType.ACTION,
            )
        )

    async def open_audio_channels(self, conn):
        self.conn = conn
        self.tts_timeout = conn.config.get("tts_timeout", 10)
        # tts 消化线程
        self.tts_priority_thread = threading.Thread(
            target=self.tts_text_priority_thread, daemon=True
        )
        self.tts_priority_thread.start()

        # 音频播放 消化线程
        self.audio_play_priority_thread = threading.Thread(
            target=self._audio_play_priority_thread, daemon=True
        )
        self.audio_play_priority_thread.start()

    # 这里默认是非流式的处理方式
    # 流式处理方式请在子类中重写
    def tts_text_priority_thread(self):
        while not self.conn.stop_event.is_set():
            try:
                message = self.tts_text_queue.get(timeout=1)
                if self.conn.client_abort:
                    logger.bind(tag=TAG).info("收到打断信息，终止TTS文本处理线程")
                    self._pipeline_reset()
                    continue
                if message.sentence_type == SentenceType.FIRST:
                    # 初始化参数
                    self.tts_stop_request = False
                    self.processed_chars = 0
                    self.tts_text_buff = []
                    self.is_first_sentence = True
                    self.tts_audio_first_sentence = True
                    self._pipeline_reset()
                elif ContentType.TEXT == message.content_type:
                    self.tts_text_buff.append(message.content_detail)
                    segment_text = self._get_segment_text()
                    if segment_text:
                        # 阶段零打点：T5 = 首个可朗读句子就绪
                        try:
                            from core.utils import latency as _lat

                            _lat.mark(self.conn, "t5")
                            _lat.sentence(self.conn)
                        except Exception:
                            pass
                        import time as _t0

                        _t_start = _t0.time()
                        # 并发路径：提交后立刻返回，按序结果由 _synth_drain 入队
                        if not self._synth_submit(segment_text, message.sentence_type):
                            if self.delete_audio_file:
                                audio_datas = self.to_tts(segment_text)
                                if audio_datas:
                                    self.tts_audio_queue.put(
                                        (message.sentence_type, audio_datas, segment_text)
                                    )
                            else:
                                tts_file = self.to_tts(segment_text)
                                if tts_file:
                                    audio_datas = self._process_audio_file(tts_file)
                                    self.tts_audio_queue.put(
                                        (message.sentence_type, audio_datas, segment_text)
                                    )
                            logger.bind(tag="tts_time").info(
                                f"[TTS计时] 合成 {len(segment_text)} 字 用时 {_t0.time()-_t_start:.1f}s"
                            )
                        else:
                            logger.bind(tag="tts_time").info(
                                f"[TTS计时] 已提交并发合成 {len(segment_text)} 字（排队中）"
                            )
                elif ContentType.FILE == message.content_type:
                    self._process_remaining_text()
                    tts_file = message.content_file
                    if tts_file and os.path.exists(tts_file):
                        audio_datas = self._process_audio_file(tts_file)
                        self.tts_audio_queue.put(
                            (message.sentence_type, audio_datas, message.content_detail)
                        )

                if message.sentence_type == SentenceType.LAST:
                    self._process_remaining_text()
                    self._synth_flush()          # 并发路径：把剩余按序发完再收尾
                    self.tts_audio_queue.put(
                        (message.sentence_type, [], message.content_detail)
                    )

            except queue.Empty:
                continue
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"处理TTS文本失败: {str(e)}, 类型: {type(e).__name__}, 堆栈: {traceback.format_exc()}"
                )
                continue

    def _audio_play_priority_thread(self):
        while not self.conn.stop_event.is_set():
            text = None
            try:
                try:
                    sentence_type, audio_datas, text = self.tts_audio_queue.get(
                        timeout=1
                    )
                    logger.bind(tag="tts_time").info(
                        f"[TTS计时] 取出待播 {len(audio_datas or [])} 帧"
                    )
                except queue.Empty:
                    if self.conn.stop_event.is_set():
                        break
                    continue
                future = asyncio.run_coroutine_threadsafe(
                    sendAudioMessage(self.conn, sentence_type, audio_datas, text),
                    self.conn.loop,
                )
                future.result()
                if self.conn.max_output_size > 0 and text:
                    add_device_output(self.conn.headers.get("device-id"), len(text))
                enqueue_tts_report(self.conn, text, audio_datas)
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"audio_play_priority priority_thread: {text} {e}"
                )

    async def start_session(self, session_id):
        pass

    async def finish_session(self, session_id):
        pass

    async def close(self):
        """资源清理方法"""
        if hasattr(self, "ws") and self.ws:
            await self.ws.close()

    def _get_segment_text(self):
        # 合并当前全部文本并处理未分割部分
        full_text = "".join(self.tts_text_buff)
        current_text = full_text[self.processed_chars :]  # 从未处理的位置开始
        last_punct_pos = -1

        # 根据是否是第一句话选择不同的标点符号集合
        punctuations_to_use = (
            self.first_sentence_punctuations
            if self.is_first_sentence
            else self.punctuations
        )

        for punct in punctuations_to_use:
            pos = current_text.rfind(punct)
            if (pos != -1 and last_punct_pos == -1) or (
                pos != -1 and pos < last_punct_pos
            ):
                last_punct_pos = pos

        if last_punct_pos != -1:
            segment_text_raw = current_text[: last_punct_pos + 1]
            segment_text = textUtils.get_string_no_punctuation_or_emoji(
                segment_text_raw
            )
            self.processed_chars += len(segment_text_raw)  # 更新已处理字符位置

            # 如果是第一句话，在找到第一个逗号后，将标志设置为False
            if self.is_first_sentence:
                self.is_first_sentence = False

            return segment_text
        elif self.tts_stop_request and current_text:
            segment_text = current_text
            self.is_first_sentence = True  # 重置标志
            return segment_text
        else:
            return None

    def _process_audio_file(self, tts_file):
        """处理音频文件并转换为指定格式

        Args:
            tts_file: 音频文件路径
            content_detail: 内容详情

        Returns:
            tuple: (sentence_type, audio_datas, content_detail)
        """
        audio_datas = []
        if tts_file.endswith(".p3"):
            audio_datas, _ = p3.decode_opus_from_file(tts_file)
        elif self.conn.audio_format == "pcm":
            audio_datas, _ = self.audio_to_pcm_data(tts_file)
        else:
            audio_datas, _ = self.audio_to_opus_data(tts_file)

        if (
            self.delete_audio_file
            and tts_file is not None
            and os.path.exists(tts_file)
            and tts_file.startswith(self.output_file)
        ):
            os.remove(tts_file)
        return audio_datas

    def _process_before_stop_play_files(self):
        for tts_file, text in self.before_stop_play_files:
            if tts_file and os.path.exists(tts_file):
                audio_datas = self._process_audio_file(tts_file)
                self.tts_audio_queue.put((SentenceType.MIDDLE, audio_datas, text))
        self.before_stop_play_files.clear()
        self.tts_audio_queue.put((SentenceType.LAST, [], None))

    def _process_remaining_text(self):
        """处理剩余的文本并生成语音

        Returns:
            bool: 是否成功处理了文本
        """
        full_text = "".join(self.tts_text_buff)
        remaining_text = full_text[self.processed_chars :]
        if remaining_text:
            segment_text = textUtils.get_string_no_punctuation_or_emoji(remaining_text)
            if segment_text:
                if self.delete_audio_file:
                    audio_datas = self.to_tts(segment_text)
                    if audio_datas:
                        self.tts_audio_queue.put(
                            (SentenceType.MIDDLE, audio_datas, segment_text)
                        )
                else:
                    tts_file = self.to_tts(segment_text)
                    audio_datas = self._process_audio_file(tts_file)
                    self.tts_audio_queue.put(
                        (SentenceType.MIDDLE, audio_datas, segment_text)
                    )
                self.processed_chars += len(full_text)
                return True
        return False
