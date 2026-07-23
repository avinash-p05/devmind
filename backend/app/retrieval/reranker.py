from dataclasses import dataclass


@dataclass(frozen=True)
class RankedCandidate:
    chunk_id: str
    score: float
    retrieval_method: str


def combine_scores(semantic_score: float | None, keyword_score: float | None) -> float:
    """Blend normalized retrieval scores while preserving single-source results."""
    if semantic_score is None:
        return max(0.0, min(1.0, keyword_score or 0.0))
    if keyword_score is None:
        return max(0.0, min(1.0, semantic_score))
    return max(0.0, min(1.0, semantic_score * 0.65 + keyword_score * 0.35))


def reciprocal_rank_fusion(
    semantic_rank: int | None,
    keyword_rank: int | None,
    *,
    semantic_weight: float = 0.65,
    keyword_weight: float = 0.35,
    rank_constant: int = 60,
) -> float:
    """Combine independent retrieval rankings without comparing score scales."""
    if rank_constant <= 0:
        raise ValueError("rank_constant must be positive")
    if semantic_weight < 0 or keyword_weight < 0:
        raise ValueError("retrieval weights must be non-negative")

    score = 0.0
    if semantic_rank is not None:
        score += semantic_weight / (rank_constant + semantic_rank)
    if keyword_rank is not None:
        score += keyword_weight / (rank_constant + keyword_rank)
    return score