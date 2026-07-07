import pytest

from app.domain.contracts import SourceMetadata
from app.ingestion.parsers import parse_text_source


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
