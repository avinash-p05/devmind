"""The agent: route -> call retrieval tools -> guardrail -> generate -> validate citations.

    route_question
          |
       retrieve  (general search + the route's specialised tool as a coverage guarantee)
          |
    enough evidence? --no--> refuse   (no LLM call: nothing to ground an answer in)
          | yes
       generate  <-----------------+
          |                        |
   validate_citations --invalid--> + (one bounded correction retry)
          | valid
         END
"""

import asyncio
import re
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agent.prompts import (
    ANSWER_TEMPLATE,
    CITATION_CORRECTION,
    INCIDENT_TEMPLATE,
    REFUSAL,
    SYSTEM_PROMPT,
    format_context,
)
from app.agent.tools import ROUTE_TOOLS, TOOLS
from app.config import get_settings
from app.llm import chat
from app.retrieval.hybrid import Hit, Retrieval

MAX_GENERATIONS = 2  # first answer + one correction

_CODE = re.compile(
    r"\b(implemented|implementation|defined|function|class|method|module|code|source file|"
    r"configured|configuration|config|setting|yaml)\b|\.(py|ts|js|go|java|ya?ml)\b",
    re.IGNORECASE,
)
_LOGS = re.compile(r"\b(log|logs|logged|stack trace|exception|request id|emitted)\b", re.I)
_INCIDENT = re.compile(
    r"\b(incident|outage|root cause|postmortem|post-mortem|sev-?\d|rollback|rolled back|"
    r"degradation|degraded|fail(s|ed|ing|ure)?|delay(ed)?|backlog)\b",
    re.IGNORECASE,
)
_CITATION = re.compile(r"\[(\d+)\]")
_DONT_KNOW = re.compile(
    r"\b(don't|do not|cannot|can't) (know|find|answer)\b|not in the (context|sources)", re.I
)


class AgentState(TypedDict, total=False):
    question: str
    top_k: int
    task: str  # "answer" or "incident"
    service: str
    severity: str
    route: str
    tools_used: list[str]
    hits: list[Hit]
    top_similarity: float
    answer: str
    cited: list[int]
    citations_valid: bool
    refused: bool
    generation_attempts: int
    prompt_tokens: int
    completion_tokens: int


def route_question(state: AgentState) -> AgentState:
    """Rule-based router: free and deterministic, and good enough for four routes."""
    question = state["question"]
    if state.get("task") == "incident" or _INCIDENT.search(question):
        route = "incident"
    elif _LOGS.search(question):
        route = "logs"
    elif _CODE.search(question):
        route = "code"
    else:
        route = "docs"
    return {"route": route}


async def retrieve(state: AgentState, config: RunnableConfig) -> AgentState:
    session = config["configurable"]["session"]
    tool_names = ROUTE_TOOLS[state["route"]]
    # Sequential on purpose: the tools share one AsyncSession, which does not allow
    # concurrent operations. Each search takes ~40 ms, so this costs little.
    results = [
        await TOOLS[name](session, state["question"], state["top_k"]) for name in tool_names
    ]
    return {
        "tools_used": tool_names,
        "hits": merge_with_coverage(results, state["top_k"]),
        "top_similarity": max(result.top_similarity for result in results),
    }


def merge_with_coverage(results: list[Retrieval], top_k: int) -> list[Hit]:
    """The general search ranking is the backbone; the specialised tool only guarantees
    that the source type the question is about appears in the top-k.

    Fusing the two rankings with RRF was measured to *lower* recall@5 (0.96 -> 0.93):
    every hit the specialised tool shares with the general search gets double credit,
    so e.g. "where is incident severity normalized?" filled the top-k with incident
    reports and pushed out the code file that answers it.
    """
    general = results[-1].hits[:top_k]
    if len(results) == 1:
        return general
    specialised = results[0].hits
    wanted_types = {hit.source_type for hit in specialised}
    if not specialised or any(hit.source_type in wanted_types for hit in general):
        return general
    return general[: top_k - 1] + [specialised[0]]


def has_enough_evidence(state: AgentState) -> str:
    """Guardrail: weak retrieval means we'd be asking the LLM to guess. Refuse instead."""
    if not state["hits"] or state["top_similarity"] < get_settings().min_score:
        return "refuse"
    return "generate"


def refuse(state: AgentState) -> AgentState:
    return {"answer": REFUSAL, "refused": True, "cited": [], "citations_valid": True}


async def generate(state: AgentState) -> AgentState:
    context = format_context(state["hits"])
    if state.get("task") == "incident":
        prompt = INCIDENT_TEMPLATE.format(
            context=context,
            question=state["question"],
            service=state.get("service", "unknown"),
            severity=state.get("severity", "unknown"),
        )
    else:
        prompt = ANSWER_TEMPLATE.format(context=context, question=state["question"])
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    attempts = state.get("generation_attempts", 0)
    if attempts:  # correction retry: show the model its bad answer and what was wrong
        messages += [
            {"role": "assistant", "content": state["answer"]},
            {"role": "user", "content": CITATION_CORRECTION.format(count=len(state["hits"]))},
        ]
    result = await asyncio.to_thread(chat, messages)  # the SDK client is synchronous
    return {
        "answer": result.text,
        "refused": False,
        "generation_attempts": attempts + 1,
        "prompt_tokens": state.get("prompt_tokens", 0) + result.prompt_tokens,
        "completion_tokens": state.get("completion_tokens", 0) + result.completion_tokens,
    }


def validate_citations(state: AgentState) -> AgentState:
    """Every [n] must point at a retrieved source, and there must be at least one."""
    cited = list(dict.fromkeys(int(n) for n in _CITATION.findall(state["answer"])))
    if len(_CITATION.sub("", state["answer"]).split()) < 3:
        # e.g. the model replied with just "[1]": a valid citation but no answer.
        return {"cited": [], "citations_valid": False}
    if not cited and _DONT_KNOW.search(state["answer"]):
        # The model declined because the sources don't answer the question. That is the
        # correct behaviour, not a citation failure, so don't spend a correction retry on it.
        return {"cited": [], "citations_valid": True, "refused": True}
    valid_numbers = range(1, len(state["hits"]) + 1)
    return {
        "cited": [n for n in cited if n in valid_numbers],
        "citations_valid": bool(cited) and all(n in valid_numbers for n in cited),
    }


def needs_correction(state: AgentState) -> str:
    if not state["citations_valid"] and state["generation_attempts"] < MAX_GENERATIONS:
        return "generate"
    return END


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("route_question", route_question)
    graph.add_node("retrieve", retrieve)
    graph.add_node("refuse", refuse)
    graph.add_node("generate", generate)
    graph.add_node("validate_citations", validate_citations)

    graph.add_edge(START, "route_question")
    graph.add_edge("route_question", "retrieve")
    graph.add_conditional_edges("retrieve", has_enough_evidence, ["refuse", "generate"])
    graph.add_edge("refuse", END)
    graph.add_edge("generate", "validate_citations")
    graph.add_conditional_edges("validate_citations", needs_correction, ["generate", END])
    return graph.compile()


agent = build_graph()


async def run_agent(session, question: str, top_k: int = 5, **extra) -> AgentState:
    return await agent.ainvoke(
        {"question": question, "top_k": top_k, **extra},
        config={"configurable": {"session": session}},
    )
