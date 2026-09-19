import base64
import os
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
from PIL import Image
import streamlit as st

import importlib
import src.cache.semantic_cache
importlib.reload(src.cache.semantic_cache)
from src.agent.graph import run_tactical_analysis
from src.cache.semantic_cache import GLOBAL_SEMANTIC_CACHE
from src.data_mining.db_connection import ReadOnlyDBConnection
from src.data_mining.match_miner import MatchMiner
from src.data_mining.phase_generator import MatchPhaseGenerator
from src.security.guardrails import SecurityGuardrails
import src.ui.components.admin_dashboard
importlib.reload(src.ui.components.admin_dashboard)
from src.ui.components.admin_dashboard import (
    render_knowledge_base_explorer,
    render_model_benchmark_panel,
    render_sql_query_console,
    render_telemetry_metrics,
)
from src.ui.components.report_renderer import (
    render_citations_panel,
    render_critical_events_timeline,
    render_facts_table,
    render_structured_report,
)

# Chargement des variables d'environnement
load_dotenv()

# Chargement du favicon officiel foot-GPT
favicon_path = Path(__file__).parent / "src" / "ui" / "assets" / "favicon.png"
if not favicon_path.exists():
    favicon_path = Path(__file__).parent / "src" / "ui" / "assets" / "foot_gpt_icon_badge.jpg"

page_icon_img = Image.open(favicon_path) if favicon_path.exists() else "⚽"

