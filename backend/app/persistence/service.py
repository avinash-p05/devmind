from dataclasses import asdict
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.contracts import SourceMetadata
from app.embeddings import embed_text
from app.ingestion.text import chunk_text
from app.persistence.models import ChunkRecord, DocumentRecord
from app.retrieval.reranker import combine_scores
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
    session: AsyncSession, query: str, top_k: int, mode: str = "hybrid"
) -> list[SearchResult]:
    candidates: dict[UUID, dict] = {}
    if mode in {"semantic", "hybrid"}:
        query_embedding = embed_text(query)
        distance = ChunkRecord.embedding.cosine_distance(query_embedding).label("distance")
        semantic_statement = (
            select(ChunkRecord, DocumentRecord, distance)
            .join(DocumentRecord, ChunkRecord.document_id == DocumentRecord.id)
            .where(ChunkRecord.embedding.is_not(None))
            .order_by(distance)
            .limit(top_k * 3)
        )
        semantic_result = await session.execute(semantic_statement)
        for chunk, document, distance_value in semantic_result.all():
            candidates[chunk.id] = {
                "chunk": chunk,
                "document": document,
                "semantic_score": max(0.0, 1 - float(distance_value)),
                "keyword_score": None,
            }

    if mode in {"keyword", "hybrid"}:
        document_vector = func.to_tsvector("simple", ChunkRecord.content)
        query_vector = func.websearch_to_tsquery("simple", query)
        keyword_score = func.ts_rank_cd(document_vector, query_vector).label("keyword_score")
        keyword_statement = (
            select(ChunkRecord, DocumentRecord, keyword_score)
            .join(DocumentRecord, ChunkRecord.document_id == DocumentRecord.id)
            .where(document_vector.op("@@")(query_vector))
            .order_by(keyword_score.desc())
            .limit(top_k * 3)
        )
        keyword_result = await session.execute(keyword_statement)
        for chunk, document, score in keyword_result.all():
            candidate = candidates.setdefault(
                chunk.id,
                {
                    "chunk": chunk,
                    "document": document,
                    "semantic_score": None,
                    "keyword_score": None,
                },
            )
            candidate["keyword_score"] = min(1.0, float(score))

    ranked = sorted(
        candidates.values(),
        key=lambda candidate: combine_scores(
            candidate["semantic_score"], candidate["keyword_score"]
        ),
        reverse=True,
    )[:top_k]
    return [
        SearchResult(
            chunk_id=candidate["chunk"].id,
            document_id=candidate["document"].id,
            document_name=candidate["document"].name,
            content=candidate["chunk"].content,
            score=combine_scores(candidate["semantic_score"], candidate["keyword_score"]),
            rank=rank,
            retrieval_method=(
                "hybrid"
                if candidate["semantic_score"] is not None
                and candidate["keyword_score"] is not None
                else "semantic"
                if candidate["semantic_score"] is not None
                else "keyword"
            ),
            metadata=candidate["chunk"].metadata_json,
        )
        for rank, candidate in enumerate(ranked, start=1)
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