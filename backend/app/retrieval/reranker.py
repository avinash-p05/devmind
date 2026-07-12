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