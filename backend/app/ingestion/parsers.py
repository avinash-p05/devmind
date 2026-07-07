from dataclasses import dataclass

from app.domain.contracts import SourceMetadata
from app.ingestion.text import normalize_text


@dataclass(frozen=True)
class ParsedSource:
    content: str
    metadata: SourceMetadata


def parse_text_source(content: str, metadata: SourceMetadata) -> ParsedSource:
    normalized = normalize_text(content)
    if not normalized:
        raise ValueError("source content is empty after normalization")
    return ParsedSource(content=normalized, metadata=metadata)
