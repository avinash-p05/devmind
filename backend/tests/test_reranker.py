import pytest

from app.retrieval.reranker import reciprocal_rank_fusion


def test_reciprocal_rank_fusion_prefers_evidence_in_both_rankings() -> None:
    agreement = reciprocal_rank_fusion(1, 1)
    semantic_only = reciprocal_rank_fusion(1, None)
    keyword_only = reciprocal_rank_fusion(None, 1)

    assert agreement > semantic_only
    assert agreement > keyword_only


def test_reciprocal_rank_fusion_rejects_invalid_rank_constant() -> None:
    with pytest.raises(ValueError, match="rank_constant"):
        reciprocal_rank_fusion(1, 1, rank_constant=0)
