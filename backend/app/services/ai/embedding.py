"""F5: 임베딩 생성.

Anthropic 은 임베딩 API를 제공하지 않으므로 OpenAI 호환 `/v1/embeddings`
엔드포인트를 HTTP로 직접 호출한다(SDK 의존성 추가 없이). 키가 없거나 호출이
실패하면 **결정론적 해싱 임베딩**으로 fallback해 키 없이도 F5가 동작한다.

두 방식의 벡터는 서로 다른 공간이라 비교하면 안 되므로, 항상 어떤 모델로
만든 벡터인지(`model_name`)를 함께 반환해 검색 시 같은 공간만 비교한다.
"""

import hashlib
import math
import re

from app.core.config import settings
from app.models.case import EMBEDDING_DIM

FALLBACK_MODEL = "hash-embed-v1"

_WORD_RE = re.compile(r"[0-9a-z가-힣]+")

try:
    import httpx
except ImportError:  # 의존성 미설치 환경 방어
    httpx = None  # type: ignore


def embed(text: str) -> tuple[list[float], str]:
    """returns (vector, model_name)"""
    if httpx is not None and settings.embedding_api_key:
        try:
            return _embed_remote(text), settings.embedding_model
        except Exception:
            # 네트워크·응답 형식 실패 시에도 F5가 멈추지 않도록 fallback
            pass
    return _embed_hashed(text), FALLBACK_MODEL


def _embed_remote(text: str) -> list[float]:
    resp = httpx.post(
        settings.embedding_api_url,
        headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
        json={"model": settings.embedding_model, "input": text, "dimensions": EMBEDDING_DIM},
        timeout=20.0,
    )
    resp.raise_for_status()
    vector = resp.json()["data"][0]["embedding"]
    if len(vector) != EMBEDDING_DIM:
        raise ValueError(f"임베딩 차원 불일치: {len(vector)} != {EMBEDDING_DIM}")
    return [float(v) for v in vector]


def _embed_hashed(text: str) -> list[float]:
    """문자 n-gram 해싱(signed hashing trick) 기반 어휘 유사도 벡터.

    한국어는 형태소 분석기 없이도 문자 2~3-gram 이 어느 정도 어휘 겹침을
    잡아내므로, 데모·오프라인 환경에서 쓸 만한 근사치가 된다.
    """
    vec = [0.0] * EMBEDDING_DIM
    for token in _tokens(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
        vec[index] += 1.0 if digest[4] & 1 else -1.0

    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        # 영벡터는 코사인 거리가 정의되지 않으므로 고정 단위벡터로 대체
        vec[0] = 1.0
        return vec
    return [v / norm for v in vec]


def _tokens(text: str) -> list[str]:
    words = _WORD_RE.findall(text.lower())
    tokens = list(words)
    for word in words:
        for size in (2, 3):
            tokens.extend(word[i : i + size] for i in range(len(word) - size + 1))
    return tokens
