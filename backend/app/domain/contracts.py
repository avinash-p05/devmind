from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class SourceMetadata:
    source_type: str
    source_name: str
    uri: str | None = None
    path: str | None = None
    page: int | None = None
    start_line: int | None = None
    end_line: int | None = None
    service: str | None = None
    commit_sha: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TextChunk:
    id: str
    content: str
    ordinal: int
    metadata: SourceMetadata


@dataclass(frozen=True)
class Evidence:
    chunk_id: UUID | str
    content: str
    score: float
    rank: int
    retrieval_method: str
    metadata: SourceMetadata
