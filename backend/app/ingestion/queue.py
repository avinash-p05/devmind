"""Async ingestion: the API pushes a job id onto a Redis list; app.worker pops and indexes it."""

import json
from uuid import UUID, uuid4

from redis.asyncio import Redis

from app.config import get_settings
from app.schemas import DocumentCreate, IngestionJob

QUEUE = "devmind:ingestion"
JOB_TTL_SECONDS = 24 * 3600


def redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def _key(job_id: UUID | str) -> str:
    return f"devmind:job:{job_id}"


async def enqueue(redis: Redis, payload: DocumentCreate) -> IngestionJob:
    job = IngestionJob(id=uuid4(), status="queued")
    record = {**job.model_dump(mode="json"), "payload": payload.model_dump(mode="json")}
    await redis.set(_key(job.id), json.dumps(record), ex=JOB_TTL_SECONDS)
    await redis.rpush(QUEUE, str(job.id))
    return job


async def load_job(redis: Redis, job_id: UUID | str) -> dict | None:
    raw = await redis.get(_key(job_id))
    return json.loads(raw) if raw else None


async def update_job(redis: Redis, job_id: UUID | str, **changes) -> None:
    record = await load_job(redis, job_id) or {"id": str(job_id)}
    record.update(changes)
    await redis.set(_key(job_id), json.dumps(record), ex=JOB_TTL_SECONDS)


async def get_job(redis: Redis, job_id: UUID) -> IngestionJob | None:
    record = await load_job(redis, job_id)
    return IngestionJob.model_validate(record) if record else None


async def queue_stats(redis: Redis) -> dict:
    """Jobs waiting in the queue, plus job counts by status (jobs expire after 24 h)."""
    by_status: dict[str, int] = {}
    async for key in redis.scan_iter(match="devmind:job:*", count=500):
        record = await load_job(redis, key.removeprefix("devmind:job:"))
        if record:
            by_status[record["status"]] = by_status.get(record["status"], 0) + 1
    return {"pending": await redis.llen(QUEUE), "jobs_by_status": by_status}
