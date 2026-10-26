"""
Nœud 1 : Taxonomic Router Node (Cadrage sémantique & extraction du TacticalPlan).
"""

import time
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from src.agent.prompts import ROUTER_SYSTEM_PROMPT
from src.llm_factory import LLMFactory
from src.schemas.router import QueryType, TacticalPlan
from src.schemas.state import TacticalAgentState


def router_node(state: TacticalAgentState) -> Dict[str, Any]:
    """
    Analyse la question du coach et instancie un TacticalPlan Pydantic.
    """
    t_start = time.perf_counter()
    coach_query = state.get("coach_query", "")
    match_id = state.get("match_id", 3869685)

    llm = LLMFactory.get_fast_model(temperature=0.0)
    structured_llm = llm.with_structured_output(TacticalPlan)

    user_time_range = state.get("user_time_range")
    # Sequence ciblee = une phase choisie par l'utilisateur, sauf la vue « Global » (match entier)
    is_targeted_window = bool(user_time_range) and not state.get("is_global_view")
    
    from src.data_mining.match_miner import MatchMiner
    try:
        meta = MatchMiner().get_match_metadata(match_id)
        match_info = f"Match en cours : {meta['home_team']} vs {meta['away_team']} ({meta['match_date']})\nÉquipes autorisées pour 'target_teams' : ['{meta['home_team']}', '{meta['away_team']}']"
    except Exception:
        match_info = f"Match ID : {match_id}"

    prompt_content = f"Question de l'entraîneur : '{coach_query}'\n{match_info}"
    if user_time_range:
        prompt_content += f"\nTranche temporelle sélectionnée par le coach : minutes {user_time_range[0]} à {user_time_range[1]}"

    messages = [
        SystemMessage(content=ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=prompt_content),
    ]

    # Détection par mots-clés des joueurs mentionnés dans la question pour garantir leur inclusion
    def _detect_players(query: str) -> list[str]:
        q = query.lower()
        found = []
        mapping = {
            "messi": "Lionel Messi",
            "mbapp": "Kylian Mbappé",
            "griezmann": "Antoine Griezmann",
            "di maria": "Ángel Di María",
            "di maría": "Ángel Di María",
            "alvarez": "Julián Álvarez",
            "álvarez": "Julián Álvarez",
            "giroud": "Olivier Giroud",
            "demb": "Ousmane Dembélé",
            "kolo muani": "Randal Kolo Muani",
            "thuram": "Marcus Thuram",
            "coman": "Kingsley Coman",
            "camavinga": "Eduardo Camavinga",
            "rabiot": "Adrien Rabiot",
            "tchouameni": "Aurélien Tchouaméni",
            "tchouaméni": "Aurélien Tchouaméni",
            "mac allister": "Alexis Mac Allister",
            "de paul": "Rodrigo De Paul",
            "martinez": "Emiliano Martínez",
            "martínez": "Emiliano Martínez",
            "modric": "Luka Modrić",
            "modrić": "Luka Modrić",
            "ziyech": "Hakim Ziyech",
            "hakimi": "Achraf Hakimi",
        }
        for k, v in mapping.items():
            if k in q and v not in found:
                found.append(v)
        return found

    detected_players = _detect_players(coach_query)

    try:
        plan: TacticalPlan = structured_llm.invoke(messages)
        if detected_players:
            existing = plan.target_players or []
            for dp in detected_players:
                if dp not in existing:
                    existing.insert(0, dp)
            plan.target_players = existing
        # Si le coach a sélectionné une séquence précise (ex: 0-40, 70-85), garantir le ciblage
        if is_targeted_window:
            plan.time_windows = [user_time_range]
            plan.query_type = QueryType.DIAGNOSTIC_SEQUENCE
    except Exception:
        # Fallback de secours robuste et dynamique
        fallback_teams = [meta.get("home_team", "Home"), meta.get("away_team", "Away")] if "home_team" in meta else ["Argentina", "France"]
        fallback_players = detected_players if detected_players else None
        if is_targeted_window:
            plan = TacticalPlan(
                query_type=QueryType.DIAGNOSTIC_SEQUENCE,
                game_phases=["Organisation Offensive", "Transition Défensive"],
                time_windows=[user_time_range],
                target_teams=fallback_teams,
                target_players=fallback_players,
                spatial_zones=["left_half_space", "zone_14"],
                key_metrics_needed=["turnovers_under_pressure", "xg"],
                theoretical_topics=["Rest-Defense", "Half-Spaces"],
                reasoning_summary=f"Analyse chirurgicale de la séquence {user_time_range[0]}-{user_time_range[1]} min ({fallback_teams[0]} vs {fallback_teams[1]}).",
            )
        else:
            from src.data_mining.phase_generator import MatchPhaseGenerator
            try:
                phases = MatchPhaseGenerator().get_or_create_phases(match_id)
                windows = [(p.minute_start, p.minute_end) for p in phases]
            except Exception:
                windows = [(0, 40), (40, 70), (70, 85), (85, 90), (90, 120)]
            plan = TacticalPlan(
                query_type=QueryType.MACRO_MATCH_FLOW,
                game_phases=["Organisation Offensive", "Transition Défensive"],
                time_windows=windows,
                target_teams=fallback_teams,
                target_players=fallback_players,
                spatial_zones=["left_half_space", "zone_14"],
                key_metrics_needed=["turnovers_under_pressure", "xg"],
                theoretical_topics=["Rest-Defense", "Half-Spaces", "Passing Networks"],
                reasoning_summary=f"Analyse globale et cadrage par défaut ({fallback_teams[0]} vs {fallback_teams[1]}).",
            )

    t_latency = round((time.perf_counter() - t_start) * 1000, 1)
    telemetry = state.get("execution_telemetry") or {}
    telemetry["router_latency_ms"] = t_latency

    return {
        "tactical_plan": plan,
        "execution_telemetry": telemetry,
    }
