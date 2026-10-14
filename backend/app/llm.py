"""Model access: the only module that calls a chat model or an embedding model.

Ollama (local development) and the OpenAI API (production) speak the same API, so one
OpenAI SDK client covers both; only LLM_BASE_URL, LLM_API_KEY and LLM_MODEL change.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from openai import OpenAI

from app.config import get_settings

log = logging.getLogger("devmind.llm")


@dataclass(frozen=True)
class ChatResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


# Cached: the client owns an HTTP connection pool, so reusing it avoids a new TCP + TLS
# handshake on every request.
@lru_cache(maxsize=1)
def _client() -> OpenAI:
    settings = get_settings()
    return OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout_seconds,
    )


def _token_limit() -> dict[str, int]:
    # OpenAI uses max_completion_tokens (newer models reject max_tokens). Ollama's
    # OpenAI-compatible API silently ignores max_completion_tokens and honours max_tokens.
    settings = get_settings()
    key = "max_completion_tokens" if "api.openai.com" in settings.llm_base_url else "max_tokens"
    return {key: settings.max_completion_tokens}


def chat(messages: list[dict]) -> ChatResult:
    settings = get_settings()
    response = _client().chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=0,
        **_token_limit(),
    )
    choice = response.choices[0]
    if choice.finish_reason == "length":
        log.warning("Answer cut off at max_completion_tokens=%s", settings.max_completion_tokens)
    usage = response.usage
    return ChatResult(
        text=choice.message.content or "",
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        model=settings.llm_model,
    )


@lru_cache(maxsize=1)
def _local_embedding_model():
    from fastembed import TextEmbedding  # imported lazily: loading the model takes seconds

    return TextEmbedding(get_settings().local_embedding_model)


def embed(texts: list[str]) -> np.ndarray:
    """Return one unit-length vector per text, so cosine similarity is a dot product."""
    settings = get_settings()
    if settings.embedding_provider == "openai":
        response = _client().embeddings.create(
            model=settings.openai_embedding_model,
            input=texts,
            dimensions=settings.embedding_dimension,  # text-embedding-3-* can be shortened
        )
        vectors = np.array([item.embedding for item in response.data], dtype=np.float32)
    else:
        vectors = np.array(list(_local_embedding_model().embed(texts)), dtype=np.float32)
    if vectors.shape[1] != settings.embedding_dimension:
        raise RuntimeError(
            f"embedding model returned {vectors.shape[1]} dimensions, "
            f"EMBEDDING_DIMENSION is {settings.embedding_dimension}"
        )
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.clip(norms, 1e-12, None)


def provider_info() -> dict[str, str]:
    settings = get_settings()
    return {
        "llm_base_url": settings.llm_base_url,
        "llm_model": settings.llm_model,
        "embedding_provider": settings.embedding_provider,
    }
