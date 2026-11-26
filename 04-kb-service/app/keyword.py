"""中文关键词检索（BM25），作为 hash 向量不可用时的兜底。

hash embedding 的相似度几乎是噪声（实测「怎么唤醒」搜不到「唤醒词」），
所以当 embedding 退化为 hash 时，直接走关键词打分，效果反而靠谱。
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Tuple

try:
    import jieba

    _HAS_JIEBA = True
except Exception:  # pragma: no cover
    _HAS_JIEBA = False

# 中文停用词（极简版，够用）
_STOP = set("的 了 是 在 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这 那 吗 呢 吧 啊 呀 么 怎么 什么 怎样 如何 可以 能不能 需要 应该 请问".split())


def tokenize(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text or "")
    if _HAS_JIEBA:
        words = jieba.lcut(text)
    else:
        # 退化：按字切，中文双字组合
        words = re.findall(r"[\u4e00-\u9fff]{1,2}|[a-zA-Z0-9]+", text)
    out = []
    for w in words:
        w = w.strip().lower()
        if not w or w in _STOP:
            continue
        if len(w) == 1 and not re.match(r"[a-zA-Z0-9]", w):
            continue
        out.append(w)

    # 追加中文二元组：jieba 会把「锂电池」切成一个整词，
    # 不加这一层的话用「电池」就搜不到。
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        for i in range(len(seg) - 1):
            bg = seg[i:i + 2]
            if bg not in _STOP:
                out.append(bg)
    return out


def bm25_scores(query: str, docs: List[Tuple[str, str]], k1: float = 1.5, b: float = 0.75) -> Dict[str, float]:
    """docs = [(id, text)]，返回 {id: 归一化分数 0~1}"""
    if not docs:
        return {}
    q_terms = tokenize(query)
    if not q_terms:
        return {}

    tokenized = [(did, tokenize(text)) for did, text in docs]
    n = len(tokenized)
    avg_len = sum(len(t) for _, t in tokenized) / n or 1.0

    # 文档频率
    df: Dict[str, int] = {}
    for _, toks in tokenized:
        for w in set(toks):
            df[w] = df.get(w, 0) + 1

    idf = {w: math.log(1 + (n - df.get(w, 0) + 0.5) / (df.get(w, 0) + 0.5)) for w in set(q_terms)}

    scores: Dict[str, float] = {}
    for did, toks in tokenized:
        tf: Dict[str, int] = {}
        for w in toks:
            tf[w] = tf.get(w, 0) + 1
        dl = len(toks) or 1
        s = 0.0
        for w in q_terms:
            if w not in tf:
                continue
            f = tf[w]
            s += idf[w] * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avg_len))
        if s > 0:
            scores[did] = s

    if not scores:
        return {}
    top = max(scores.values())
    return {k: v / top for k, v in scores.items()}
