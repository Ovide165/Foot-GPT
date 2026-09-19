"""
Schémas Pydantic pour le Nœud 2A (SQL Data Miner).
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MatchPhaseMetric(BaseModel):
    """Métriques statistiques agrégées sur une tranche temporelle donnée."""
    phase_label: str = Field(description="Libellé descriptif (ex: '00-40 min (Domination Argentine)')")
    minute_start: int = Field(ge=0, description="Minute de début de la séquence")
    minute_end: int = Field(ge=0, description="Minute de fin de la séquence")
    team: str = Field(description="Nom de l'équipe")
    total_events: int = Field(default=0, description="Nombre total d'événements")
    on_ball_events: int = Field(default=0, description="Événements avec ballon (Passes, Conduites, Tirs, Dribbles)")
    defensive_events: int = Field(default=0, description="Événements défensifs (Pressions, Tacles, Interceptions, Dégagements, Fautes)")
    field_tilt_pct: float = Field(default=0.0, description="Field Tilt (%) : % de passes réussies dans le dernier tiers par rapport au total du match sur cette phase")
    passes_attempted: int = Field(default=0, description="Total des passes tentées")
    passes_completed: int = Field(default=0, description="Total des passes réussies")
    pass_accuracy_pct: float = Field(default=0.0, description="Taux de complétion des passes (%)")
    passes_final_third: int = Field(default=0, description="Passes dans les 35 derniers mètres (x >= 80)")
    passes_zone_14: int = Field(default=0, description="Passes dans la Zone 14 (x in [75, 95], y in [30, 50])")
    shots_count: int = Field(default=0, description="Nombre de tirs")
    shots_on_target: int = Field(default=0, description="Nombre de tirs cadrés")
    goals_count: int = Field(default=0, description="Nombre de buts inscrits")
    xg_sum: float = Field(default=0.0, description="Somme des Expected Goals (StatsBomb xG)")
    turnovers_under_pressure: int = Field(default=0, description="Pertes de balle subies sous pression")
    high_recoveries_count: int = Field(default=0, description="Ballons récupérés dans le camp adverse (x >= 60)")
    actions_under_pressure_total: int = Field(default=0, description="Total d'actions effectuées sous pression")


class PlayerHighlight(BaseModel):
    """Statistiques individualisées sur un joueur clé."""
    player_id: int
    player_name: str
    team_name: str
    minutes_played: int
    goals: int = 0
    shots: int = 0
    xg_total: float = 0.0
    passes_completed: int = 0
    passes_attempted: int = 0
    pass_accuracy_pct: float = 0.0
    duels_won: int = 0
    turnovers_under_pressure: int = 0
    key_events_timeline: List[str] = Field(default_factory=list)


class MatchFacts(BaseModel):
    """
    Source de vérité mathématique indiscutable produite par le moteur SQL.
    Transmise directement au Synthesizer et au Critic.
    """
    match_id: int
    match_name: str
    match_date: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    phases_data: List[MatchPhaseMetric] = Field(
        default_factory=list,
        description="Données chiffrées par tranche de jeu analysée"
    )
    baseline_match_averages: Dict[str, float] = Field(
        default_factory=dict,
        description="Moyennes de référence par 15 minutes sur l'ensemble du match"
    )
    significant_deltas: Dict[str, str] = Field(
        default_factory=dict,
        description="Écarts statistiques relatifs remarquables (ex: '+328% de pertes sous pression')"
    )
    player_highlights: Optional[Dict[str, PlayerHighlight]] = Field(
        default=None,
        description="Statistiques par joueur cible si applicable"
    )
    substitutions_timeline: List[str] = Field(
        default_factory=list,
        description="Chronologie des remplacements effectués (ex: '[41\'] France: Olivier Giroud (OUT) -> Marcus Thuram (IN)')"
    )
    raw_query_summary: str = Field(
        default="",
        description="Résumé textuel des filtres et requêtes SQL exécutés"
    )
