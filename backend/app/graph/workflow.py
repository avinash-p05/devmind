import re

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.state import AgentState
from app.graph.tools import code_search_tool, hybrid_retrieval_tool
from app.llm import generate_grounded_answer
from app.schemas import ChatResponse, Citation, IncidentAnalysis, IncidentAnalyzeRequest

CODE_QUERY = re.compile(
    r"\b(where|which|how|function|class|method|implemented|defined|file|source|repository)\b|[/\\]"
)
INCIDENT_QUERY = re.compile(
    r"\b(incident|failure|failed|outage|root cause|stack trace|error|timeout|rollback)\b",
    re.IGNORECASE,
)
LOG_QUERY = re.compile(r"\b(log|logs|trace|request id|exception)\b", re.IGNORECASE)


def _analyze_query(state: AgentState) -> AgentState:
    query = state["query"]
    if CODE_QUERY.search(query):
        state["route"] = "code_search"
    elif INCIDENT_QUERY.search(query):
        state["route"] = "incident_analysis"
    elif LOG_QUERY.search(query):
        state["route"] = "log_search"
    else:
        state["route"] = "hybrid_retrieval"
    state["retrieval_attempts"] = 0
    return state


def _retrieve(session: AsyncSession):
    async def retrieve(state: AgentState) -> AgentState:
        state["retrieval_attempts"] = state.get("retrieval_attempts", 0) + 1
        if state["route"] == "code_search":
            state["evidence"] = await code_search_tool(session, state["query"], state["top_k"])
        else:
            state["evidence"] = await hybrid_retrieval_tool(
                session,
                state["query"],
                state["top_k"] * state["retrieval_attempts"],
            )
        return state

    return retrieve


def _should_retry(state: AgentState) -> str:
    if not state.get("evidence") and state.get("retrieval_attempts", 0) < 2:
        return "retrieve_more"
    return "generate_answer"


def _generate_answer(state: AgentState) -> AgentState:
    evidence = state.get("evidence", [])
    state["evidence_sufficient"] = bool(evidence)
    if not evidence:
        state["answer"] = (
            "I could not find supporting evidence in the indexed workspace. "
            "Add the relevant source or refine the question."
        )
        state["citations"] = []
        return state

    lead = evidence[0]
    state["answer"] = (
        f"The strongest indexed evidence for this question is in {lead.document_name}. "
        f"It indicates: {lead.content}"
    )
    state["citations"] = [
        Citation(
            chunk_id=result.chunk_id,
            document_name=result.document_name,
            score=result.score,
            metadata=result.metadata,
        )
        for result in evidence[:3]
    ]
    return state


def _validate_citations(state: AgentState) -> AgentState:
    evidence_ids = {result.chunk_id for result in state.get("evidence", [])}
    state["citations"] = [
        citation for citation in state.get("citations", []) if citation.chunk_id in evidence_ids
    ]
    if state.get("evidence_sufficient") and not state["citations"]:
        state["evidence_sufficient"] = False
    return state


async def _generate_answer_node(state: AgentState) -> AgentState:
    answer, tokens, metadata = await generate_grounded_answer(
        state["query"], state.get("evidence", [])
    )
    state["answer"] = answer
    state["estimated_tokens"] = tokens
    state["llm_metadata"] = metadata
    state["evidence_sufficient"] = bool(state.get("evidence"))
    state["citations"] = [
        Citation(
            chunk_id=result.chunk_id,
            document_name=result.document_name,
            score=result.score,
            metadata=result.metadata,
        )
        for result in state.get("evidence", [])[:3]
    ]
    return state


def build_agent_graph(session: AsyncSession):
    graph = StateGraph(AgentState)
    graph.add_node("analyze_query", _analyze_query)
    graph.add_node("retrieve", _retrieve(session))
    graph.add_node("retrieve_more", _retrieve(session))
    graph.add_node("generate_answer", _generate_answer_node)
    graph.add_node("validate_citations", _validate_citations)
    graph.add_edge(START, "analyze_query")
    graph.add_edge("analyze_query", "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        _should_retry,
        {"retrieve_more": "retrieve_more", "generate_answer": "generate_answer"},
    )
    graph.add_edge("retrieve_more", "generate_answer")
    graph.add_edge("generate_answer", "validate_citations")
    graph.add_edge("validate_citations", END)
    return graph.compile()


async def answer_question(session: AsyncSession, query: str, top_k: int) -> ChatResponse:
    result = await build_agent_graph(session).ainvoke({"query": query, "top_k": top_k})
    return ChatResponse(
        query=query,
        answer=result["answer"],
        route=result["route"],
        confidence="medium" if result["evidence_sufficient"] else "low",
        evidence_sufficient=result["evidence_sufficient"],
        citations=result["citations"],
        llm_provider=result.get("llm_metadata", {}).get("provider"),
        llm_model=result.get("llm_metadata", {}).get("model"),
        estimated_tokens=result.get("estimated_tokens"),
    )


async def analyze_incident(
    session: AsyncSession, request: IncidentAnalyzeRequest
) -> IncidentAnalysis:
    query = f"{request.service} {request.query}"
    result = await build_agent_graph(session).ainvoke({"query": query, "top_k": request.top_k})
    citations = result["citations"]
    if citations:
        root_cause = result["evidence"][0].content
        affected_component = request.service
        next_steps = [
            f"Inspect the latest {request.service} deployment and configuration changes.",
            "Compare the cited evidence with application and infrastructure metrics.",
            "Reproduce the failure in a controlled environment before rollout.",
        ]
        unresolved = []
    else:
        root_cause = "No supporting evidence was found for a reliable root-cause hypothesis."
        affected_component = request.service
        next_steps = [
            f"Index logs, traces, and deployment details for {request.service}.",
            "Refine the incident window and failure symptoms.",
        ]
        unresolved = ["Which deployment, log window, and component should be correlated?"]
    return IncidentAnalysis(
        service=request.service,
        severity=request.severity,
        root_cause_hypothesis=root_cause,
        evidence=citations,
        affected_component=affected_component,
        recommended_next_steps=next_steps,
        confidence="medium" if citations else "low",
        route=result["route"],
        unresolved_questions=unresolved,
    )