"""文档解析 + 切片。支持 PDF / Word / Markdown / 纯文本。"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import List, Tuple

from .config import settings


def extract_text(filename: str, raw: bytes) -> str:
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(parts)

    if ext in (".docx", ".doc"):
        if ext == ".doc":
            raise ValueError("暂不支持老式 .doc，请另存为 .docx")
        from docx import Document

        doc = Document(io.BytesIO(raw))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(c.text.strip() for c in row.cells))
        return "\n".join(parts)

    # markdown / txt / 其他按文本处理
    for enc in ("utf-8", "gb18030", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _overlap_tail(text: str, overlap: int) -> str:
    """取上一块末尾作为重叠部分，并对齐到句子边界，避免新块从半句话开始。"""
    if overlap <= 0 or not text:
        return ""
    tail = text[-overlap:]
    # 往后找到第一个句末标点，从它之后开始
    m = re.search(r"[。！？!?]\s*|\n", tail)
    if m and m.end() < len(tail):
        tail = tail[m.end():]
    return tail.strip()


def split_chunks(text: str, size: int | None = None, overlap: int | None = None) -> List[str]:
    """按段落聚合到 size，相邻块留 overlap，避免句子被切断。"""
    size = size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    text = _clean(text)
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    buf = ""

    for para in paragraphs:
        # 单段就超长：按句子再切
        if len(para) > size:
            sentences = re.split(r"(?<=[。！？.!?])\s*", para)
            for s in sentences:
                if not s:
                    continue
                if len(buf) + len(s) <= size:
                    buf += s
                else:
                    if buf:
                        chunks.append(buf.strip())
                    buf = (_overlap_tail(chunks[-1], overlap) + s) if chunks else s
            continue

        if len(buf) + len(para) + 1 <= size:
            buf = f"{buf}\n{para}" if buf else para
        else:
            if buf:
                chunks.append(buf.strip())
            tail = _overlap_tail(chunks[-1], overlap) if chunks else ""
            buf = (tail + "\n" + para).strip() if tail else para

    if buf.strip():
        chunks.append(buf.strip())

    return [c for c in chunks if len(c) >= 10]


def parse_and_split(filename: str, raw: bytes) -> Tuple[str, List[str]]:
    text = extract_text(filename, raw)
    return text, split_chunks(text)
