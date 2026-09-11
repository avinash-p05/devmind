from contextlib import asynccontextmanager
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.evaluation import get_evaluation, run_evaluation
from app.graph.workflow import analyze_incident, answer_question
from app.ingestion.bulk import index_repository
from app.ingestion.queue import enqueue_ingestion, get_ingestion_job
from app.persistence.database import get_session, initialize_database
from app.persistence.service import (
    create_persisted_document,
    get_conversation,
    list_persisted_documents,
    save_chat_interaction,
    save_incident_analysis,
    search_persisted_documents,
)
from app.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    Document,
    DocumentCreate,
    DocumentListResponse,
    EvaluationRunRequest,
    EvaluationRunResponse,
    HealthResponse,
    IncidentAnalysis,
    IncidentAnalyzeRequest,
    IngestionJobResponse,
    RepositoryIndexRequest,
    RepositoryIndexResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
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


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


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


@app.post(
    "/ingestions",
    response_model=IngestionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["ingestion"],
)
async def enqueue_document(payload: DocumentCreate) -> IngestionJobResponse:
    if not settings.persistence_enabled:
        raise HTTPException(status_code=503, detail="Persistence is required for queued ingestion")
    return await enqueue_ingestion(payload)


@app.get("/ingestions/{job_id}", response_model=IngestionJobResponse, tags=["ingestion"])
async def read_ingestion(job_id: UUID) -> IngestionJobResponse:
    job = await get_ingestion_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return job


@app.post(
    "/repositories/index",
    response_model=RepositoryIndexResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["ingestion"],
)
async def index_repository_route(
    payload: RepositoryIndexRequest, session: AsyncSession = Depends(get_session)
) -> RepositoryIndexResponse:
    if not settings.persistence_enabled:
        raise HTTPException(
            status_code=503, detail="Persistence is required for repository indexing"
        )
    stats = await index_repository(session, payload.path, batch_size=payload.batch_size)
    return RepositoryIndexResponse(path=payload.path, **stats.__dict__)


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
        return SearchResponse(query=payload.query, mode=payload.mode, results=[])
    results = await search_persisted_documents(session, payload.query, payload.top_k, payload.mode)
    return SearchResponse(query=payload.query, mode=payload.mode, results=results)


@app.post("/chat", response_model=ChatResponse, tags=["agent"])
async def chat(
    request: Request, payload: ChatRequest, session: AsyncSession = Depends(get_session)
) -> ChatResponse:
    if not settings.persistence_enabled:
        return ChatResponse(
            query=payload.query,
            answer="Persistence is disabled; start the Docker stack to use the agent.",
            route="unavailable",
            confidence="low",
            evidence_sufficient=False,
            citations=[],
            request_id=request.state.request_id,
        )
    started = perf_counter()
    response = await answer_question(session, payload.query, payload.top_k)
    conversation = await save_chat_interaction(
        session,
        conversation_id=payload.conversation_id,
        query=payload.query,
        response=response.answer,
        latency_ms=round((perf_counter() - started) * 1000, 2),
        estimated_tokens=response.estimated_tokens or max(1, len(response.answer) // 4),
        observability={
            "request_id": request.state.request_id,
            "route": response.route,
            "llm_provider": response.llm_provider,
            "llm_model": response.llm_model,
            "retrieval_latency_ms": response.retrieval_latency_ms,
            "retry_count": response.retry_count,
            "citation_validation_passed": response.citation_validation_passed,
        },
        evidence=[
            SearchResult(
                chunk_id=citation.chunk_id,
                document_id=citation.chunk_id,
                document_name=citation.document_name,
                content="",
                score=citation.score,
                rank=index,
                retrieval_method="citation",
                metadata=citation.metadata,
            )
            for index, citation in enumerate(response.citations, start=1)
        ],
    )
    response.conversation_id = conversation.id
    response.message_id = conversation.messages[-1].id
    response.estimated_tokens = conversation.messages[-1].estimated_tokens
    response.request_id = request.state.request_id
    return response


@app.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    tags=["conversations"],
)
async def read_conversation(
    conversation_id: UUID, session: AsyncSession = Depends(get_session)
) -> ConversationResponse:
    conversation = await get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/incidents/analyze", response_model=IncidentAnalysis, tags=["incidents"])
async def analyze_incident_route(
    payload: IncidentAnalyzeRequest, session: AsyncSession = Depends(get_session)
) -> IncidentAnalysis:
    if not settings.persistence_enabled:
        return IncidentAnalysis(
            service=payload.service,
            severity=payload.severity,
            root_cause_hypothesis=(
                "Persistence is disabled; start the Docker stack to analyze incidents."
            ),
            evidence=[],
            affected_component=payload.service,
            recommended_next_steps=[],
            confidence="low",
            route="unavailable",
            unresolved_questions=["Start the persistent application environment."],
            timeline=[],
            contributing_factors=[],
        )
    analysis = await analyze_incident(session, payload)
    return await save_incident_analysis(session, analysis)


@app.post("/evaluations/run", response_model=EvaluationRunResponse, tags=["evaluations"])
async def start_evaluation(
    payload: EvaluationRunRequest, session: AsyncSession = Depends(get_session)
) -> EvaluationRunResponse:
    if not settings.persistence_enabled:
        raise HTTPException(status_code=503, detail="Persistence is required for evaluations")
    return await run_evaluation(session, payload)


@app.get("/evaluations/{run_id}", response_model=EvaluationRunResponse, tags=["evaluations"])
async def read_evaluation(
    run_id: UUID, session: AsyncSession = Depends(get_session)
) -> EvaluationRunResponse:
    evaluation = await get_evaluation(session, run_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return evaluation
