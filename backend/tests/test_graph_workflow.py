from uuid import uuid4

from app.graph.workflow import _analyze_query, _generate_answer, _validate_citations
from app.schemas import SearchResult


def test_query_analyzer_routes_code_questions() -> None:
    assert (
        _analyze_query({"query": "Where is OAuth validation implemented?"})["route"]
        == "code_search"
    )
    assert _analyze_query({"query": "Why did the service fail?"})["route"] == "hybrid_retrieval"


def test_citation_validation_keeps_only_retrieved_chunks() -> None:
    chunk_id = uuid4()
    evidence = SearchResult(
        chunk_id=chunk_id,
        document_id=uuid4(),
        document_name="incident.md",
        content="The pool exhausted.",
        score=0.9,
        rank=1,
        retrieval_method="hybrid",
        metadata={},
    )
    state = _generate_answer({"query": "Why?", "evidence": [evidence]})
    state["citations"].append(state["citations"][0].model_copy(update={"chunk_id": uuid4()}))

    validated = _validate_citations(state)

    assert validated["evidence_sufficient"] is True
    assert [citation.chunk_id for citation in validated["citations"]] == [chunk_id]
