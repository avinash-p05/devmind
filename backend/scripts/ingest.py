"""Index a directory (repository or document folder) and print ingestion stats.

    python scripts/ingest.py ./build/corpus
"""

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from app.db import SessionFactory, init_db
from app.ingestion.parsers import parse_directory
from app.ingestion.pipeline import index_sources


async def run(path: Path, batch_size: int) -> dict:
    await init_db()
    sources = parse_directory(path)
    async with SessionFactory() as session:
        stats = await index_sources(session, sources, batch_size)
    return asdict(stats)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.path, args.batch_size)), indent=2))


if __name__ == "__main__":
    main()
