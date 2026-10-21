"""离线哈希向量。

为什么不用真模型：
- 现场可能没有 Embedding API，也可能没有 GPU；
- 交付阶段的首要目标是"稳定可演示"，而不是最高召回率。

做法：字符 2/3-gram + 英文单词，按 crc32 散列到固定维度后 L2 归一化。
它是**词面相似度**，不是语义向量；配合字面覆盖率做混合打分，够用于课程资料问答。
"""

from __future__ import annotations

import re
import zlib

import numpy as np

EMBED_DIM = 512
EMBED_VERSION = "hash-char-ngram-v1"

_ASCII_WORD = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]{1,}")
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")


def _features(text: str) -> list[str]:
    lowered = text.lower()
    features: list[str] = [word for word in _ASCII_WORD.findall(lowered)]
    for run in _CJK_RUN.findall(lowered):
        for size in (2, 3):
            for index in range(len(run) - size + 1):
                features.append(run[index : index + size])
    return features


def embed_text(text: str, dim: int = EMBED_DIM) -> list[float]:
    vector = np.zeros(dim, dtype=np.float32)
    for feature in _features(text):
        slot = zlib.crc32(feature.encode("utf-8")) % dim
        vector[slot] += 1.0
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        return vector.tolist()
    return (vector / norm).tolist()


def embed_batch(texts: list[str], dim: int = EMBED_DIM) -> list[list[float]]:
    return [embed_text(text, dim) for text in texts]


def lexical_coverage(query: str, text: str) -> float:
    """查询词在文本中的覆盖比例，用于和余弦分数做混合。"""
    query_features = set(_features(query))
    if not query_features:
        return 0.0
    text_features = set(_features(text))
    return len(query_features & text_features) / len(query_features)
