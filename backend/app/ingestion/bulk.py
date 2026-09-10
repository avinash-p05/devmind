from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.parsers import ParsedSource, parse_repository_snapshot
from app.persistence.models import DocumentRecord
from app.persistence.service import create_persisted_document
from app.schemas import DocumentCreate, SourceType


@dataclass
class BulkIndexStats:
    discovered: int = 0
    indexed: int = 0
    skipped_duplicates: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def build_repository_payloads(root: str | Path) -> list[DocumentCreate]:
    return [_payload_from_source(source) for source in parse_repository_snapshot(root)]


async def index_repository(
    session: AsyncSession,
    root: str | Path,
    *,
    batch_size: int = 100,
    metrics: dict[str, float] | None = None,
) -> BulkIndexStats:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    payloads = build_repository_payloads(root)
    stats = BulkIndexStats(discovered=len(payloads))
    for offset in range(0, len(payloads), batch_size):
        for payload in payloads[offset : offset + batch_size]:
            content_hash = _content_hash(payload.content)
            existing = await session.scalar(
                select(DocumentRecord.id).where(DocumentRecord.content_hash == content_hash)
            )
            if existing is not None:
                stats.skipped_duplicates += 1
                continue
            try:
                await create_persisted_document(session, payload, metrics)
            except Exception as error:
                await session.rollback()
                stats.failed += 1
                stats.errors.append(f"{payload.name}: {error}")
            else:
                stats.indexed += 1
    return stats


def _payload_from_source(source: ParsedSource) -> DocumentCreate:
    metadata = {
        "path": source.metadata.path or source.metadata.source_name,
        "format": source.metadata.extra.get("format", "text"),
    }
    if source.metadata.commit_sha:
        metadata["commit_sha"] = source.metadata.commit_sha
    if source.metadata.service:
        metadata["service"] = source.metadata.service
    return DocumentCreate(
        name=source.metadata.source_name,
        source_type=SourceType.repository,
        uri=source.metadata.uri,
        content=source.content,
        metadata=metadata,
    )


def _content_hash(content: str) -> str:
    from hashlib import sha256

    return sha256(content.encode("utf-8")).hexdigest()
