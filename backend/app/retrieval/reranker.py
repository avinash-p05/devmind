import re
from collections.abc import Sequence

RRF_K = 60  # standard Reciprocal Rank Fusion constant

_TOKEN = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    "a an and are as at be by did do does for from how in is it of on or should the this "
    "to was what when where which who why with".split()
)


def reciprocal_rank_fusion[T](rankings: Sequence[Sequence[T]], k: int = RRF_K) -> dict[T, float]:
    """score(item) = sum over rankings of 1 / (k + rank).

    Uses only rank positions, so cosine similarities and BM25-style scores, which live on
    different scales, never have to be compared. An item ranked high by *either* retriever
    scores well; an item ranked high by both scores best.
    """
    if k <= 0:
        raise ValueError("k must be positive")
    scores: dict[T, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return scores


def terms(text: str) -> set[str]:
    # A 5-character prefix is a cheap stemmer: "normalized" and "normalization" both match.
    return {
        token[:5]
        for token in _TOKEN.findall(text.lower())
        if len(token) > 2 and token not in STOPWORDS
    }


def term_coverage(query: str, text: str) -> float:
    """Fraction of the distinct query terms that appear in the text."""
    query_terms = terms(query)
    if not query_terms:
        return 0.0
    return len(query_terms & terms(text)) / len(query_terms)


def rerank[T](
    query: str,
    candidates: Sequence[tuple[T, str, float]],
    *,
    coverage_weight: float = 0.5,
) -> list[tuple[T, float]]:
    """Second-stage rerank of fused (item, text, fusion_score) candidates.

    RRF only sees rank positions. This stage reads the candidate text and rewards chunks
    that cover more of the question, so a chunk one retriever ranked low but that matches
    the whole question can move up.
    """
    if not 0 <= coverage_weight <= 1:
        raise ValueError("coverage_weight must be between 0 and 1")
    if not candidates:
        return []
    top_fusion = max(score for _, _, score in candidates) or 1.0
    scored = [
        (
            item,
            (1 - coverage_weight) * (fusion / top_fusion)
            + coverage_weight * term_coverage(query, text),
        )
        for item, text, fusion in candidates
    ]
    return sorted(scored, key=lambda pair: pair[1], reverse=True)
