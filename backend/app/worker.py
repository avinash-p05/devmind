import asyncio
import json

from redis.asyncio import Redis

from app.config import get_settings
from app.ingestion.queue import QUEUE_NAME, update_ingestion_job
from app.persistence.database import SessionFactory, initialize_database
from app.persistence.service import create_persisted_document
from app.schemas import DocumentCreate


async def run_worker() -> None:
    settings = get_settings()
    await initialize_database()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        while True:
            item = await redis.blpop(QUEUE_NAME, timeout=5)
            if item is None:
                continue
            _, job_id = item
            raw = await redis.get(f"devmind:job:{job_id}")
            if raw is None:
                continue
            job = json.loads(raw)
            await update_ingestion_job(job_id, status="processing")
            try:
                async with SessionFactory() as session:
                    document = await create_persisted_document(
                        session, DocumentCreate.model_validate(job["payload"])
                    )
                await update_ingestion_job(
                    job_id, status="completed", document_id=str(document.id)
                )
            except Exception as error:
                await update_ingestion_job(job_id, status="failed", error=str(error))
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run_worker())