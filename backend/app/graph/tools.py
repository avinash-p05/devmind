from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.service import search_persisted_documents
from app.schemas import SearchResult


async def hybrid_retrieval_tool(
    session: AsyncSession, query: str, top_k: int
) -> list[SearchResult]:
    return await search_persisted_documents(session, query, top_k, "hybrid")


async def code_search_tool(
    session: AsyncSession, query: str, top_k: int
) -> list[SearchResult]:
    results = await search_persisted_documents(session, query, top_k * 3, "keyword")
    code_results = [
        result
        for result in results
        if result.metadata.get("source_type") == "repository"
        or any(
            str(result.metadata.get("path", "")).endswith(extension)
            for extension in (".py", ".ts", ".tsx", ".js", ".java", ".go", ".sql")
        )
    ]
    return code_results[:top_k]