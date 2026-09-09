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
    llm_metadata: dict
    estimated_tokens: int
    generation_attempts: int
    citation_validation_passed: bool