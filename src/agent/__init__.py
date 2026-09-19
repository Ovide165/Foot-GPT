"""
Package agent : Cœur d'orchestration LangGraph de foot-GPT.
"""

from src.agent.graph import create_tactical_graph, run_tactical_analysis
from src.agent.prompts import (
    CRITIC_SYSTEM_PROMPT,
    FEW_SHOT_GOLD_STANDARD,
    ROUTER_SYSTEM_PROMPT,
    SYNTHESIZER_SYSTEM_PROMPT,
)

__all__ = [
    "create_tactical_graph",
    "run_tactical_analysis",
    "ROUTER_SYSTEM_PROMPT",
    "SYNTHESIZER_SYSTEM_PROMPT",
    "CRITIC_SYSTEM_PROMPT",
    "FEW_SHOT_GOLD_STANDARD",
]
