import pytest

from app.ingestion.chunking import chunk_text, normalize
from app.ingestion.parsers import classify, extract_metadata, parse_directory


def test_short_text_is_one_chunk():
    assert chunk_text("hello world", chunk_size=100, overlap=10) == ["hello world"]


def test_chunks_overlap_and_cover_the_whole_text():
    text = "\n".join(f"line {i:03d} of the runbook" for i in range(200))
    chunks = chunk_text(text, chunk_size=300, overlap=60)

    assert len(chunks) > 1
    assert all(len(chunk) <= 300 for chunk in chunks)
    assert chunks[0].startswith("line 000") and chunks[-1].endswith("line 199 of the runbook")
    # Consecutive chunks share text, so a fact on a boundary is in at least one chunk.
    assert chunks[1].split("\n")[0] in chunks[0]


def test_chunks_break_on_line_boundaries():
    text = "\n".join(f"line {i:03d} of the runbook" for i in range(200))
    for chunk in chunk_text(text, chunk_size=300, overlap=60):
        assert chunk.startswith("line ")
        assert chunk.endswith("runbook")


@pytest.mark.parametrize(("size", "overlap"), [(0, 0), (100, 100), (100, -1)])
def test_invalid_chunk_settings(size, overlap):
    with pytest.raises(ValueError):
        chunk_text("text", chunk_size=size, overlap=overlap)


def test_normalize_collapses_whitespace_but_keeps_lines():
    assert normalize("a   b\n\n\n\nc\t\td  ") == "a b\n\nc d"


@pytest.mark.parametrize(
    ("path", "kind"),
    [
        ("src/db/pool.py", "code"),
        ("config/retries.yaml", "config"),
        ("logs/payment-service.log", "log"),
        ("incidents/payment.md", "incident"),
        ("postmortems/payment.md", "incident"),
        ("docs/oauth.md", "document"),
    ],
)
def test_classify(path, kind):
    assert classify(path) == kind


def test_extract_metadata_reads_incident_fields():
    content = "# Payment outage\n\nIncident ID: INC-1\nService: payment-service\nSeverity: SEV-1\n"
    metadata = extract_metadata("incidents/payment.md", content)

    assert metadata == {
        "format": "md",
        "title": "Payment outage",
        "incident_id": "INC-1",
        "service": "payment-service",
        "severity": "SEV-1",
    }


def test_parse_directory_uses_posix_relative_paths_and_skips_vendored(tmp_path):
    (tmp_path / "src" / "db").mkdir(parents=True)
    (tmp_path / "src" / "db" / "pool.py").write_text("POOL = 20\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("ignored")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")

    sources = parse_directory(tmp_path)

    assert [source.path for source in sources] == ["src/db/pool.py"]
    assert sources[0].source_type == "code"
