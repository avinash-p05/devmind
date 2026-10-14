"""Metric definitions. Pure functions so each one is easy to test and to explain."""

import re
from statistics import mean, median

from app.retrieval.reranker import STOPWORDS

FACT_MATCH_THRESHOLD = 0.75  # share of a fact's terms the answer must contain


def recall_at_k(retrieved: list[str], expected: list[str]) -> float:
    """Share of the expected sources that appear in the top-k retrieved sources."""
    if not expected:
        return 0.0
    return len(set(retrieved) & set(expected)) / len(set(expected))


def precision_at_k(retrieved: list[str], expected: list[str]) -> float:
    unique = list(dict.fromkeys(retrieved))
    if not unique:
        return 0.0
    return len(set(unique) & set(expected)) / len(unique)


def reciprocal_rank(retrieved: list[str], expected: list[str]) -> float:
    for rank, path in enumerate(retrieved, start=1):
        if path in expected:
            return 1.0 / rank
    return 0.0


def _fact_terms(text: str) -> set[str]:
    # Unlike retrieval terms, keep short numbers: "4" attempts or "6" replicas is the fact.
    found = set()
    # Split digits from letters so "3000ms" yields "3000" and "v2" yields "2".
    for word in re.findall(r"[a-z]+|[0-9]+", text.lower()):
        if word.isdigit():
            found.add(word)
        elif len(word) > 2 and word not in STOPWORDS:
            found.add(word[:5])
    return found


def fact_supported(answer: str, fact: str) -> bool:
    """A fact counts as stated when most of its terms appear in the answer.

    Exact substring matching would fail on any rephrasing ("validated" vs "validates");
    term overlap tolerates that while still requiring the specific details (numbers,
    versions, names) to be present. "a|b" lists equivalent forms, e.g. "5 seconds|5000".
    """
    answer_terms = _fact_terms(answer)
    for alternative in fact.split("|"):
        fact_terms = _fact_terms(alternative)
        if fact_terms and len(fact_terms & answer_terms) / len(fact_terms) >= FACT_MATCH_THRESHOLD:
            return True
    return False


def answer_correct(answer: str, key_facts: list[str]) -> bool:
    return bool(key_facts) and all(fact_supported(answer, fact) for fact in key_facts)


def citation_precision(cited: list[str], expected: list[str]) -> float:
    """Share of the cited sources that are actually relevant sources."""
    if not cited:
        return 0.0
    return len(set(cited) & set(expected)) / len(set(cited))


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))
    return ordered[index]


def summarize(results: list[dict]) -> dict:
    answerable = [r for r in results if r["expected_sources"]]
    unanswerable = [r for r in results if not r["expected_sources"]]
    latencies = [r["latency_ms"] for r in results]
    summary = {
        "cases": len(results),
        "answerable_cases": len(answerable),
        "unanswerable_cases": len(unanswerable),
        "recall_at_k": _avg(answerable, "retrieval_recall"),
        "hit_rate_at_k": _avg(answerable, "hit"),
        "mrr": _avg(answerable, "reciprocal_rank"),
        "precision_at_k": _avg(answerable, "retrieval_precision"),
        "latency_ms_p50": round(median(latencies), 1) if latencies else 0.0,
        "latency_ms_p95": round(percentile(latencies, 95), 1),
        "recall_by_type": {
            kind: _avg([r for r in answerable if r["type"] == kind], "retrieval_recall")
            for kind in sorted({r["type"] for r in answerable})
        },
    }
    generated = [r for r in results if "answer" in r]
    if generated:
        answered = [r for r in answerable if not r["refused"]]
        summary |= {
            "answer_correctness": _avg(answerable, "answer_correct"),
            "citation_accuracy": _avg(answered, "citation_accurate"),
            "citation_precision": _avg(answered, "citation_precision"),
            "citation_valid_rate": _avg(answered, "citation_valid"),
            "false_refusal_rate": _avg(answerable, "refused"),
            "correct_refusal_rate": _avg(unanswerable, "refused"),
            "avg_prompt_tokens": _avg(generated, "prompt_tokens", 1),
            "avg_completion_tokens": _avg(generated, "completion_tokens", 1),
            "total_tokens": sum(r["prompt_tokens"] + r["completion_tokens"] for r in generated),
            "llm_calls": sum(r["llm_calls"] for r in generated),
        }
    return summary


def _avg(rows: list[dict], key: str, digits: int = 4) -> float:
    return round(mean(float(r[key]) for r in rows), digits) if rows else 0.0
