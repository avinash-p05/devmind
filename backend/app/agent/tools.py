"""Retrieval tools the agent can call. Each is the hybrid retriever scoped to a source type."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.hybrid import Retrieval, search


async def search_knowledge_base(session: AsyncSession, query: str, top_k: int) -> Retrieval:
    """Everything that was indexed."""
    return await search(session, query, top_k)


async def search_code(session: AsyncSession, query: str, top_k: int) -> Retrieval:
    """Source files and configuration only: 'where is X implemented / configured?'."""
    return await search(session, query, top_k, source_types={"code", "config"})


async def search_logs(session: AsyncSession, query: str, top_k: int) -> Retrieval:
    return await search(session, query, top_k, source_types={"log"})


async def search_incidents(session: AsyncSession, query: str, top_k: int) -> Retrieval:
    """Incident reports and postmortems."""
    return await search(session, query, top_k, source_types={"incident"})


TOOLS = {
    "search_knowledge_base": search_knowledge_base,
    "search_code": search_code,
    "search_logs": search_logs,
    "search_incidents": search_incidents,
}

# Which tools each route calls. The general search (last) provides the ranking; the
# specialised tool (first) guarantees its source type is represented - see
# graph.merge_with_coverage.
ROUTE_TOOLS = {
    "code": ["search_code", "search_knowledge_base"],
    "logs": ["search_logs", "search_knowledge_base"],
    "incident": ["search_incidents", "search_knowledge_base"],
    "docs": ["search_knowledge_base"],
}
