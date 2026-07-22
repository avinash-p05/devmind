from pathlib import Path

import pytest

from app.domain.contracts import SourceMetadata
from app.ingestion.parsers import parse_file, parse_repository_snapshot, parse_text_source


def test_parse_text_source_returns_normalized_content() -> None:
    source = parse_text_source(
        "  stack trace  ",
        SourceMetadata(source_type="log", source_name="app.log", service="payments"),
    )

    assert source.content == "stack trace"
    assert source.metadata.service == "payments"


def test_parse_text_source_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="empty"):
        parse_text_source(" \n\t", SourceMetadata(source_type="document", source_name="empty.txt"))


def test_parse_file_extracts_html_and_preserves_path(tmp_path) -> None:
    path = tmp_path / "incident.html"
    path.write_text("<h1>Payment failure</h1><p>Pool exhausted.</p>", encoding="utf-8")

    parsed = parse_file(path, source_type="incident", service="payments")

    assert "Payment failure" in parsed.content
    assert "Pool exhausted." in parsed.content
    assert parsed.metadata.path == str(path)
    assert parsed.metadata.extra["format"] == "html"


def test_parse_repository_snapshot_skips_generated_directories(tmp_path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")

    parsed = parse_repository_snapshot(tmp_path)

    assert len(parsed) == 1
    assert parsed[0].metadata.path == str(Path("app") / "main.py")
    assert parsed[0].metadata.source_type == "repository"
