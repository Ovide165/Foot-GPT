"""
État global du graphe LangGraph (TacticalAgentState).
"""

from typing import Annotated, Any, Dict, List, Optional, Tuple
from typing_extensions import TypedDict

from src.schemas.router import TacticalPlan
from src.schemas.miner import MatchFacts
from src.schemas.critic import VerificationVerdict


def merge_telemetry(
    old: Optional[Dict[str, Any]], new: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Reducer pour fusionner proprement la télémétrie produite par les différents nœuds."""
    merged = dict(old or {})
    if new:
        merged.update(new)
    return merged


class TacticalAgentState(TypedDict):
    """
    Conteneur d'état centralisé pour l'orchestration LangGraph.
    Chaque nœud lit et met à jour des sections spécifiques de cet état.
    """
    # 1. Entrées de session
    coach_query: str
    match_id: int
    thread_id: str
    user_time_range: Optional[Tuple[int, int]]
    
    # 2. Sortie Nœud 1 (Router)
    tactical_plan: Optional[TacticalPlan]
    
    # 3. Sortie Nœud 2A (SQL Miner)
    match_facts: Optional[MatchFacts]
    
    # 4. Sortie Nœud 2B (Hybrid RAG)
    retrieved_chunks: Optional[List[Dict[str, Any]]]
    
    # 5. Sortie Nœud 3 (Synthesizer)
    draft_report: Optional[str]
    
    # 6. Sortie Nœud 4 (Critic Audit)
    critic_verdict: Optional[VerificationVerdict]
    critic_feedback: Optional[str]
    iteration_count: int
    
    # 7. Sortie Nœud 5 (Human-in-the-loop)
    is_human_approved: bool
    analyst_modifications: Optional[str]
    
    # 8. Sortie Finale
    final_report: Optional[str]
    execution_telemetry: Annotated[Optional[Dict[str, Any]], merge_telemetry]
