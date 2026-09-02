import json
from time import perf_counter
from urllib.request import Request, urlopen

from app.config import get_settings
from app.schemas import SearchResult


def _local_answer(query: str, evidence: list[SearchResult]) -> str:
    lead = evidence[0]
    citations = ", ".join(f"[{item.chunk_id}]" for item in evidence[:3])
    return (
        f"The strongest indexed evidence for this question is in {lead.document_name}. "
        f"It indicates: {lead.content}\n\nSources: {citations}"
    )


def _grounding_prompt(query: str, evidence: list[SearchResult]) -> str:
    context = "\n\n".join(
        f"[{item.chunk_id}] {item.document_name}\n{item.content}" for item in evidence
    )
    return (
        "Answer the engineering question using only the evidence below. "
        "Separate verified evidence from inference. Do not invent facts. "
        "Cite every factual statement with one or more source IDs in brackets.\n\n"
        f"Question: {query}\n\nEvidence:\n{context}"
    )


def _remote_answer(query: str, evidence: list[SearchResult]) -> tuple[str, int | None]:
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is required when LLM_PROVIDER is not 'local'")
    request = Request(
        f"{settings.llm_base_url.rstrip('/')}/chat/completions",
        data=json.dumps(
            {
                "model": settings.llm_model,
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a grounded engineering incident assistant. "
                            "Use only supplied evidence and include citation IDs."
                        ),
                    },
                    {"role": "user", "content": _grounding_prompt(query, evidence)},
                ],
            }
        ).encode(),
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=settings.llm_timeout_seconds) as response:
        payload = json.load(response)
    usage = payload.get("usage", {})
    tokens = usage.get("total_tokens")
    return payload["choices"][0]["message"]["content"], tokens


async def generate_grounded_answer(
    query: str, evidence: list[SearchResult]
) -> tuple[str, int, dict[str, str | int | float]]:
    if not evidence:
        return (
            "I could not find supporting evidence in the indexed workspace. "
            "Add the relevant source or refine the question.",
            0,
            llm_metadata(),
        )
    started = perf_counter()
    settings = get_settings()
    if settings.llm_provider.lower() == "local":
        answer = _local_answer(query, evidence)
        tokens = max(1, len(answer) // 4)
    else:
        answer, provider_tokens = _remote_answer(query, evidence)
        tokens = provider_tokens or max(1, len(answer) // 4)
    metadata = llm_metadata()
    metadata["latency_ms"] = round((perf_counter() - started) * 1000, 2)
    metadata["tokens"] = tokens
    return answer, tokens, metadata


def llm_metadata() -> dict[str, str | int | float]:
    settings = get_settings()
    return {"provider": settings.llm_provider, "model": settings.llm_model}
