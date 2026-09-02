import hashlib
import json
import math
from urllib.request import Request, urlopen

from app.config import get_settings

EMBEDDING_DIMENSION = 1536


def _local_embedding(text: str) -> list[float]:
    values = [0.0] * EMBEDDING_DIMENSION
    encoded = text.encode("utf-8")
    for offset in range(0, len(encoded), 4):
        digest = hashlib.sha256(encoded[offset : offset + 4]).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        values[index] += 1.0 if digest[4] % 2 else -1.0

    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude == 0:
        return values
    return [value / magnitude for value in values]


def _remote_embedding(text: str) -> list[float]:
    settings = get_settings()
    if not settings.embedding_api_key:
        raise RuntimeError(
            "EMBEDDING_API_KEY is required when EMBEDDING_PROVIDER is not 'local'"
        )
    request = Request(
        f"{settings.embedding_base_url.rstrip('/')}/embeddings",
        data=json.dumps({"model": settings.embedding_model, "input": text}).encode(),
        headers={
            "Authorization": f"Bearer {settings.embedding_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=settings.llm_timeout_seconds) as response:
        payload = json.load(response)
    vector = payload["data"][0]["embedding"]
    if len(vector) != settings.embedding_dimension:
        raise RuntimeError(
            f"Embedding provider returned {len(vector)} dimensions; "
            f"configured schema requires {settings.embedding_dimension}"
        )
    return vector


def embed_text(text: str) -> list[float]:
    """Return a configured embedding while keeping local development deterministic."""
    settings = get_settings()
    if settings.embedding_dimension != EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"EMBEDDING_DIMENSION={settings.embedding_dimension} is incompatible with "
            f"the current pgvector schema ({EMBEDDING_DIMENSION})"
        )
    if settings.embedding_provider.lower() == "local":
        return _local_embedding(text)
    return _remote_embedding(text)


def embedding_metadata() -> dict[str, str | int]:
    settings = get_settings()
    return {
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
        "dimension": settings.embedding_dimension,
    }
