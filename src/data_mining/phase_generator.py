"""
Générateur dynamique de phases de jeu fondé sur la timeline factuelle d'un match (Option B Hybride).
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.config import DB_PATH
from src.data_mining.db_connection import ReadOnlyDBConnection
from src.llm_factory import LLMFactory
from src.schemas.phases import MatchPhases, PhaseDefinition


class MatchPhaseGenerator:
    """
    Génère et met en cache des découpages tactiques dynamiques pour les matchs.
    Utilise une timeline d'événements clés et un LLM pour décider des phases.
    """

    def __init__(self, cache_path: str = "data/cached_phases.json"):
        self.cache_path = Path(cache_path)
        self.db = ReadOnlyDBConnection()

    def _get_match_timeline_data(self, match_id: int) -> Tuple[Dict[str, Any], str]:
        """Récupère les événements chronologiques bruts depuis SQLite et construit un résumé textuel."""
        # 1. Métadonnées du match
        meta_rows = self.db.execute_safe_query(
            "SELECT match_id, home_team, away_team, home_score, away_score FROM matches WHERE match_id = ?",
            (match_id,),
        )
        if not meta_rows:
            raise ValueError(f"Match {match_id} introuvable.")
        meta = dict(meta_rows[0])
        home, away = meta["home_team"], meta["away_team"]

        # 2. Buts
        goals_rows = self.db.execute_safe_query(
            "SELECT minute, second, team, player FROM events WHERE match_id = ? AND type = 'Shot' AND raw_data LIKE '%\"shot_outcome\": \"Goal\"%' ORDER BY minute, second",
            (match_id,),
        )
        goals = [dict(g) for g in goals_rows]

        # 3. Remplacements
        subs_rows = self.db.execute_safe_query(
            "SELECT minute, team, player, json_extract(raw_data, '$.substitution_replacement') as replacement FROM events WHERE match_id = ? AND type = 'Substitution' ORDER BY minute",
            (match_id,),
        )
        subs = [dict(s) for s in subs_rows]

        # 4. Tirs et xG par tranches de 10 minutes
        xg_rows = self.db.execute_safe_query(
            """
            SELECT 
                (minute / 10) * 10 as minute_bin,
                team,
                COUNT(*) as shots,
                SUM(CAST(json_extract(raw_data, '$.shot_statsbomb_xg') AS REAL)) as xg
            FROM events
            WHERE match_id = ? AND type = 'Shot'
            GROUP BY minute_bin, team
            ORDER BY minute_bin;
            """,
            (match_id,),
        )
        xg_bins = [dict(x) for x in xg_rows]

        # 5. Minute maximum du match
        max_min_row = self.db.execute_safe_query(
            "SELECT MAX(minute) as max_min FROM events WHERE match_id = ?",
            (match_id,),
        )
        max_minute = int(max_min_row[0]["max_min"] or 90) if max_min_row else 90

        # Construction de la timeline textuelle pour le LLM
        timeline = f"MATCH: {home} {meta['home_score']} - {meta['away_score']} {away} (Max minute: {max_minute})\n\n"
        timeline += "--- GOALS ---\n"
        for g in goals:
            timeline += f"- Min {g['minute']}:{g['second']:02d} | Goal for {g['team']} by {g['player']}\n"
        if not goals:
            timeline += "- No goals scored.\n"

        timeline += "\n--- SUBSTITUTIONS ---\n"
        for s in subs:
            timeline += f"- Min {s['minute']} | {s['team']}: {s['player']} OUT -> {s['replacement']} IN\n"
        if not subs:
            timeline += "- No substitutions recorded.\n"

        timeline += "\n--- xG AND SHOTS VOLUME BY 10-MINUTE BINS ---\n"
        bins_data: Dict[int, Dict[str, str]] = {}
        for x in xg_bins:
            m_bin = int(x["minute_bin"])
            t_name = str(x["team"])
            if m_bin not in bins_data:
                bins_data[m_bin] = {}
            bins_data[m_bin][t_name] = f"{x['shots']} shots, {float(x['xg'] or 0.0):.2f} xG"

        for m_bin in sorted(bins_data.keys()):
            home_bin = bins_data[m_bin].get(home, "0 shots, 0.00 xG")
            away_bin = bins_data[m_bin].get(away, "0 shots, 0.00 xG")
            timeline += f"- Min {m_bin:02d}-{m_bin+10:02d} | {home}: {home_bin} vs {away}: {away_bin}\n"

        return meta, timeline

    def _validate_and_clean_phases(self, phases: List[PhaseDefinition], max_minute: int) -> List[PhaseDefinition]:
        """Trie, comble les trous, élimine les chevauchements et valide les bornes temporelles."""
        if not phases:
            # Fallback par défaut si vide
            return [
                PhaseDefinition(minute_start=0, minute_end=45, name="First Half", description="First half of the match"),
                PhaseDefinition(minute_start=45, minute_end=max_minute, name="Second Half", description="Second half of the match")
            ]

        # Tri par minute de début
        phases = sorted(phases, key=lambda p: p.minute_start)

        cleaned: List[PhaseDefinition] = []
        current_min = 0

        for i, p in enumerate(phases):
            start = current_min
            end = p.minute_end
            if end <= start:
                # Évite les tranches invalides
                continue

            # Si c'est la dernière phase, on s'assure qu'elle va jusqu'à max_minute
            if i == len(phases) - 1:
                end = max(max_minute, end)

            cleaned.append(
                PhaseDefinition(
                    minute_start=start,
                    minute_end=end,
                    name=p.name,
                    description=p.description,
                )
            )
            current_min = end

        # Si la dernière phase ne couvre pas la fin du match, on en rajoute une ou on prolonge la dernière
        if cleaned and cleaned[-1].minute_end < max_minute:
            cleaned[-1].minute_end = max_minute

        return cleaned

    def get_or_create_phases(self, match_id: int) -> List[PhaseDefinition]:
        """
        Retourne la liste des phases du match.
        Lit depuis le cache JSON si disponible, sinon interroge le LLM et met en cache.
        """
        # 1. Tentative de lecture du cache
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                if str(match_id) in cache:
                    return [PhaseDefinition(**p) for p in cache[str(match_id)]]
            except Exception:
                pass  # En cas d'erreur de lecture du cache, on regénère

        # 2. Cache Miss : Récupération de la timeline
        meta, timeline_str = self._get_match_timeline_data(match_id)
        max_minute = 120 if match_id == 3869685 else 90  # Prolongations ou non

        # On interroge SQLite de nouveau pour valider la minute max réelle
        max_min_row = self.db.execute_safe_query(
            "SELECT MAX(minute) as max_min FROM events WHERE match_id = ?",
            (match_id,),
        )
        if max_min_row and max_min_row[0]["max_min"] is not None:
            max_minute = int(max_min_row[0]["max_min"])

        # 3. Appel du LLM pour segmenter le match
        system_prompt = (
            "You are an expert tactical analyst. Your task is to segment a football match into 4 to 5 chronological phases "
            "representing major tactical shifts, based on a factual timeline of goals, substitutions, and xG bins.\n"
            "Guidelines:\n"
            "1. The first phase MUST start at minute 0.\n"
            "2. Phases must be chronological and contiguous (the end minute of a phase is the start minute of the next).\n"
            "3. The final phase MUST end at the max minute of the match.\n"
            "4. Each phase must be justified tactically (ex: 'France switches to 4-2-4 after double sub' or 'High intensity pressing by Argentina').\n"
            "5. Do NOT use emojis."
        )

        llm = LLMFactory.get_fast_model(temperature=0.0)
        structured_llm = llm.with_structured_output(MatchPhases)

        from langchain_core.messages import HumanMessage, SystemMessage
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Timeline for Match {match_id}:\n{timeline_str}"),
        ]

        try:
            res: MatchPhases = structured_llm.invoke(messages)
            raw_phases = res.phases
        except Exception:
            # Fallback si l'appel LLM échoue
            raw_phases = [
                PhaseDefinition(minute_start=0, minute_end=40, name="Initial Phase", description="Initial tactical setup"),
                PhaseDefinition(minute_start=40, minute_end=70, name="Second Phase", description="Mid-game adjustments"),
                PhaseDefinition(minute_start=70, minute_end=90, name="Final Phase", description="Late-game dynamics"),
            ]

        # 4. Validation et nettoyage
        cleaned_phases = self._validate_and_clean_phases(raw_phases, max_minute)

        # 5. Enregistrement dans le cache JSON
        cache_data = {}
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
            except Exception:
                pass

        cache_data[str(match_id)] = [p.model_dump() for p in cleaned_phases]

        # Création du répertoire parent si nécessaire
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)

        return cleaned_phases
