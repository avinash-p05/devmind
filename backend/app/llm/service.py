import json
import re
from time import perf_counter
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app.config import get_settings
from app.schemas import SearchResult


def _local_answer(
    query: str, evidence: list[SearchResult], correction: bool = False
) -> str:
    lead = evidence[0]
    citations = ", ".join(f"[{item.chunk_id}]" for item in evidence[:3])
    prefix = "Use only the cited evidence. " if correction else ""
    return (
        prefix +
        f"The strongest indexed evidence for this question is in {lead.document_name}. "
        f"It indicates: {lead.content}\n\nSources: {citations}"
    )


def _grounding_prompt(
    query: str, evidence: list[SearchResult], correction: bool = False
) -> str:
    context = "\n\n".join(
        f"[{item.chunk_id}] {item.document_name}\n{item.content}" for item in evidence
    )
    correction_note = (
        " The previous answer had invalid or missing citations. Return only claims "
        "supported by the evidence and cite valid IDs exactly."
        if correction
        else ""
    )
    return (
        "Answer the engineering question using only the evidence below. "
        "Separate verified evidence from inference. Do not invent facts. "
        "Cite every factual statement with one or more source IDs in brackets."
        f"{correction_note}\n\n"
        f"Question: {query}\n\nEvidence:\n{context}"
    )


def _remote_answer(
    query: str, evidence: list[SearchResult], correction: bool = False
) -> tuple[str, int | None]:
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
                        "content": [{
                            "type": "text",
                            "text": (
                                "You are a grounded engineering incident assistant. "
                                "Use only supplied evidence and include citation IDs. "
                                "Never cite an ID that is not supplied."
                            ),
                        }],
                    },
                    {
                        "role": "user",
                        "content": [{
                            "type": "text",
                            "text": _grounding_prompt(query, evidence, correction),
                        }],
                    },
                ],
            }
        ).encode(),
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.llm_timeout_seconds) as response:
            payload = json.load(response)
    except HTTPError as error:
        detail = error.read(2000).decode("utf-8", errors="replace")
        raise RuntimeError(
            f"LLM provider request failed with HTTP {error.code}: {detail}"
        ) from error
    usage = payload.get("usage", {})
    tokens = usage.get("total_tokens")
    return payload["choices"][0]["message"]["content"], tokens


async def generate_grounded_answer(
    query: str, evidence: list[SearchResult], correction: bool = False
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
        answer = _local_answer(query, evidence, correction)
        tokens = max(1, len(answer) // 4)
    else:
        answer, provider_tokens = _remote_answer(query, evidence, correction)
        tokens = provider_tokens or max(1, len(answer) // 4)
    metadata = llm_metadata()
    metadata["latency_ms"] = round((perf_counter() - started) * 1000, 2)
    metadata["tokens"] = tokens
    return answer, tokens, metadata


def cited_chunk_ids(answer: str) -> set[str]:
    return set(re.findall(r"\[([0-9a-fA-F-]{36})\]", answer))


def llm_metadata() -> dict[str, str | int | float]:
    settings = get_settings()
    return {"provider": settings.llm_provider, "model": settings.llm_model}
