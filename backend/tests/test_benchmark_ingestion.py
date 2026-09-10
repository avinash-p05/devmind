from pathlib import Path

from app.ingestion.corpus import generate_corpus


def test_corpus_generator_supports_benchmark_size(tmp_path: Path) -> None:
    assert generate_corpus(tmp_path, 1001) == 1001
    assert len([path for path in tmp_path.rglob("*") if path.is_file()]) == 1001
