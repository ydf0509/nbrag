"""
检索分词器：为 BM25 sparse retrieval 生成中英文、代码、结构化编号 token。

该模块只做文本归一化和 tokenization，不依赖 ChromaDB/config/core，避免把
存储逻辑混入 tokenizer。
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Iterable


BM25_CHANNELS = ("word", "ngram", "code")

_HEADER_RE = re.compile(r"^#\s*\[File:.*$", re.MULTILINE)
_CJK_SPAN_RE = re.compile(r"[\u4e00-\u9fff]+")
_CAMEL_SPLIT_RE = re.compile(r"([a-z0-9])([A-Z])")
_CAMEL_UPPER_RE = re.compile(r"([A-Z]+)([A-Z][a-z])")
_LATIN_OR_CODE_RE = re.compile(
    r"""
    [A-Za-z_][A-Za-z0-9_]*
    (?:[.\-/::]+[A-Za-z0-9_]+)*
    |
    \d+(?:\.\d+)*(?:%|ms|s|kg|g|mg|ug|ml|l|kb|mb|gb|tb)?
    """,
    re.VERBOSE,
)
_STRUCTURED_TERM_RE = re.compile(
    r"""
    第[一二三四五六七八九十百千万亿零〇两0-9]+[章节条款项编部]
    |
    [A-Z]{2,}(?:[_-][A-Z0-9]+)+
    |
    [A-Z]{2,}\s*\d+(?:\.\d+)*
    |
    [A-Za-z]+Error
    |
    \d+(?:\.\d+)?(?:%|ms|s|kg|g|mg|ug|ml|l|kb|mb|gb|tb)
    """,
    re.VERBOSE,
)

_loaded_jieba_dicts: set[str] = set()


def normalize_text(text: str) -> str:
    """Normalize text before lexical tokenization."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _HEADER_RE.sub(" ", text)
    return text


def _require_jieba():
    try:
        import jieba  # type: ignore
    except ImportError as exc:
        raise ImportError("nbrag BM25 tokenizer requires dependency: jieba") from exc
    return jieba


@lru_cache(maxsize=4)
def _get_pkuseg(user_dict: str | None = None):
    try:
        import pkuseg  # type: ignore
    except ImportError:
        return None
    if user_dict:
        return pkuseg.pkuseg(user_dict=user_dict)
    return pkuseg.pkuseg()


def _load_jieba_user_dict(user_dict: str | None) -> None:
    if not user_dict or user_dict in _loaded_jieba_dicts:
        return
    jieba = _require_jieba()
    jieba.load_userdict(user_dict)
    _loaded_jieba_dicts.add(user_dict)


def _dedupe_preserve_order(tokens: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for token in tokens:
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _identifier_parts(token: str) -> list[str]:
    """Return exact and split variants for English/code identifiers."""
    if not token:
        return []

    raw = token.strip()
    if not raw:
        return []

    variants = [raw.lower()]
    expanded = _CAMEL_SPLIT_RE.sub(r"\1 \2", raw)
    expanded = _CAMEL_UPPER_RE.sub(r"\1 \2", expanded)
    expanded = re.sub(r"[_\-./:]+", " ", expanded)
    for part in re.findall(r"[A-Za-z0-9]+", expanded):
        part = part.lower()
        if len(part) > 1 or part.isdigit():
            variants.append(part)

    return _dedupe_preserve_order(variants)


def _structured_terms(text: str) -> list[str]:
    tokens = []
    for match in _STRUCTURED_TERM_RE.finditer(text):
        term = re.sub(r"\s+", "", match.group(0))
        tokens.extend(_identifier_parts(term) if re.search(r"[A-Za-z]", term) else [term])
    return tokens


def _cjk_word_tokens(text: str, user_dict: str | None) -> list[str]:
    spans = [match.group(0) for match in _CJK_SPAN_RE.finditer(text)]
    if not spans:
        return []

    _load_jieba_user_dict(user_dict)
    jieba = _require_jieba()
    pku = _get_pkuseg(user_dict)

    tokens = []
    for span in spans:
        if 2 <= len(span) <= 16:
            tokens.append(span)
        if pku is not None:
            tokens.extend(tok for tok in pku.cut(span) if len(tok) > 1)
        tokens.extend(tok for tok in jieba.cut_for_search(span) if len(tok) > 1)
    return tokens


def _latin_word_tokens(text: str) -> list[str]:
    tokens = []
    for match in _LATIN_OR_CODE_RE.finditer(text):
        tokens.extend(_identifier_parts(match.group(0)))
    return tokens


def tokenize_word(text: str, *, user_dict: str | None = None) -> list[str]:
    """Tokenize multilingual prose plus structured terms for the word BM25 channel."""
    normalized = normalize_text(text)
    tokens = []
    tokens.extend(_structured_terms(normalized))
    tokens.extend(_cjk_word_tokens(normalized, user_dict))
    tokens.extend(_latin_word_tokens(normalized))
    return _dedupe_preserve_order(tokens)


def tokenize_cjk_ngram(text: str, *, n_values: tuple[int, ...] = (2, 3)) -> list[str]:
    """Generate Chinese 2/3-gram tokens for recall-oriented BM25 search."""
    normalized = normalize_text(text)
    tokens = []
    for match in _CJK_SPAN_RE.finditer(normalized):
        span = match.group(0)
        for n in n_values:
            if len(span) < n:
                continue
            tokens.extend(span[i:i + n] for i in range(len(span) - n + 1))
    return tokens


def tokenize_code(text: str) -> list[str]:
    """Tokenize code identifiers, API names, paths, constants, and error-like symbols."""
    normalized = normalize_text(text)
    tokens = []
    for match in _LATIN_OR_CODE_RE.finditer(normalized):
        token = match.group(0)
        if re.search(r"[A-Za-z_./:\-]", token):
            tokens.extend(_identifier_parts(token))
    tokens.extend(_structured_terms(normalized))
    return _dedupe_preserve_order(tokens)


def tokenize_all(text: str, *, user_dict: str | None = None) -> dict[str, list[str]]:
    """Return tokens for all BM25 channels."""
    return {
        "word": tokenize_word(text, user_dict=user_dict),
        "ngram": tokenize_cjk_ngram(text),
        "code": tokenize_code(text),
    }


def tokenize_query_all(query: str, *, user_dict: str | None = None) -> dict[str, list[str]]:
    """Return query tokens for all BM25 channels."""
    return tokenize_all(query, user_dict=user_dict)
