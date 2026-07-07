from datetime import UTC, datetime
from uuid import UUID

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.schemas import Document, DocumentCreate, DocumentListResponse, HealthResponse

settings = get_settings()
app = FastAPI(
    title="DevMind API", version="0.1.0", description="Grounded incident intelligence API"
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
def create_document(payload: DocumentCreate) -> Document:
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
def list_documents() -> DocumentListResponse:
    items = list(_documents.values())
    return DocumentListResponse(items=items, total=len(items))
