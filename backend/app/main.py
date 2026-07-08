from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.persistence.database import get_session, initialize_database
from app.persistence.service import (
    create_persisted_document,
    list_persisted_documents,
    search_persisted_documents,
)
from app.schemas import (
    Document,
    DocumentCreate,
    DocumentListResponse,
    HealthResponse,
    SearchRequest,
    SearchResponse,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.persistence_enabled:
        await initialize_database()
    yield


app = FastAPI(
    title="DevMind API",
    version="0.1.0",
    description="Grounded incident intelligence API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_documents: dict[UUID, Document] = {}


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="devmind-api", environment=settings.app_env)


@app.post(
    "/documents", response_model=Document, status_code=status.HTTP_201_CREATED, tags=["documents"]
)
async def create_document(
    payload: DocumentCreate, session: AsyncSession = Depends(get_session)
) -> Document:
    if settings.persistence_enabled:
        return await create_persisted_document(session, payload)

    document = Document(
        name=payload.name,
        source_type=payload.source_type,
        uri=payload.uri,
        metadata=payload.metadata,
        content_length=len(payload.content),
        created_at=datetime.now(UTC),
    )
    _documents[document.id] = document
    return document


@app.get("/documents", response_model=DocumentListResponse, tags=["documents"])
async def list_documents(session: AsyncSession = Depends(get_session)) -> DocumentListResponse:
    if settings.persistence_enabled:
        items = await list_persisted_documents(session)
        return DocumentListResponse(items=items, total=len(items))

    items = list(_documents.values())
    return DocumentListResponse(items=items, total=len(items))


@app.post("/search", response_model=SearchResponse, tags=["retrieval"])
async def search(
    payload: SearchRequest, session: AsyncSession = Depends(get_session)
) -> SearchResponse:
    if not settings.persistence_enabled:
        return SearchResponse(query=payload.query, results=[])
    results = await search_persisted_documents(session, payload.query, payload.top_k)
    return SearchResponse(query=payload.query, results=results)
