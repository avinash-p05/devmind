import argparse
import json
from pathlib import Path

from app.evaluation import _load_cases, run_evaluation
from app.persistence.database import SessionFactory, initialize_database
from app.schemas import EvaluationRunRequest


async def run(dataset_version: str, top_k: int, output: Path) -> None:
    await initialize_database()
    async with SessionFactory() as session:
        hybrid = await run_evaluation(
            session,
            EvaluationRunRequest(dataset_version=dataset_version, mode="hybrid", top_k=top_k),
        )
        semantic = await run_evaluation(
            session,
            EvaluationRunRequest(dataset_version=dataset_version, mode="semantic", top_k=top_k),
        )
    report = {
        "dataset_version": dataset_version,
        "case_count": len(_load_cases(dataset_version)),
        "top_k": top_k,
        "hybrid": hybrid.summary,
        "semantic": semantic.summary,
        "hybrid_beats_semantic_recall": (
            hybrid.summary.get("recall_at_k", 0)
            > semantic.summary.get("recall_at_k", 0)
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reproducible DevMind retrieval benchmarks")
    parser.add_argument("--dataset", default="v1")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("data/evaluation/report.json"))
    args = parser.parse_args()

    import asyncio

    asyncio.run(run(args.dataset, args.top_k, args.output))


if __name__ == "__main__":
    main()
