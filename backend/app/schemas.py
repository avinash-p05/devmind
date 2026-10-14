from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

SourceType = Literal["document", "code", "config", "log", "incident", "repository"]


class HealthResponse(BaseModel):
    status: str
    environment: str
    providers: dict[str, str]


class ServiceCount(BaseModel):
    name: str
    documents: int


class StatsResponse(BaseModel):
    documents: int
    chunks: int
    characters: int
    last_indexed_at: datetime | None
    by_source_type: dict[str, int]
    services: list[ServiceCount]
    ingestion: dict
    providers: dict[str, str]
    min_score: float
    benchmark: dict | None


class DocumentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="File name or relative path")
    content: str = Field(min_length=1)
    source_type: SourceType | None = Field(default=None, description="Inferred from the path")


class DocumentOut(BaseModel):
    id: UUID
    name: str
    path: str
    source_type: str
    content_length: int
    metadata: dict
    created_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentOut]
    total: int


class RepositoryIndexRequest(BaseModel):
    path: str = Field(min_length=1, description="Directory on the API server to index")
    batch_size: int = Field(default=64, ge=1, le=500)


class RepositoryIndexResponse(BaseModel):
    path: str
    discovered: int
    indexed: int
    skipped_duplicates: int
    failed: int
    chunks: int
    duration_ms: float
    errors: list[str]


class IngestionJob(BaseModel):
    id: UUID
    status: str  # queued | processing | retrying | completed | failed
    attempts: int = 0
    document_id: UUID | None = None
    error: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: Literal["hybrid", "vector", "keyword", "semantic"] = "hybrid"

    @field_validator("mode")
    @classmethod
    def _semantic_is_vector(cls, mode: str) -> str:
        return "vector" if mode == "semantic" else mode


class SearchResult(BaseModel):
    chunk_id: UUID
    document_name: str
    path: str
    content: str
    score: float
    similarity: float | None
    rank: int
    retrieval_method: str
    metadata: dict


class SearchResponse(BaseModel):
    query: str
    mode: str
    top_similarity: float
    results: list[SearchResult]


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)


class Citation(BaseModel):
    number: int
    chunk_id: UUID
    document_name: str
    path: str
    score: float
    metadata: dict


class ChatResponse(BaseModel):
    query: str
    answer: str
    route: str
    tools_used: list[str]
    refused: bool
    confidence: Literal["high", "low"]
    evidence_sufficient: bool
    citations: list[Citation]
    citation_validation_passed: bool
    top_similarity: float
    llm_model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float


class IncidentAnalyzeRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    service: str = Field(min_length=1, max_length=120)
    severity: str = Field(default="unknown", max_length=32)
    top_k: int = Field(default=5, ge=1, le=10)


class IncidentAnalysis(BaseModel):
    service: str
    severity: str
    root_cause_hypothesis: str
    affected_component: str
    recommended_next_steps: list[str]
    unresolved_questions: list[str]
    evidence: list[Citation]  # sources the analysis cited
    retrieved: list[Citation]  # everything the agent retrieved and showed the model
    confidence: Literal["high", "low"]
    route: str
    total_tokens: int


class EvaluationRunRequest(BaseModel):
    dataset_version: str = "v1"
    mode: Literal["hybrid", "vector", "keyword"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=20)
    retrieval_only: bool = Field(default=False, description="Skip the LLM; measure retrieval")


class EvaluationRunResponse(BaseModel):
    id: UUID
    dataset_version: str
    mode: str
    summary: dict
    results: list[dict]
    created_at: datetime
