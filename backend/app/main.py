import logging
from contextlib import asynccontextmanager
from uuid import UUID

import openai
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.service import analyze_incident, ask
from app.config import get_settings
from app.db import Document, EvaluationRun, get_session, init_db
from app.evaluation.runner import evaluate, load_dataset
from app.ingestion import queue
from app.ingestion.parsers import parse_directory, parse_text
from app.ingestion.pipeline import index_source, index_sources
from app.llm import provider_info
from app.retrieval.hybrid import search
from app.schemas import (
    ChatRequest,
    ChatResponse,
    DocumentCreate,
    DocumentList,
    DocumentOut,
    EvaluationRunRequest,
    EvaluationRunResponse,
    HealthResponse,
    IncidentAnalysis,
    IncidentAnalyzeRequest,
    IngestionJob,
    RepositoryIndexRequest,
    RepositoryIndexResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    StatsResponse,
)
from app.stats import workspace_stats

settings = get_settings()
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.redis = queue.redis_client()
    yield
    await app.state.redis.aclose()


app = FastAPI(title="DevMind API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(openai.APIError)
async def llm_unavailable(request: Request, error: openai.APIError) -> JSONResponse:
    # The SDK has already retried (max_retries=2). Tell the caller it's the model, not us.
    logging.getLogger("devmind.api").error("LLM provider error: %s", error)
    return JSONResponse(status_code=503, content={"detail": "LLM provider unavailable"})


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", environment=settings.app_env, providers=provider_info())


@app.get("/stats", response_model=StatsResponse, tags=["system"])
async def stats(session: AsyncSession = Depends(get_session)) -> StatsResponse:
    """What is indexed, ingestion queue state, configured models, and the latest benchmark."""
    return StatsResponse(**await workspace_stats(session, app.state.redis))


# ---------- ingestion ----------


@app.post("/documents", response_model=DocumentOut, status_code=201, tags=["ingestion"])
async def create_document(
    payload: DocumentCreate, session: AsyncSession = Depends(get_session)
) -> DocumentOut:
    """Synchronous ingestion of a single document."""
    document = await index_source(
        session, parse_text(payload.name, payload.content, payload.source_type)
    )
    return _document_out(document)


@app.get("/documents", response_model=DocumentList, tags=["ingestion"])
async def list_documents(
    limit: int = Query(default=100, ge=1, le=5000), session: AsyncSession = Depends(get_session)
) -> DocumentList:
    total = await session.scalar(select(func.count()).select_from(Document))
    documents = await session.scalars(
        select(Document).order_by(Document.created_at.desc()).limit(limit)
    )
    return DocumentList(items=[_document_out(d) for d in documents], total=total or 0)


@app.post("/ingestions", response_model=IngestionJob, status_code=202, tags=["ingestion"])
async def enqueue_document(payload: DocumentCreate) -> IngestionJob:
    """Async ingestion: queued in Redis and indexed by the worker."""
    return await queue.enqueue(app.state.redis, payload)


@app.get("/ingestions/{job_id}", response_model=IngestionJob, tags=["ingestion"])
async def ingestion_status(job_id: UUID) -> IngestionJob:
    job = await queue.get_job(app.state.redis, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="ingestion job not found")
    return job


@app.post("/repositories/index", response_model=RepositoryIndexResponse, tags=["ingestion"])
async def index_repository(
    payload: RepositoryIndexRequest, session: AsyncSession = Depends(get_session)
) -> RepositoryIndexResponse:
    try:
        sources = parse_directory(payload.path)
    except FileNotFoundError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    stats = await index_sources(session, sources, payload.batch_size)
    return RepositoryIndexResponse(path=payload.path, **vars(stats))


# ---------- retrieval and agent ----------


@app.post("/search", response_model=SearchResponse, tags=["retrieval"])
async def search_chunks(
    payload: SearchRequest, session: AsyncSession = Depends(get_session)
) -> SearchResponse:
    retrieval = await search(session, payload.query, payload.top_k, payload.mode)
    return SearchResponse(
        query=payload.query,
        mode=payload.mode,
        top_similarity=retrieval.top_similarity,
        results=[
            SearchResult(
                chunk_id=hit.chunk_id,
                document_name=hit.path.rsplit("/", 1)[-1],
                path=hit.path,
                content=hit.content,
                score=hit.score,
                similarity=hit.similarity,
                rank=rank,
                retrieval_method=hit.method,
                metadata=hit.metadata,
            )
            for rank, hit in enumerate(retrieval.hits, start=1)
        ],
    )


@app.post("/chat", response_model=ChatResponse, tags=["agent"])
async def chat(payload: ChatRequest, session: AsyncSession = Depends(get_session)) -> ChatResponse:
    return await ask(session, payload.query, payload.top_k)


@app.post("/incidents/analyze", response_model=IncidentAnalysis, tags=["agent"])
async def incident(
    payload: IncidentAnalyzeRequest, session: AsyncSession = Depends(get_session)
) -> IncidentAnalysis:
    return await analyze_incident(
        session, payload.query, payload.service, payload.severity, payload.top_k
    )


# ---------- evaluation ----------


@app.post("/evaluations/run", response_model=EvaluationRunResponse, tags=["evaluation"])
async def run_evaluation(
    payload: EvaluationRunRequest, session: AsyncSession = Depends(get_session)
) -> EvaluationRunResponse:
    try:
        cases = load_dataset(payload.dataset_version)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    summary, results = await evaluate(
        session,
        cases,
        mode=payload.mode,
        top_k=payload.top_k,
        retrieval_only=payload.retrieval_only,
    )
    run = EvaluationRun(
        dataset=payload.dataset_version,
        mode="retrieval:" + payload.mode if payload.retrieval_only else "agent",
        summary=summary,
        results=results,
    )
    session.add(run)
    await session.commit()
    return _evaluation_out(run)


@app.get("/evaluations/{run_id}", response_model=EvaluationRunResponse, tags=["evaluation"])
async def get_evaluation(
    run_id: UUID, session: AsyncSession = Depends(get_session)
) -> EvaluationRunResponse:
    run = await session.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="evaluation run not found")
    return _evaluation_out(run)


def _document_out(document: Document) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        name=document.name,
        path=document.path,
        source_type=document.source_type,
        content_length=document.content_length,
        metadata=document.metadata_json,
        created_at=document.created_at,
    )


def _evaluation_out(run: EvaluationRun) -> EvaluationRunResponse:
    return EvaluationRunResponse(
        id=run.id,
        dataset_version=run.dataset,
        mode=run.mode,
        summary=run.summary,
        results=run.results,
        created_at=run.created_at,
    )
