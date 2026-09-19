"""
Orchestration du graphe d'agents LangGraph (TacticalAgentGraph).
"""

from typing import Any, Dict, Literal, Optional, Tuple
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.agent.nodes.critic_node import critic_node
from src.agent.nodes.deep_rag_node import deep_rag_node
from src.agent.nodes.router_node import router_node
from src.agent.nodes.sql_miner_node import sql_miner_node
from src.agent.nodes.synthesizer_node import synthesizer_node
from src.schemas.state import TacticalAgentState


def should_continue_after_critic(
    state: TacticalAgentState,
) -> Literal["synthesizer", END]:
    """
    Règle de routage conditionnel :
    - Si le Critic renvoie FAIL et qu'on a moins de 2 itérations -> Boucle de correction vers synthesizer
    - Sinon -> Fin d'exécution (END)
    """
    verdict = state.get("critic_verdict")
    iteration = state.get("iteration_count", 0)

    if verdict and verdict.verdict == "FAIL" and iteration < 2:
        return "synthesizer"
    return END


_DEFAULT_CHECKPOINTER = MemorySaver()


def create_tactical_graph(checkpointer: Any = None) -> Any:
    """
    Construit et compile le StateGraph LangGraph avec enchaînement
    séquentiel Data-Informed RAG et auto-correction.
    """
    workflow = StateGraph(TacticalAgentState)

    # 1. Déclaration des Nœuds
    workflow.add_node("router", router_node)
    workflow.add_node("sql_miner", sql_miner_node)
    workflow.add_node("deep_rag", deep_rag_node)
    workflow.add_node("synthesizer", synthesizer_node)
    workflow.add_node("critic", critic_node)

    # 2. Déclaration des Arêtes (Edges)
    workflow.set_entry_point("router")
    workflow.add_edge("router", "sql_miner")
    workflow.add_edge("sql_miner", "deep_rag")      # Séquence Data-Informed
    workflow.add_edge("deep_rag", "synthesizer")
    workflow.add_edge("synthesizer", "critic")

    # 3. Arête Conditionnelle d'Auto-Correction
    workflow.add_conditional_edges(
        "critic",
        should_continue_after_critic,
        {
            "synthesizer": "synthesizer",
            END: END,
        },
    )

    # 4. Compilation avec mémoire d'état (Checkpointer)
    memory = checkpointer if checkpointer is not None else _DEFAULT_CHECKPOINTER
    return workflow.compile(checkpointer=memory)


def run_tactical_analysis(
    coach_query: str,
    match_id: int = 3869685,
    thread_id: str = "default_session",
    user_time_range: Optional[Tuple[int, int]] = None,
    analyst_modifications: str | None = None,
    checkpointer: Any = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Fonction utilitaire synchrone pour exécuter une analyse tactique complète.
    """
    graph = create_tactical_graph(checkpointer=checkpointer)
    initial_state: TacticalAgentState = {
        "coach_query": coach_query,
        "match_id": match_id,
        "thread_id": thread_id,
        "user_time_range": user_time_range,
        "tactical_plan": None,
        "match_facts": None,
        "retrieved_chunks": None,
        "draft_report": None,
        "critic_verdict": None,
        "critic_feedback": None,
        "iteration_count": 0,
        "is_human_approved": False,
        "analyst_modifications": analyst_modifications,
        "final_report": None,
        "execution_telemetry": {},
    }

    config = {"configurable": {"thread_id": thread_id}}
    result_state = graph.invoke(initial_state, config=config)

    # Consolidation de fin de pipeline
    if not result_state.get("final_report"):
        result_state["final_report"] = result_state.get("draft_report", "")

    telemetry = result_state.get("execution_telemetry") or {}
    total_latency = (
        telemetry.get("router_latency_ms", 0)
        + telemetry.get("sql_miner_latency_ms", 0)
        + telemetry.get("deep_rag_latency_ms", 0)
        + telemetry.get("synthesizer_latency_ms", 0)
        + telemetry.get("critic_latency_ms", 0)
    )
    telemetry["total_pipeline_latency_ms"] = round(total_latency, 1)
    result_state["execution_telemetry"] = telemetry

    return result_state
