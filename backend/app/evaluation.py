import json
import time
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import EvaluationRunRecord
from app.persistence.service import search_persisted_documents
from app.schemas import EvaluationRunRequest, EvaluationRunResponse

DATASET_PATH = Path(__file__).parents[1] / "data" / "evaluation" / "cases.jsonl"


def _load_cases(dataset_version: str) -> list[dict]:
    if dataset_version != "v1" or not DATASET_PATH.exists():
        return []
    return [json.loads(line) for line in DATASET_PATH.read_text().splitlines() if line.strip()]


async def run_evaluation(
    session: AsyncSession, request: EvaluationRunRequest
) -> EvaluationRunResponse:
    run_id = uuid4()
    cases = _load_cases(request.dataset_version)
    case_results: list[dict] = []
    for case in cases:
        started = time.perf_counter()
        retrieved = await search_persisted_documents(
            session, case["question"], request.top_k, request.mode
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        expected_sources = set(case.get("expected_sources", []))
        retrieved_sources = {
            result.document_name
            for result in retrieved
        } | {
            str(result.metadata.get("path"))
            for result in retrieved
            if result.metadata.get("path")
        }
        relevant = expected_sources & retrieved_sources
        key_facts = [fact.lower() for fact in case.get("key_facts", [])]
        evidence_text = " ".join(result.content.lower() for result in retrieved)
        facts_supported = sum(fact in evidence_text for fact in key_facts)
        case_results.append(
            {
                "question": case["question"],
                "retrieval_recall": round(len(relevant) / len(expected_sources), 4)
                if expected_sources
                else 0.0,
                "retrieval_precision": round(len(relevant) / len(retrieved), 4)
                if retrieved
                else 0.0,
                "answer_correct": bool(key_facts) and facts_supported == len(key_facts),
                "citation_accurate": bool(relevant),
                "hallucination": bool(key_facts) and facts_supported < len(key_facts),
                "latency_ms": latency_ms,
                "estimated_tokens": max(1, len(case["question"] + evidence_text) // 4),
                "retrieved_sources": sorted(retrieved_sources),
            }
        )

    summary = _summarize(case_results)
    record = EvaluationRunRecord(
        id=run_id,
        dataset_version=request.dataset_version,
        mode=request.mode,
        status="completed",
        summary_json=summary,
        results_json=case_results,
    )
    session.add(record)
    await session.commit()
    return EvaluationRunResponse(
        id=run_id,
        dataset_version=request.dataset_version,
        mode=request.mode,
        status="completed",
        summary=summary,
        results=case_results,
        created_at=record.created_at,
    )


async def get_evaluation(session: AsyncSession, run_id: UUID) -> EvaluationRunResponse | None:
    record = await session.scalar(
        select(EvaluationRunRecord).where(EvaluationRunRecord.id == run_id)
    )
    if record is None:
        return None
    return EvaluationRunResponse(
        id=record.id,
        dataset_version=record.dataset_version,
        mode=record.mode,
        status=record.status,
        summary=record.summary_json,
        results=record.results_json,
        created_at=record.created_at,
    )


def _summarize(results: list[dict]) -> dict:
    if not results:
        return {"case_count": 0}
    fields = (
        "retrieval_recall",
        "retrieval_precision",
        "answer_correct",
        "citation_accurate",
        "hallucination",
        "latency_ms",
        "estimated_tokens",
    )
    return {
        "case_count": len(results),
        "recall_at_k": round(sum(item["retrieval_recall"] for item in results) / len(results), 4),
        "precision_at_k": round(
            sum(item["retrieval_precision"] for item in results) / len(results), 4
        ),
        "answer_correctness": round(
            sum(item["answer_correct"] for item in results) / len(results), 4
        ),
        "citation_accuracy": round(
            sum(item["citation_accurate"] for item in results) / len(results), 4
        ),
        "hallucination_rate": round(
            sum(item["hallucination"] for item in results) / len(results), 4
        ),
        "avg_latency_ms": round(sum(item["latency_ms"] for item in results) / len(results), 2),
        "avg_estimated_tokens": round(
            sum(item["estimated_tokens"] for item in results) / len(results), 2
        ),
        "measured_fields": fields,
    }