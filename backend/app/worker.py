"""Ingestion worker: `python -m app.worker`. Retries a failing job up to MAX_ATTEMPTS times."""

import asyncio
import logging

from app.db import SessionFactory, init_db
from app.ingestion.parsers import parse_text
from app.ingestion.pipeline import index_source
from app.ingestion.queue import QUEUE, load_job, redis_client, update_job
from app.schemas import DocumentCreate

MAX_ATTEMPTS = 3
log = logging.getLogger("devmind.worker")


async def process(redis, job_id: str) -> None:
    job = await load_job(redis, job_id)
    if job is None:
        return
    attempts = job.get("attempts", 0) + 1
    await update_job(redis, job_id, status="processing", attempts=attempts)
    try:
        payload = DocumentCreate.model_validate(job["payload"])
        async with SessionFactory() as session:
            document = await index_source(
                session, parse_text(payload.name, payload.content, payload.source_type)
            )
        await update_job(redis, job_id, status="completed", document_id=str(document.id))
    except Exception as error:
        log.exception("ingestion job %s failed (attempt %s)", job_id, attempts)
        if attempts < MAX_ATTEMPTS:
            await update_job(redis, job_id, status="retrying", error=str(error))
            await redis.rpush(QUEUE, job_id)
        else:
            await update_job(redis, job_id, status="failed", error=str(error))


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_db()
    redis = redis_client()
    try:
        while True:
            item = await redis.blpop(QUEUE, timeout=5)
            if item:
                await process(redis, item[1])
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
