"""
Nœud 2A : SQL Miner Node (Extraction déterministe des faits StatsBomb).
"""

import time
from typing import Any, Dict

from src.data_mining.match_miner import MatchMiner
from src.schemas.miner import MatchFacts
from src.schemas.router import TacticalPlan
from src.schemas.state import TacticalAgentState


def sql_miner_node(state: TacticalAgentState) -> Dict[str, Any]:
    """
    Exécute les calculs SQL déterministes sur SQLite en fonction du TacticalPlan.
    """
    t_start = time.perf_counter()
    match_id = state.get("match_id", 3869685)
    plan = state.get("tactical_plan")

    if not plan:
        # Initialisation par défaut si omis
        from src.schemas.router import QueryType
        from src.data_mining.phase_generator import MatchPhaseGenerator
        try:
            phases = MatchPhaseGenerator().get_or_create_phases(match_id)
            windows = [(p.minute_start, p.minute_end) for p in phases]
        except Exception:
            windows = [(0, 40), (40, 70), (70, 85), (85, 90), (90, 120)]
        plan = TacticalPlan(
            query_type=QueryType.MACRO_MATCH_FLOW,
            time_windows=windows,
            target_teams=["Argentina", "France"],
        )

    miner = MatchMiner()
    match_facts: MatchFacts = miner.build_match_facts(match_id, plan)

    t_latency = round((time.perf_counter() - t_start) * 1000, 1)
    telemetry = state.get("execution_telemetry") or {}
    telemetry["sql_miner_latency_ms"] = t_latency

    return {
        "match_facts": match_facts,
        "execution_telemetry": telemetry,
    }
