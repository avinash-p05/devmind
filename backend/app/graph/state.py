from typing import TypedDict

from app.schemas import Citation, SearchResult


class AgentState(TypedDict, total=False):
    query: str
    top_k: int
    route: str
    evidence: list[SearchResult]
    retrieval_attempts: int
    answer: str
    citations: list[Citation]
    evidence_sufficient: bool