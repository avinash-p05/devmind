import pytest

from app.retrieval.reranker import reciprocal_rank_fusion, rerank, term_coverage


def test_rrf_rewards_agreement_between_retrievers():
    scores = reciprocal_rank_fusion([["a", "b", "c"], ["b", "d"]])

    assert max(scores, key=scores.get) == "b"  # 2nd + 1st beats a lone 1st
    assert scores["a"] == pytest.approx(1 / 61)
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 61)


def test_rrf_treats_both_retrievers_equally():
    scores = reciprocal_rank_fusion([["vector_top"], ["keyword_top"]])
    assert scores["vector_top"] == scores["keyword_top"]


def test_rrf_rejects_non_positive_k():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"]], k=0)


def test_term_coverage_uses_prefix_stemming_and_ignores_stopwords():
    assert term_coverage("Where is severity normalized?", "normalize_severity maps labels") == 1.0
    assert term_coverage("the of and", "anything") == 0.0


def test_rerank_promotes_the_candidate_that_covers_the_question():
    query = "retry backoff configuration"
    candidates = [
        ("noise", "deploy record with unrelated changes", 1.0),
        ("answer", "config/retries.yaml retry backoff configuration", 0.6),
    ]

    ranked = rerank(query, candidates)

    assert [item for item, _ in ranked] == ["answer", "noise"]


def test_rerank_with_zero_coverage_weight_keeps_fusion_order():
    candidates = [("first", "x", 1.0), ("second", "retry backoff", 0.5)]
    assert [item for item, _ in rerank("retry backoff", candidates, coverage_weight=0)] == [
        "first",
        "second",
    ]
