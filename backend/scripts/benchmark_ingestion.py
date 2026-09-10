import argparse
import asyncio
import json
import time
from pathlib import Path

from sqlalchemy import func, select

from app.ingestion.bulk import index_repository
from app.ingestion.corpus import generate_corpus
from app.persistence.database import SessionFactory, initialize_database
from app.persistence.models import ChunkRecord, DocumentRecord


async def run(root: Path, output: Path, document_count: int, batch_size: int) -> dict:
    if document_count:
        generate_corpus(root, document_count)
    await initialize_database()
    metrics: dict[str, float] = {}
    started = time.perf_counter()
    async with SessionFactory() as session:
        stats = await index_repository(session, root, batch_size=batch_size, metrics=metrics)
        first_pass_ms = round((time.perf_counter() - started) * 1000, 2)
        duplicate_started = time.perf_counter()
        duplicate_stats = await index_repository(session, root, batch_size=batch_size)
        duplicate_pass_ms = round((time.perf_counter() - duplicate_started) * 1000, 2)
        document_total = await session.scalar(select(func.count(DocumentRecord.id)))
        chunk_total = await session.scalar(select(func.count(ChunkRecord.id)))
    result = {
        "path": str(root),
        "requested_documents": document_count or None,
        "discovered": stats.discovered,
        "indexed": stats.indexed,
        "skipped_duplicates": stats.skipped_duplicates,
        "failed": stats.failed,
        "errors": stats.errors,
        "document_total": document_total or 0,
        "chunk_total": chunk_total or 0,
        "ingestion_duration_ms": first_pass_ms,
        "embedding_duration_ms": round(metrics.get("embedding_duration_ms", 0.0), 2),
        "average_processing_ms": round(first_pass_ms / stats.indexed, 2)
        if stats.indexed
        else 0.0,
        "duplicate_pass": {
            "skipped_duplicates": duplicate_stats.skipped_duplicates,
            "duration_ms": duplicate_pass_ms,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark DevMind repository ingestion")
    parser.add_argument("path", type=Path)
    parser.add_argument("--documents", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument(
        "--output", type=Path, default=Path("data/evaluation/ingestion-report.json")
    )
    args = parser.parse_args()
    result = asyncio.run(run(args.path, args.output, args.documents, args.batch_size))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
