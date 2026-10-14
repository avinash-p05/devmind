import pytest

from app.evaluation import metrics


def test_recall_precision_and_reciprocal_rank():
    retrieved = ["a.md", "b.md", "a.md", "c.md"]
    expected = ["b.md", "d.md"]

    assert metrics.recall_at_k(retrieved, expected) == 0.5
    assert metrics.precision_at_k(retrieved, expected) == pytest.approx(1 / 3)  # unique docs
    assert metrics.reciprocal_rank(retrieved, expected) == 0.5


def test_fact_matching_tolerates_rephrasing_but_requires_the_details():
    assert metrics.fact_supported("The URI gets validated before exchange", "URI validated")
    assert metrics.fact_supported("It retries up to 4 times", "4")
    assert not metrics.fact_supported("It retries up to 5 times", "4")


def test_numbers_match_when_attached_to_units():
    assert metrics.fact_supported("The timeout is 3000ms", "3000")


def test_fact_alternatives():
    assert metrics.fact_supported("Requests waited 5 seconds", "5 seconds|5000")
    assert metrics.fact_supported("waited=5000ms", "5 seconds|5000ms")


def test_answer_correct_needs_every_fact():
    assert metrics.answer_correct("codes 502, 503 and 504", ["502", "503", "504"])
    assert not metrics.answer_correct("codes 502 and 503", ["502", "503", "504"])
    assert not metrics.answer_correct("anything", [])


def test_citation_precision():
    assert metrics.citation_precision(["a.md", "b.md"], ["a.md"]) == 0.5
    assert metrics.citation_precision([], ["a.md"]) == 0.0


def test_summarize_separates_answerable_and_unanswerable():
    rows = [
        {
            "type": "docs", "expected_sources": ["a.md"], "retrieval_recall": 1.0, "hit": True,
            "reciprocal_rank": 1.0, "retrieval_precision": 0.5, "latency_ms": 10.0,
            "answer": "x [1]", "refused": False, "answer_correct": True,
            "citation_accurate": True, "citation_precision": 1.0, "citation_valid": True,
            "prompt_tokens": 100, "completion_tokens": 10, "llm_calls": 1,
        },
        {
            "type": "unanswerable", "expected_sources": [], "retrieval_recall": 0.0,
            "hit": False, "reciprocal_rank": 0.0, "retrieval_precision": 0.0,
            "latency_ms": 30.0, "answer": "I don't know", "refused": True,
            "answer_correct": True, "citation_accurate": False, "citation_precision": 0.0,
            "citation_valid": True, "prompt_tokens": 0, "completion_tokens": 0, "llm_calls": 0,
        },
    ]

    summary = metrics.summarize(rows)

    assert summary["recall_at_k"] == 1.0  # the unanswerable row does not drag recall down
    assert summary["correct_refusal_rate"] == 1.0
    assert summary["false_refusal_rate"] == 0.0
    assert summary["total_tokens"] == 110
    assert summary["llm_calls"] == 1
