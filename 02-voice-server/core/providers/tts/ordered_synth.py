"""保序并发合成（V1.2 阶段一的核心组件）。

问题：`base.py::tts_text_priority_thread` 是「单线程 + 每句 asyncio.run(to_tts)」，
一句 2~7 秒，多句回答逐句累加。直接在原线程里加并发是无效的（asyncio.run 阻塞）。

本模块只做纯调度，不碰网络与队列：
    提交 (seq, fn) → 线程池执行 fn → **严格按 seq 顺序**取出已完成的结果。

顺序保证方式：只有「当前最小未取走 seq」完成了才允许取走；后面的先完成也先压着，
不会因为 2、3 句先合成完就抢在第 1 句前面播。

失败策略（V1.2 要求「失败必须推进 sequence」）：
    某一句抛异常或返回空时，take_ready 会把它作为失败项返回，调用方记一次失败并继续，
    绝不会让后续句子永久等待。
"""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Tuple


class OrderedSynth:
    def __init__(self, workers: int = 2, name: str = "tts-synth"):
        self._pool = ThreadPoolExecutor(max_workers=max(1, workers),
                                        thread_name_prefix=name)
        self._lock = threading.Lock()
        self._futures: Dict[int, Future] = {}
        self._meta: Dict[int, Any] = {}
        self._next = None          # 下一个允许取走的 seq（首次 submit 时对齐）
        self._closed = False

    # ---------------------------------------------------------------- 提交
    def submit(self, seq: int, fn: Callable[[], Any], meta: Any = None) -> None:
        with self._lock:
            if self._closed:
                return
            if self._next is None:
                self._next = seq          # 序号可以从 0 或 1 开始，以第一次提交为准
            self._futures[seq] = self._pool.submit(fn)
            self._meta[seq] = meta

    # ---------------------------------------------------------------- 取出
    def _try_take_locked(self) -> Tuple[bool, int, Any, Any]:
        """尝试取走当前 seq 的结果；返回 (是否有结果, seq, 结果或异常, meta)。"""
        fut = self._futures.get(self._next)
        if fut is None or not fut.done():
            return False, self._next, None, None
        seq = self._next
        self._futures.pop(seq, None)
        meta = self._meta.pop(seq, None)
        self._next = seq + 1
        try:
            return True, seq, fut.result(), meta
        except BaseException as exc:          # noqa: BLE001 - 失败也要推进 sequence
            return True, seq, exc, meta

    def take_ready(self, block_ms: int = 0) -> List[Tuple[int, bool, Any, Any]]:
        """取走「按序连续可用」的结果，返回 [(seq, ok, 值或异常, meta)]。

        - 严格按 seq 顺序：后面先完成也先压着，不会插队播出；
        - 失败项也会返回（ok=False），调用方据此推进 sequence，避免后面永久等待；
        - block_ms > 0 时最多等这么久（用于收尾 flush）。
        """
        import time

        out: List[Tuple[int, bool, Any, Any]] = []
        deadline = (time.time() + block_ms / 1000.0) if block_ms > 0 else None
        while True:
            with self._lock:
                fut = self._futures.get(self._next)
                if fut is None:
                    return out                    # 没有待取的，说明已经连续取完
                if not fut.done():
                    earliest = fut
                    completed = False
                else:
                    seq = self._next
                    self._futures.pop(seq, None)
                    meta = self._meta.pop(seq, None)
                    self._next = seq + 1
                    earliest = self._futures.get(self._next)
                    completed = True
            if completed:
                try:
                    out.append((seq, True, fut.result(), meta))
                except BaseException as exc:      # noqa: BLE001
                    out.append((seq, False, exc, meta))
                continue
            if earliest is None:
                return out
            if deadline is None:
                return out
            remain = deadline - time.time()
            if remain <= 0:
                return out
            try:
                earliest.result(timeout=min(0.1, remain))
            except BaseException:
                pass

    # ---------------------------------------------------------------- 状态
    def pending(self) -> int:
        with self._lock:
            return len(self._futures)

    def cancel_all(self) -> None:
        with self._lock:
            for fut in self._futures.values():
                fut.cancel()
            self._futures.clear()
            self._meta.clear()
            self._next = 0

    def shutdown(self) -> None:
        self.cancel_all()
        with self._lock:
            self._closed = True
        self._pool.shutdown(wait=False, cancel_futures=True)
