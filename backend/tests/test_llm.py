from uuid import uuid4

import pytest

from app.llm.service import cited_chunk_ids, generate_grounded_answer
from app.schemas import SearchResult


@pytest.mark.asyncio
async def test_local_grounded_generation_includes_retrieved_citations() -> None:
    chunk_id = uuid4()
    evidence = [
        SearchResult(
            chunk_id=chunk_id,
            document_id=uuid4(),
            document_name="payment-incident.md",
            content="The deployment exhausted the database connection pool.",
            score=0.9,
            rank=1,
            retrieval_method="hybrid",
            metadata={},
        )
    ]

    answer, tokens, metadata = await generate_grounded_answer(
        "Why did payment fail?", evidence
    )

    assert str(chunk_id) in answer
    assert "database connection pool" in answer
    assert tokens > 0
    assert metadata["provider"] == "local"


def test_cited_chunk_ids_extracts_only_uuid_citations() -> None:
    chunk_id = uuid4()

    assert cited_chunk_ids(f"Supported claim [{chunk_id}]") == {str(chunk_id)}
    assert cited_chunk_ids("Unsupported claim [not-a-chunk]") == set()
