import hashlib
import re

from app.domain.contracts import SourceMetadata, TextChunk


def normalize_text(content: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in content.splitlines()]
    normalized_lines = []
    previous_blank = False
    for line in lines:
        if not line:
            if not previous_blank:
                normalized_lines.append("")
            previous_blank = True
            continue
        normalized_lines.append(line)
        previous_blank = False
    return "\n".join(normalized_lines).strip()


def chunk_text(
    content: str,
    metadata: SourceMetadata,
    *,
    chunk_size: int = 1200,
    overlap: int = 150,
) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    normalized = normalize_text(content)
    if not normalized:
        return []

    step = chunk_size - overlap
    chunks: list[TextChunk] = []
    for ordinal, start in enumerate(range(0, len(normalized), step)):
        chunk_content = normalized[start : start + chunk_size]
        if not chunk_content:
            break
        stable_key = f"{metadata.source_name}:{ordinal}:{chunk_content}".encode()
        chunk_id = hashlib.sha256(stable_key).hexdigest()
        chunks.append(
            TextChunk(id=chunk_id, content=chunk_content, ordinal=ordinal, metadata=metadata)
        )
        if start + chunk_size >= len(normalized):
            break
    return chunks
