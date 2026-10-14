"""parse -> chunk -> embed -> store. Shared by the API, the Redis worker and the CLI script."""

import asyncio
from dataclasses import dataclass, field
from hashlib import sha256
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import Chunk, Document
from app.ingestion.chunking import chunk_text
from app.ingestion.parsers import ParsedSource
from app.llm import embed


@dataclass
class IndexStats:
    discovered: int = 0
    indexed: int = 0
    skipped_duplicates: int = 0
    failed: int = 0
    chunks: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


async def index_sources(
    session: AsyncSession, sources: list[ParsedSource], batch_size: int = 64
) -> IndexStats:
    """Index sources in batches. One embedding call per batch, one commit per batch."""
    started = perf_counter()
    stats = IndexStats(discovered=len(sources))
    for offset in range(0, len(sources), batch_size):
        batch = await _drop_duplicates(session, sources[offset : offset + batch_size], stats)
        if not batch:
            continue
        try:
            # Chunking + embedding is synchronous CPU/network work; keep the event loop free.
            documents = await asyncio.to_thread(_build_documents, batch)
            session.add_all(documents)
            await session.commit()
        except Exception as error:  # one bad batch must not stop a 1,000-file ingestion
            await session.rollback()
            stats.failed += len(batch)
            stats.errors.append(f"batch at {offset}: {error}")
            continue
        stats.indexed += len(documents)
        stats.chunks += sum(len(document.chunks) for document in documents)
    stats.duration_ms = round((perf_counter() - started) * 1000, 1)
    return stats


async def index_source(session: AsyncSession, source: ParsedSource) -> Document | None:
    """Index one source; returns the stored document (the existing one for duplicates)."""
    stats = await index_sources(session, [source])
    if stats.errors:
        raise RuntimeError(stats.errors[0])
    return await session.scalar(
        select(Document).where(Document.content_hash == _hash(source.content))
    )


async def _drop_duplicates(
    session: AsyncSession, batch: list[ParsedSource], stats: IndexStats
) -> list[ParsedSource]:
    hashes = {_hash(source.content) for source in batch}
    query = select(Document.content_hash).where(Document.content_hash.in_(hashes))
    existing = set(await session.scalars(query))
    unique: dict[str, ParsedSource] = {}
    for source in batch:
        digest = _hash(source.content)
        if digest in existing or digest in unique or not source.content.strip():
            stats.skipped_duplicates += 1
        else:
            unique[digest] = source
    return list(unique.values())


def _build_documents(batch: list[ParsedSource]) -> list[Document]:
    settings = get_settings()
    chunked = [chunk_text(s.content, settings.chunk_size, settings.chunk_overlap) for s in batch]
    # Prefix each chunk with its path and title before embedding, so a chunk from the middle
    # of a file still "knows" which file and topic it belongs to.
    texts = [
        f"{source.path}\n{source.metadata.get('title', '')}\n{chunk}"
        for source, chunks in zip(batch, chunked, strict=True)
        for chunk in chunks
    ]
    vectors = iter(embed(texts)) if texts else iter(())
    documents = []
    for source, chunks in zip(batch, chunked, strict=True):
        documents.append(
            Document(
                name=source.name,
                source_type=source.source_type,
                path=source.path,
                content_hash=_hash(source.content),
                content_length=len(source.content),
                metadata_json=source.metadata,
                chunks=[
                    Chunk(
                        ordinal=ordinal,
                        content=chunk,
                        path=source.path,
                        source_type=source.source_type,
                        metadata_json=source.metadata,
                        embedding=next(vectors).tolist(),
                    )
                    for ordinal, chunk in enumerate(chunks)
                ],
            )
        )
    return documents


def _hash(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()
