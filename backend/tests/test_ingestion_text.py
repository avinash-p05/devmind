from app.domain.contracts import SourceMetadata
from app.ingestion.text import chunk_text, normalize_text


def test_normalize_text_collapses_whitespace_and_blank_lines() -> None:
    assert normalize_text("  first   line  \n\n\n second\tline ") == "first line\n\nsecond line"


def test_chunking_preserves_metadata_and_is_deterministic() -> None:
    metadata = SourceMetadata(
        source_type="document", source_name="runbook.md", path="docs/runbook.md"
    )
    content = "0123456789" * 20

    first = chunk_text(content, metadata, chunk_size=40, overlap=10)
    second = chunk_text(content, metadata, chunk_size=40, overlap=10)

    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]
    assert first[0].metadata.path == "docs/runbook.md"
    assert first[0].ordinal == 0
    assert first[1].content.startswith(first[0].content[-10:])
