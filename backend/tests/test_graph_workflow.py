from uuid import uuid4

from app.graph.workflow import _analyze_query, _generate_answer, _should_retry, _validate_citations
from app.schemas import SearchResult


def test_query_analyzer_routes_code_questions() -> None:
    assert (
        _analyze_query({"query": "Where is OAuth validation implemented?"})["route"]
        == "code_search"
    )
    assert _analyze_query({"query": "What does the service own?"})["route"] == "hybrid_retrieval"


def test_query_analyzer_routes_incidents_and_logs() -> None:
    assert _analyze_query({"query": "What caused the payment outage?"})["route"] == (
        "incident_analysis"
    )
    assert _analyze_query({"query": "Find the request ID in the logs"})["route"] == "log_search"


def test_retrieval_retries_once_when_evidence_is_missing() -> None:
    assert _should_retry({"evidence": [], "retrieval_attempts": 1}) == "retrieve_more"
    assert _should_retry({"evidence": [], "retrieval_attempts": 2}) == "generate_answer"


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
