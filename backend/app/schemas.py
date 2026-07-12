from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    document = "document"
    repository = "repository"
    log = "log"
    incident = "incident"


class DocumentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_type: SourceType = SourceType.document
    uri: str | None = None
    content: str = Field(min_length=1)
    metadata: dict[str, str] = Field(default_factory=dict)


class Document(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    source_type: SourceType
    uri: str | None = None
    metadata: dict[str, str]
    content_length: int
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class DocumentListResponse(BaseModel):
    items: list[Document]
    total: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: str = Field(default="hybrid", pattern="^(semantic|keyword|hybrid)$")


class SearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str
    content: str
    score: float
    rank: int
    retrieval_method: str
    metadata: dict


class SearchResponse(BaseModel):
    query: str
    mode: str
    results: list[SearchResult]
