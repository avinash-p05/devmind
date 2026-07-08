import hashlib
import math

EMBEDDING_DIMENSION = 1536


def embed_text(text: str) -> list[float]:
    """Create a deterministic local embedding for development and repeatable tests."""
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