# Configuration de la page
st.set_page_config(
    page_title="foot-GPT | Pro Analytics",
    page_icon=page_icon_img,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Chargement du style CSS épuré
css_path = Path(__file__).parent / "src" / "ui" / "styles.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def get_asset_base64(filename: str) -> str:
    """Encode une image locale du dossier assets en data URI base64."""
    path = Path(__file__).parent / "src" / "ui" / "assets" / filename
    if path.exists():
        data = path.read_bytes()
        return f"data:image/jpeg;base64,{base64.b64encode(data).decode('utf-8')}"
    return ""


MATCH_METADATA = {
    3869685: {
        "stage": "WORLD CUP 2022 · FINAL",
        "stadium": "Lusail Iconic Stadium, Qatar",
        "home_code": "ARG",
        "away_code": "FRA",
        "score_detail": "3 - 3 (4 - 2 pens)",
    },
    3869684: {
        "stage": "WORLD CUP 2022 · 3RD PLACE",
        "stadium": "Khalifa International Stadium, Qatar",
        "home_code": "CRO",
        "away_code": "MAR",
        "score_detail": "2 - 1 (FT)",
    },
    3869552: {
        "stage": "WORLD CUP 2022 · SEMI-FINAL",
        "stadium": "Al Bayt Stadium, Qatar",
        "home_code": "FRA",
        "away_code": "MAR",
        "score_detail": "2 - 0 (FT)",
    },
    3857276: {
        "stage": "WORLD CUP 2022 · GROUP STAGE",
        "stadium": "Al Thumama Stadium, Qatar",
        "home_code": "CAN",
        "away_code": "MAR",
        "score_detail": "1 - 2 (FT)",
    },
}


@st.cache_data
def get_available_matches():
    """Charge dynamiquement uniquement les matchs disposant d'événements détaillés en base."""
    try:
        db = ReadOnlyDBConnection()
        sql = """
        SELECT m.match_id, m.match_date, m.home_team, m.away_team, m.home_score, m.away_score
        FROM matches m
        WHERE m.match_id IN (SELECT DISTINCT match_id FROM events)
        ORDER BY m.match_date DESC;
        """
        rows = db.execute_safe_query(sql)
        if rows:
            return [dict(r) for r in rows]
    except Exception:
        pass
    return [{"match_id": 3869685, "home_team": "Argentina", "away_team": "France", "home_score": 3, "away_score": 3, "match_date": "2022-12-18"}]


matches = get_available_matches()
match_options = {
    f"{m['home_team']} {m['home_score']} - {m['away_score']} {m['away_team']} ({m['match_date']})": m
    for m in matches
}

# Initialisation du State de session
if "selected_match_id" not in st.session_state:
    st.session_state.selected_match_id = None
if "current_result" not in st.session_state:
    st.session_state.current_result = None
if "active_phase_id" not in st.session_state:
    st.session_state.active_phase_id = "global"
if "active_time_range" not in st.session_state:
    st.session_state.active_time_range = (0, 120)

# --- BARRE SUPÉRIEURE ÉPURÉE (LOGO + PICKLIST DE MATCH + BOUTON RESET CACHE) ---
col_logo, col_match, col_clear = st.columns([1.5, 1.9, 0.6], gap="small")

with col_logo:
    icon_b64 = get_asset_base64("foot_gpt_icon_badge.jpg")
    img_tag = f'<img src="{icon_b64}" class="app-logo-img" />' if icon_b64 else ''
    st.markdown(
        f"""
        <div class="app-brand-wrapper">
            {img_tag}
            <div class="app-brand-text">
                <div class="app-brand-title-row">
                    <span class="hud-title">foot-GPT</span>
                    <span class="brand-pill-emerald">PRO TACTICS</span>
                </div>
                <div class="app-brand-subtitle">Tactical Intelligence Suite</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

match_list = list(match_options.keys())
default_idx = None
if "current_selected_label" in st.session_state and st.session_state.current_selected_label in match_list:
    default_idx = match_list.index(st.session_state.current_selected_label)

with col_match:
    st.markdown('<div class="match-selector-wrapper">', unsafe_allow_html=True)
    selected_match_label = st.selectbox(
        "Match to Analyze (FIFA World Cup 2022):",
        options=match_list,
        index=default_idx,
        placeholder="Select a fixture to analyze...",
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)
    if selected_match_label:
        st.session_state.current_selected_label = selected_match_label
    else:
        st.session_state.current_selected_label = None
        st.session_state.selected_match_id = None

with col_clear:
    if st.button("Clear Cache", key="btn_clear_cache_top", use_container_width=True):
        GLOBAL_SEMANTIC_CACHE.clear()
        st.session_state.current_result = None
        st.session_state.current_selected_label = None
        st.session_state.selected_match_id = None
        st.toast("Application cache purged!")
        st.rerun()

tab_coach, tab_admin = st.tabs(["Tactical Analysis", "Supervision & Benchmark"])

# ==============================================================================
# TAB 1 : TACTICAL ANALYSIS (COACH / ANALYST WORKSPACE)
# ==============================================================================
with tab_coach:
    if not selected_match_label or selected_match_label not in match_options:
        # High-Impact Match Selection Portal with Generated Tactical Hero Banner
        hero_b64 = get_asset_base64("football_tactical_hero.jpg")
        hero_img_html = f'<img src="{hero_b64}" class="hero-tactical-img" alt="Tactical Intelligence Board" />' if hero_b64 else ''

        st.markdown(
            f"""
            <div class="hero-portal-container">
                <div class="hero-portal-grid">
                    <div class="hero-portal-left">
                        {hero_img_html}
                        <div class="hero-img-caption">
                            TACTICAL INTELLIGENCE BOARD · ZONE 14 & SPATIO-TEMPORAL DYNAMICS
                        </div>
                    </div>
                    <div class="hero-portal-right">
                        <div class="hero-eyebrow">
                            <span class="pulse-dot"></span> PRO MATCH DIAGNOSIS
                        </div>
                        <div class="hero-title">STAFF TACTICAL ANALYSIS PORTAL</div>
                        <div class="hero-desc">
                            High-precision match diagnosis analyzing spatial dynamics, high-pressing structures, 
                            defensive transitions, and Zone 14 penetration patterns based on detailed event streams.
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; padding: 0 4px;">
                <span class="section-badge-title">SELECT A FIXTURE TO ANALYZE</span>
                <span style="font-size: 11.5px; color: #64748B; font-family: 'JetBrains Mono', monospace;">3 MATCHES AVAILABLE</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        m_cols = st.columns(3, gap="medium")
        for idx, (col, (label, meta)) in enumerate(zip(m_cols, match_options.items())):
            m_info = MATCH_METADATA.get(meta["match_id"], {
                "stage": "FIFA WORLD CUP 2022",
                "stadium": "Qatar 2022 Venue",
                "home_code": meta["home_team"][:3].upper(),
                "away_code": meta["away_team"][:3].upper(),
                "score_detail": f"{meta['home_score']} - {meta['away_score']}",
            })

            with col:
                st.markdown(
                    f"""
                    <div class="match-fixture-card">
                        <div class="fixture-stage-header">
                            <span class="fixture-stage-badge">{m_info['stage']}</span>
                            <span class="fixture-date">{meta['match_date']}</span>
                        </div>
                        <div class="fixture-teams-row">
                            <div class="fixture-team fixture-team-home">
                                <span class="fixture-team-name">{meta['home_team']}</span>
                            </div>
                            <div class="fixture-score-pill">
                                {meta['home_score']} : {meta['away_score']}
                            </div>
                            <div class="fixture-team fixture-team-away">
                                <span class="fixture-team-name">{meta['away_team']}</span>
                            </div>
                        </div>
                        <div class="fixture-meta-details">
                            <div class="fixture-stadium">{m_info['stadium']}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    f"Analyze {meta['home_team']} vs {meta['away_team']}",
                    key=f"quick_match_{meta['match_id']}",
                    use_container_width=True,
                    type="secondary",
                ):
                    st.session_state.current_selected_label = label
                    st.session_state.selected_match_id = meta["match_id"]
                    st.session_state.current_result = None
                    st.session_state.active_phase_id = "global"
                    st.session_state.active_time_range = (0, 120)
                    st.rerun()
    else:
        current_match_meta = match_options[selected_match_label]
        match_id = current_match_meta["match_id"]

        # Reset if the user switches matches
        if match_id != st.session_state.selected_match_id:
            st.session_state.selected_match_id = match_id
            st.session_state.current_result = None
            st.session_state.active_phase_id = "global"
            st.session_state.active_time_range = (0, 120)

        # Dynamic phase segmentation
        miner = MatchMiner()
        generator = MatchPhaseGenerator()
        try:
            generated_phases = generator.get_or_create_phases(match_id)
        except Exception:
            generated_phases = []

        home_team = current_match_meta['home_team']
        away_team = current_match_meta['away_team']
        max_min = generated_phases[-1].minute_end if generated_phases else 120

        dynamic_phases = [
            {
                "id": "global",
                "btn_label": f"00-{max_min}' Global",
                "name": f"Full Match (00-{max_min}')",
                "range": (0, max_min),
                "desc": "Global Flow & Key Pivots",
                "query": f"Provide a comprehensive tactical analysis of the {len(generated_phases)} major phases and tactical swings in {home_team} vs {away_team}",
            }
        ]

        for idx, p in enumerate(generated_phases, 1):
            dynamic_phases.append({
                "id": f"p{idx}",
                "btn_label": f"{p.minute_start:02d}-{p.minute_end:02d}' {p.name}",
                "name": f"Phase {idx}: {p.minute_start:02d}-{p.minute_end:02d} min ({p.name})",
                "range": (p.minute_start, p.minute_end),
                "desc": p.description,
                "query": f"Analyze the phase from {p.minute_start} to {p.minute_end} min of {home_team} vs {away_team}: {p.description}.",
            })

        # Synchronize active phase
        active_phase_obj = next((p for p in dynamic_phases if p["id"] == st.session_state.active_phase_id), dynamic_phases[0])
        active_range = active_phase_obj["range"]
        st.session_state.active_time_range = active_range

        # Broadcast-Style Scoreboard Header
        m_info = MATCH_METADATA.get(match_id, {
            "stage": "FIFA WORLD CUP 2022",
            "stadium": "Qatar 2022 Venue",
            "home_code": home_team[:3].upper(),
            "away_code": away_team[:3].upper(),
            "score_detail": f"{current_match_meta['home_score']} - {current_match_meta['away_score']}",
        })

        st.markdown(
            f"""
            <div class="active-match-banner">
                <div class="active-match-left">
                    <div class="active-match-stage">
                        <span class="live-indicator"></span>
                        <span>{m_info['stage']} · {m_info['stadium']}</span>
                    </div>
                    <div class="active-match-title">
                        <span>{home_team}</span>
                        <span class="active-score-badge">{current_match_meta['home_score']} - {current_match_meta['away_score']}</span>
                        <span>{away_team}</span>
                    </div>
                </div>
                <div class="active-match-right">
                    <div class="active-focus-label">ACTIVE TACTICAL FOCUS</div>
                    <div class="active-focus-value">{active_phase_obj['btn_label']}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------------------------
        # STEP 1 : MATCH PHASES BREAKDOWN (UNIFORM INTERACTIVE BUTTONS)
        # ----------------------------------------------------------------------
        st.markdown(
            f"""
            <div class="timeline-header">
                <div>
                    <span class="timeline-step-label">STEP 1 · MATCH PHASES BREAKDOWN ({current_match_meta['home_team'].upper()} VS {current_match_meta['away_team'].upper()})</span>
                    <span class="timeline-step-desc"> — Click any phase to switch tactical zoom</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        cols = st.columns(len(dynamic_phases), gap="small")
        phase_clicked = None

        for idx, (col, p) in enumerate(zip(cols, dynamic_phases)):
            with col:
                is_active = st.session_state.active_phase_id == p["id"]
                btn_type = "primary" if is_active else "secondary"
                btn_text = p["btn_label"]
                if st.button(btn_text, key=f"phase_btn_{p['id']}_{match_id}", use_container_width=True, type=btn_type):
                    phase_clicked = p

        if phase_clicked:
            st.session_state.active_phase_id = phase_clicked["id"]
            st.session_state.active_time_range = phase_clicked["range"]
            active_phase_obj = phase_clicked
            active_range = phase_clicked["range"]

            # Load from semantic cache if available, else run analysis directly
            active_query = phase_clicked["query"]
            cached_resp = GLOBAL_SEMANTIC_CACHE.get(active_query, match_id, time_range=phase_clicked['range'])
            if cached_resp:
                st.session_state.current_result = {
                    "final_report": cached_resp["final_report"],
                    "execution_telemetry": cached_resp["execution_telemetry"],
                    "match_facts": None,
                    "retrieved_chunks": [],
                }
            else:
                with st.spinner(f"Analyzing sequence: {phase_clicked['name']}..."):
                    try:
                        import time
                        res = run_tactical_analysis(
                            coach_query=active_query,
                            match_id=match_id,
                            thread_id=f"session_{match_id}_{time.time()}",
                            user_time_range=phase_clicked["range"],
                        )
                        st.session_state.current_result = res
                        if res.get("final_report"):
                            GLOBAL_SEMANTIC_CACHE.set(
                                query=active_query,
                                match_id=match_id,
                                final_report=res["final_report"],
                                match_facts_json="{}",
                                execution_telemetry=res.get("execution_telemetry", {}),
                                time_range=phase_clicked['range'],
                            )
                    except Exception as e:
                        err_msg = str(e)
                        if "Rate limit" in err_msg or "429" in err_msg:
                            st.warning("Instant Groq TPM rate limit reached. Please wait 15-20 seconds.")
                        else:
                            st.error(f"Analysis error: {err_msg}")
            st.rerun()

        # Automatic generation if no report in memory
        if st.session_state.current_result is None or not st.session_state.current_result.get("final_report"):
            init_phase = active_phase_obj
            init_query = init_phase["query"]
            cached_resp = GLOBAL_SEMANTIC_CACHE.get(init_query, match_id, time_range=init_phase['range'])
            if cached_resp:
                st.session_state.current_result = {
                    "final_report": cached_resp["final_report"],
                    "execution_telemetry": cached_resp["execution_telemetry"],
                    "match_facts": None,
                    "retrieved_chunks": [],
                }
            else:
                res = None
                with st.spinner(f"Generating tactical report: {init_phase['name']}..."):
                    try:
                        import time
                        res = run_tactical_analysis(
                            coach_query=init_query,
                            match_id=match_id,
                            thread_id=f"session_{match_id}_{time.time()}",
                            user_time_range=init_phase["range"],
                        )
                        st.session_state.current_result = res
                        if res.get("final_report"):
                            GLOBAL_SEMANTIC_CACHE.set(
                                query=init_query,
                                match_id=match_id,
                                final_report=res["final_report"],
                                match_facts_json="{}",
                                execution_telemetry=res.get("execution_telemetry", {}),
                                time_range=init_phase['range'],
                            )
                    except Exception as e:
                        err_msg = str(e)
                        if "Rate limit" in err_msg or "429" in err_msg:
                            st.warning("Instant Groq TPM rate limit reached. Please wait 15-20 seconds.")
                        else:
                            st.error(f"Analysis error: {err_msg}")
                if res and res.get("final_report"):
                    st.rerun()

        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)

        # ----------------------------------------------------------------------
        # COACH TACTICAL QUERY BAR
        # ----------------------------------------------------------------------
        col_input, col_action = st.columns([4.2, 1.0], gap="small")
        with col_input:
            prompt_placeholder = f"Ask a tactical question on {active_phase_obj['btn_label']} (e.g. 'How to counter high pressing?')"
            inline_coach_query = st.text_input(
                "Coach Query:",
                placeholder=prompt_placeholder,
                label_visibility="collapsed",
                key=f"inline_query_box_{match_id}_{st.session_state.active_phase_id}",
            )
        with col_action:
            run_query_btn = st.button("Run Analysis", type="primary", use_container_width=True, key=f"btn_run_{match_id}")

        if run_query_btn:
            query_to_run = inline_coach_query.strip() if inline_coach_query.strip() else active_phase_obj["query"]
            import time
            current_time = time.time()
            last_run = st.session_state.get("last_run_time", 0.0)
            if current_time - last_run < 3.0:
                st.warning("Please wait a moment before running another analysis to prevent server overload.")
            else:
                st.session_state.last_run_time = current_time
                is_safe, msg = SecurityGuardrails.sanitize_and_validate(query_to_run)
                if not is_safe:
                    st.error(f"Query rejected: {msg}")
                else:
                    cached_resp = GLOBAL_SEMANTIC_CACHE.get(query_to_run, match_id, time_range=active_range)
                    if cached_resp:
                        st.session_state.current_result = {
                            "final_report": cached_resp["final_report"],
                            "execution_telemetry": cached_resp["execution_telemetry"],
                            "match_facts": None,
                            "retrieved_chunks": [],
                        }
                        st.rerun()
                    else:
                        result_state = None
                        with st.spinner(f"Running tactical analysis for {active_phase_obj['btn_label']}..."):
                            try:
                                result_state = run_tactical_analysis(
                                    coach_query=query_to_run,
                                    match_id=match_id,
                                    thread_id=f"session_{match_id}_{time.time()}",
                                    user_time_range=active_range,
                                )
                                st.session_state.current_result = result_state
                                if result_state.get("final_report"):
                                    GLOBAL_SEMANTIC_CACHE.set(
                                        query=query_to_run,
                                        match_id=match_id,
                                        final_report=result_state["final_report"],
                                        match_facts_json="{}",
                                        execution_telemetry=result_state.get("execution_telemetry", {}),
                                        time_range=active_range,
                                    )
                            except Exception as e:
                                err_msg = str(e)
                                if "Rate limit" in err_msg or "429" in err_msg:
                                    st.warning("Instant Groq TPM rate limit reached. Please wait 15-20 seconds.")
                                else:
                                    st.error(f"Analysis error: {err_msg}")
                        if result_state and result_state.get("final_report"):
                            st.rerun()

        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)

        # ----------------------------------------------------------------------
        # KEY PERFORMANCE INDICATORS (HOME VS AWAY)
        # ----------------------------------------------------------------------
        kpis_data = miner.get_realtime_kpis_by_team(match_id, active_range[0], active_range[1])
        home_name = kpis_data["home_team"]
        away_name = kpis_data["away_team"]
        h_s = kpis_data["home_stats"]
        a_s = kpis_data["away_stats"]

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric(
                "Turnovers Under Pressure",
                f"{h_s['turnovers_under_pressure']} - {a_s['turnovers_under_pressure']}",
                help=f"{home_name}: {h_s['turnovers_under_pressure']} | {away_name}: {a_s['turnovers_under_pressure']}",
            )
        with k2:
            st.metric(
                "Cumulative xG (Shots)",
                f"{h_s['total_xg']:.2f} ({h_s['total_shots']}) - {a_s['total_xg']:.2f} ({a_s['total_shots']})",
                help=f"{home_name}: {h_s['total_xg']:.2f} xG ({h_s['total_shots']} shots) | {away_name}: {a_s['total_xg']:.2f} xG ({a_s['total_shots']} shots)",
            )
        with k3:
            st.metric(
                "Final Third Passes",
                f"{h_s['passes_final_third']} - {a_s['passes_final_third']}",
                help=f"{home_name}: {h_s['passes_final_third']} | {away_name}: {a_s['passes_final_third']}",
            )
        with k4:
            st.metric(
                "High Recoveries",
                f"{h_s['high_recoveries']} - {a_s['high_recoveries']}",
                help=f"{home_name}: {h_s['high_recoveries']} | {away_name}: {a_s['high_recoveries']}",
            )

        # ----------------------------------------------------------------------
        # STEP 2 : DUAL-COLUMN WORKSPACE (EVENTS TIMELINE & STAFF REPORT)
        # ----------------------------------------------------------------------
        col_facts, col_report = st.columns([1.0, 1.25], gap="medium")

        # LEFT COLUMN : TIMELINE & MATCH FACTS
        with col_facts:
            critical_events = miner.get_critical_events(match_id, active_range[0], active_range[1])
            render_critical_events_timeline(
                critical_events,
                title="KEY EVENTS & DECISIVE ACTIONS",
                subtitle=f"{active_range[0]}'-{active_range[1]}' MIN",
            )
            if st.session_state.current_result and st.session_state.current_result.get("match_facts"):
                with st.expander("DETAILED MATCH FACTS & SPATIAL ZONES", expanded=False):
                    render_facts_table(st.session_state.current_result["match_facts"])

        # RIGHT COLUMN : STRUCTURED REPORT ACCORDIONS
        with col_report:
            if st.session_state.current_result and st.session_state.current_result.get("final_report"):
                res = st.session_state.current_result
                render_structured_report(res["final_report"])
                render_citations_panel(res.get("retrieved_chunks") or [])
            else:
                st.markdown(
                    f"""
                    <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 28px 20px; text-align: center; color: #64748B;">
                        <div style="font-weight: 800; font-size: 15px; color: #0F172A; margin-bottom: 6px; font-family: 'Plus Jakarta Sans', sans-serif;">
                            Tactical Analysis Focus: {active_phase_obj['btn_label']}
                        </div>
                        <div style="font-size: 13px; margin-bottom: 16px; color: #64748B;">
                            No analysis loaded for this focus window yet. Click below to generate the report.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(f"Generate Tactical Report ({active_phase_obj['btn_label']})", type="primary", use_container_width=True, key=f"btn_gen_fallback_{match_id}"):
                    with st.spinner(f"Generating tactical report: {active_phase_obj['name']}..."):
                        import time
                        res = run_tactical_analysis(
                            coach_query=active_phase_obj["query"],
                            match_id=match_id,
                            thread_id=f"session_{match_id}_{time.time()}",
                            user_time_range=active_phase_obj["range"],
                        )
                        st.session_state.current_result = res
                        if res.get("final_report"):
                            GLOBAL_SEMANTIC_CACHE.set(
                                query=active_phase_obj["query"],
                                match_id=match_id,
                                final_report=res["final_report"],
                                match_facts_json="{}",
                                execution_telemetry=res.get("execution_telemetry", {}),
                                time_range=active_phase_obj["range"],
                            )
                        st.rerun()

# ==============================================================================
# TAB 2 : SUPERVISION (TECHNICAL METRICS & BENCHMARK)
# ==============================================================================
with tab_admin:
    st.markdown("<div style='font-size: 16px; font-weight: 800; color: #0F172A; font-family: \"Plus Jakarta Sans\", sans-serif; margin-bottom: 12px; letter-spacing: -0.01em;'>TECHNICAL SUPERVISION & BENCHMARK</div>", unsafe_allow_html=True)

    current_telem = {}
    if st.session_state.current_result:
        current_telem = st.session_state.current_result.get("execution_telemetry", {})

    render_telemetry_metrics(current_telem)
    st.divider()

    render_model_benchmark_panel()
    st.divider()

    c_left, c_right = st.columns(2)
    with c_left:
        render_knowledge_base_explorer()
    with c_right:
        render_sql_query_console()

