"""Hybrid retrieval: pgvector cosine search + Postgres full-text search, fused and reranked."""

import asyncio
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Text, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Chunk
from app.llm import embed
from app.retrieval.reranker import reciprocal_rank_fusion, rerank

CANDIDATES_PER_RETRIEVER = 20


@dataclass(frozen=True)
class Hit:
    chunk_id: UUID
    path: str
    source_type: str
    content: str
    metadata: dict
    score: float  # final ranking score for the mode used
    similarity: float | None  # cosine similarity to the query, when the vector leg found it
    method: str  # vector | keyword | hybrid


@dataclass(frozen=True)
class Retrieval:
    hits: list[Hit]
    # Best cosine similarity among vector candidates. The answer guardrail uses it to decide
    # whether retrieval found anything relevant enough to be worth an LLM call.
    top_similarity: float


async def vector_search(
    session: AsyncSession, query_vector: list[float], limit: int, source_types: set[str] | None
) -> list[tuple[Chunk, float]]:
    distance = Chunk.embedding.cosine_distance(query_vector)
    statement = select(Chunk, (1 - distance).label("similarity")).order_by(distance).limit(limit)
    if source_types:
        statement = statement.where(Chunk.source_type.in_(source_types))
    return [(chunk, float(similarity)) for chunk, similarity in await session.execute(statement)]


async def keyword_search(
    session: AsyncSession, query: str, limit: int, source_types: set[str] | None
) -> list[tuple[Chunk, float]]:
    # plainto_tsquery ANDs every term, so a full question ("where is retry backoff
    # configured?") would only match chunks containing all of them. OR the stemmed,
    # stopword-free terms instead; ts_rank_cd still ranks chunks matching more terms higher.
    ts_query = func.to_tsquery(
        "english", func.replace(cast(func.plainto_tsquery("english", query), Text), "&", "|")
    )
    rank = func.ts_rank_cd(Chunk.search_vector, ts_query)
    statement = (
        select(Chunk, rank.label("rank"))
        .where(Chunk.search_vector.op("@@")(ts_query))
        .order_by(rank.desc())
        .limit(limit)
    )
    if source_types:
        statement = statement.where(Chunk.source_type.in_(source_types))
    return [(chunk, float(score)) for chunk, score in await session.execute(statement)]


async def search(
    session: AsyncSession,
    query: str,
    top_k: int = 5,
    mode: str = "hybrid",
    source_types: set[str] | None = None,
) -> Retrieval:
    """mode: vector | keyword | hybrid. `source_types` restricts the search (e.g. code only)."""
    vector_hits: list[tuple[Chunk, float]] = []
    keyword_hits: list[tuple[Chunk, float]] = []
    if mode in {"vector", "hybrid"}:
        # Embedding is CPU/network bound and synchronous; keep it off the event loop.
        query_vector = (await asyncio.to_thread(embed, [query]))[0].tolist()
        vector_hits = await vector_search(
            session, query_vector, CANDIDATES_PER_RETRIEVER, source_types
        )
    if mode in {"keyword", "hybrid"}:
        keyword_hits = await keyword_search(session, query, CANDIDATES_PER_RETRIEVER, source_types)

    chunks = {chunk.id: chunk for chunk, _ in vector_hits + keyword_hits}
    similarity = {chunk.id: score for chunk, score in vector_hits}
    in_keyword = {chunk.id for chunk, _ in keyword_hits}
    top_similarity = max(similarity.values(), default=0.0)

    if mode == "vector":
        ranked = [(chunk.id, score) for chunk, score in vector_hits]
    elif mode == "keyword":
        ranked = [(chunk.id, score) for chunk, score in keyword_hits]
    else:
        fused = reciprocal_rank_fusion(
            [[chunk.id for chunk, _ in vector_hits], [chunk.id for chunk, _ in keyword_hits]]
        )
        ranked = rerank(
            query,
            [
                (chunk_id, f"{chunks[chunk_id].path} {chunks[chunk_id].content}", score)
                for chunk_id, score in fused.items()
            ],
        )

    hits = [
        Hit(
            chunk_id=chunk_id,
            path=chunks[chunk_id].path,
            source_type=chunks[chunk_id].source_type,
            content=chunks[chunk_id].content,
            metadata=chunks[chunk_id].metadata_json,
            score=round(score, 4),
            similarity=round(similarity[chunk_id], 4) if chunk_id in similarity else None,
            method=(
                "hybrid"
                if chunk_id in similarity and chunk_id in in_keyword
                else "vector"
                if chunk_id in similarity
                else "keyword"
            ),
        )
        for chunk_id, score in ranked[:top_k]
    ]
    return Retrieval(hits=hits, top_similarity=round(top_similarity, 4))
