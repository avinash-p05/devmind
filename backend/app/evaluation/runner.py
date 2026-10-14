"""Run the evaluation dataset through the retriever (retrieval_only) or the full agent."""

import json
from pathlib import Path
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import run_agent
from app.evaluation import metrics
from app.retrieval.hybrid import search

DATASET_DIR = Path(__file__).parents[2] / "data" / "evaluation"


def load_dataset(version: str = "v1") -> list[dict]:
    path = DATASET_DIR / f"{version}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"evaluation dataset not found: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


async def evaluate(
    session: AsyncSession,
    cases: list[dict],
    *,
    mode: str = "hybrid",
    top_k: int = 5,
    retrieval_only: bool = False,
) -> tuple[dict, list[dict]]:
    results = []
    for case in cases:
        started = perf_counter()
        if retrieval_only:
            retrieval = await search(session, case["question"], top_k, mode)
            row = _retrieval_row(case, [hit.path for hit in retrieval.hits])
        else:
            state = await run_agent(session, case["question"], top_k)
            row = _agent_row(case, state)
        row["latency_ms"] = round((perf_counter() - started) * 1000, 1)
        results.append(row)
    return metrics.summarize(results), results


def _retrieval_row(case: dict, retrieved: list[str]) -> dict:
    expected = case["expected_sources"]
    return {
        "id": case["id"],
        "question": case["question"],
        "type": case["type"],
        "expected_sources": expected,
        "retrieved_sources": retrieved,
        "retrieval_recall": metrics.recall_at_k(retrieved, expected),
        "retrieval_precision": metrics.precision_at_k(retrieved, expected),
        "reciprocal_rank": metrics.reciprocal_rank(retrieved, expected),
        "hit": metrics.recall_at_k(retrieved, expected) > 0,
    }


def _agent_row(case: dict, state: dict) -> dict:
    hits = state["hits"]
    row = _retrieval_row(case, [hit.path for hit in hits])
    expected = case["expected_sources"]
    cited = [hits[number - 1].path for number in state["cited"]]
    if expected:
        answered = not state["refused"]
        correct = answered and metrics.answer_correct(state["answer"], case["key_facts"])
    else:
        correct = state["refused"]  # the right answer to an unanswerable question is "I don't know"
    precision = metrics.citation_precision(cited, expected)
    return row | {
        "answer": state["answer"],
        "refused": state["refused"],
        "answer_correct": correct,
        "cited_sources": cited,
        "citation_valid": state["citations_valid"],
        "citation_precision": precision,
        # Valid citations, and at least one of them points at a source that holds the answer.
        "citation_accurate": state["citations_valid"] and precision > 0,
        "route": state["route"],
        "prompt_tokens": state.get("prompt_tokens", 0),
        "completion_tokens": state.get("completion_tokens", 0),
        "llm_calls": state.get("generation_attempts", 0),
    }
