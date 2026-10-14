"""Run the evaluation dataset and write a JSON report.

    python scripts/evaluate.py --retrieval-only   # vector vs keyword vs hybrid, no LLM calls
    python scripts/evaluate.py                    # full agent: answers, citations, tokens
"""

import argparse
import asyncio
import json
from pathlib import Path

from app.db import SessionFactory, init_db
from app.evaluation.runner import evaluate, load_dataset
from app.llm import provider_info

REPORT_DIR = Path(__file__).parents[1] / "data" / "evaluation"


async def run(dataset: str, top_k: int, retrieval_only: bool) -> dict:
    await init_db()
    cases = load_dataset(dataset)
    report: dict = {"dataset": dataset, "cases": len(cases), "top_k": top_k}
    async with SessionFactory() as session:
        if retrieval_only:
            for mode in ("vector", "keyword", "hybrid"):
                summary, results = await evaluate(
                    session, cases, mode=mode, top_k=top_k, retrieval_only=True
                )
                report[mode] = summary
            report["misses_hybrid"] = [
                {k: r[k] for k in ("id", "question", "expected_sources", "retrieved_sources")}
                for r in results
                if r["expected_sources"] and r["retrieval_recall"] < 1
            ]
        else:
            summary, results = await evaluate(session, cases, top_k=top_k)
            report |= {"providers": provider_info(), "agent": summary, "results": results}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", default="v1")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(run(args.dataset, args.top_k, args.retrieval_only))
    name = "retrieval-report.json" if args.retrieval_only else "agent-report.json"
    output = args.output or REPORT_DIR / name
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    printable = {k: v for k, v in report.items() if k not in {"results"}}
    print(json.dumps(printable, indent=2))


if __name__ == "__main__":
    main()
