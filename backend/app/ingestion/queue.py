import json
from uuid import UUID, uuid4

from redis.asyncio import Redis

from app.config import get_settings
from app.schemas import DocumentCreate, IngestionJobResponse

QUEUE_NAME = "devmind:ingestion"


def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


async def enqueue_ingestion(payload: DocumentCreate) -> IngestionJobResponse:
    job_id = uuid4()
    job = {"id": str(job_id), "status": "queued", "payload": payload.model_dump(mode="json")}
    redis = get_redis()
    try:
        await redis.set(f"devmind:job:{job_id}", json.dumps(job))
        await redis.rpush(QUEUE_NAME, str(job_id))
    finally:
        await redis.aclose()
    return IngestionJobResponse(id=job_id, status="queued")


async def get_ingestion_job(job_id: UUID) -> IngestionJobResponse | None:
    redis = get_redis()
    try:
        raw = await redis.get(f"devmind:job:{job_id}")
    finally:
        await redis.aclose()
    if raw is None:
        return None
    job = json.loads(raw)
    return IngestionJobResponse(
        id=job_id,
        status=job["status"],
        document_id=job.get("document_id"),
        error=job.get("error"),
    )


async def update_ingestion_job(job_id: str, **updates: str) -> None:
    redis = get_redis()
    key = f"devmind:job:{job_id}"
    try:
        raw = await redis.get(key)
        job = json.loads(raw) if raw else {"id": job_id}
        job.update(updates)
        await redis.set(key, json.dumps(job))
    finally:
        await redis.aclose()