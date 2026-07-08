from dataclasses import asdict
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.contracts import SourceMetadata
from app.embeddings import embed_text
from app.ingestion.text import chunk_text
from app.persistence.models import ChunkRecord, DocumentRecord
from app.schemas import Document, DocumentCreate, SearchResult


def _chunk_uuid(chunk_id: str) -> UUID:
    return UUID(chunk_id[:32])


async def create_persisted_document(session: AsyncSession, payload: DocumentCreate) -> Document:
    metadata = SourceMetadata(
        source_type=payload.source_type.value,
        source_name=payload.name,
        uri=payload.uri,
        path=payload.metadata.get("path"),
        service=payload.metadata.get("service"),
        extra=payload.metadata,
    )
    chunks = chunk_text(payload.content, metadata)
    document = DocumentRecord(
        source_type=payload.source_type.value,
        name=payload.name,
        uri=payload.uri,
        metadata_json=payload.metadata,
        content_hash=sha256(payload.content.encode("utf-8")).hexdigest(),
        chunks=[
            ChunkRecord(
                id=_chunk_uuid(chunk.id),
                content=chunk.content,
                ordinal=chunk.ordinal,
                metadata_json=asdict(chunk.metadata),
                embedding=embed_text(chunk.content),
            )
            for chunk in chunks
        ],
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return _to_document(document, content_length=len(payload.content))


async def list_persisted_documents(session: AsyncSession) -> list[Document]:
    result = await session.execute(
    select(DocumentRecord)
    .options(selectinload(DocumentRecord.chunks))
    .order_by(DocumentRecord.created_at.desc())
    )
    return [_to_document(document) for document in result.scalars()]


async def search_persisted_documents(
    session: AsyncSession, query: str, top_k: int
) -> list[SearchResult]:
    query_embedding = embed_text(query)
    distance = ChunkRecord.embedding.cosine_distance(query_embedding).label("distance")
    statement = (
        select(ChunkRecord, DocumentRecord, distance)
        .join(DocumentRecord, ChunkRecord.document_id == DocumentRecord.id)
        .where(ChunkRecord.embedding.is_not(None))
        .order_by(distance)
        .limit(top_k)
    )
    result = await session.execute(statement)
    return [
        SearchResult(
            chunk_id=chunk.id,
            document_id=document.id,
            document_name=document.name,
            content=chunk.content,
            score=1 - float(distance_value),
            rank=rank,
            metadata=chunk.metadata_json,
        )
        for rank, (chunk, document, distance_value) in enumerate(result.all(), start=1)
    ]


def _to_document(document: DocumentRecord, content_length: int | None = None) -> Document:
    if content_length is None:
        content_length = sum(len(chunk.content) for chunk in document.chunks)
    return Document(
        id=document.id,
        name=document.name,
        source_type=document.source_type,
        uri=document.uri,
        metadata=document.metadata_json,
        content_length=content_length,
        created_at=document.created_at,
    )