import json
import re
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import AgentState, run_agent
from app.config import get_settings
from app.schemas import ChatResponse, Citation, IncidentAnalysis


def citations(state: AgentState, numbers: list[int] | None = None) -> list[Citation]:
    """Sources by citation number: the ones the answer cited unless `numbers` is given."""
    hits = state["hits"]
    return [
        Citation(
            number=number,
            chunk_id=hits[number - 1].chunk_id,
            document_name=hits[number - 1].path.rsplit("/", 1)[-1],
            path=hits[number - 1].path,
            score=hits[number - 1].score,
            metadata=hits[number - 1].metadata,
        )
        for number in (state["cited"] if numbers is None else numbers)
    ]


def _confidence(state: AgentState) -> str:
    return "high" if not state["refused"] and state["citations_valid"] else "low"


async def ask(session: AsyncSession, question: str, top_k: int = 5) -> ChatResponse:
    started = perf_counter()
    state = await run_agent(session, question, top_k)
    prompt_tokens = state.get("prompt_tokens", 0)
    completion_tokens = state.get("completion_tokens", 0)
    return ChatResponse(
        query=question,
        answer=state["answer"],
        route=state["route"],
        tools_used=state["tools_used"],
        refused=state["refused"],
        confidence=_confidence(state),
        evidence_sufficient=not state["refused"],
        citations=citations(state),
        citation_validation_passed=state["citations_valid"],
        top_similarity=state["top_similarity"],
        llm_model=get_settings().llm_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        latency_ms=round((perf_counter() - started) * 1000, 1),
    )


async def analyze_incident(
    session: AsyncSession, query: str, service: str, severity: str, top_k: int = 5
) -> IncidentAnalysis:
    state = await run_agent(
        session, f"{service}: {query}", top_k, task="incident", service=service, severity=severity
    )
    report = {} if state["refused"] else _parse_json(state["answer"])
    return IncidentAnalysis(
        service=service,
        severity=severity,
        root_cause_hypothesis=report.get("root_cause") or state["answer"],
        affected_component=report.get("affected_component") or service,
        recommended_next_steps=list(report.get("next_steps") or []),
        unresolved_questions=list(report.get("unresolved_questions") or []),
        evidence=citations(state),
        retrieved=citations(state, list(range(1, len(state["hits"]) + 1))),
        confidence=_confidence(state),
        route=state["route"],
        total_tokens=state.get("prompt_tokens", 0) + state.get("completion_tokens", 0),
    )


def _parse_json(text: str) -> dict:
    """Models sometimes wrap JSON in prose or ``` fences; take the outermost object."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
