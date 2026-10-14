"""Workspace statistics for the dashboard: what is indexed, ingestion state, benchmark."""

import json
from pathlib import Path

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import Chunk, Document
from app.ingestion.queue import queue_stats
from app.llm import provider_info

REPORT_DIR = Path(__file__).parents[1] / "data" / "evaluation"


async def workspace_stats(session: AsyncSession, redis: Redis) -> dict:
    documents, characters, last_indexed = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(Document.content_length), 0),
                   func.max(Document.created_at))
        )
    ).one()
    chunks = await session.scalar(select(func.count()).select_from(Chunk))
    by_type = dict(
        (await session.execute(
            select(Document.source_type, func.count()).group_by(Document.source_type)
        )).all()
    )
    service = Document.metadata_json["service"].astext
    services = (
        await session.execute(
            select(service, func.count())
            .where(service.is_not(None))
            .group_by(service)
            .order_by(func.count().desc())
        )
    ).all()
    try:
        ingestion = await queue_stats(redis)
    except Exception:  # the dashboard should still load if Redis is down
        ingestion = {"pending": None, "jobs_by_status": {}}
    return {
        "documents": documents,
        "chunks": chunks or 0,
        "characters": int(characters),
        "last_indexed_at": last_indexed,
        "by_source_type": by_type,
        "services": [{"name": name, "documents": count} for name, count in services],
        "ingestion": ingestion,
        "providers": provider_info(),
        "min_score": get_settings().min_score,
        "benchmark": _benchmark(),
    }


def _benchmark() -> dict | None:
    """Latest measured results from scripts/evaluate.py, if they have been generated."""
    retrieval = _read(REPORT_DIR / "retrieval-report.json")
    agent = _read(REPORT_DIR / "agent-report.json")
    if not retrieval and not agent:
        return None
    result: dict = {}
    if retrieval:
        result["retrieval"] = {
            mode: {k: retrieval[mode][k] for k in ("recall_at_k", "hit_rate_at_k", "mrr")}
            for mode in ("vector", "keyword", "hybrid")
            if mode in retrieval
        }
        result["cases"] = retrieval.get("cases")
    if agent:
        summary = agent["agent"]
        result["agent"] = {
            "model": agent.get("providers", {}).get("llm_model"),
            **{
                k: summary.get(k)
                for k in (
                    "answer_correctness", "citation_accuracy", "correct_refusal_rate",
                    "false_refusal_rate", "latency_ms_p50", "avg_prompt_tokens",
                    "avg_completion_tokens",
                )
            },
        }
    return result


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
