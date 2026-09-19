"""
Tactical Report Rendering Component (Hudl / Veo Professional Style).
Strict Concision, Clean Cards, Zero Emojis.
"""

import re
from typing import Any, Dict, List
import pandas as pd
import streamlit as st

from src.schemas.miner import MatchFacts


def render_facts_table(match_facts: MatchFacts) -> None:
    """Renders a clean tabular view of match facts and phase metrics."""
    if not match_facts or not match_facts.phases_data:
        return

    data = []
    for p in match_facts.phases_data:
        data.append({
            "Phase": p.phase_label,
            "Team": p.team,
            "On-Ball Actions": p.on_ball_events,
            "Defensive Actions": p.defensive_events,
            "Field Tilt": f"{p.field_tilt_pct}%",
            "Passes": f"{p.passes_completed}/{p.passes_attempted} ({p.pass_accuracy_pct}%)",
            "Final Third": p.passes_final_third,
            "Zone 14": p.passes_zone_14,
            "Shots": f"{p.shots_count} ({p.shots_on_target})",
            "xG": round(p.xg_sum, 3),
            "Turnovers Under Pressure": p.turnovers_under_pressure,
            "High Recoveries": p.high_recoveries_count,
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_citations_panel(retrieved_chunks: List[Dict[str, Any]]) -> None:
    """Renders the theoretical literature citations panel."""
    if not retrieved_chunks:
        return

    with st.expander(f"METHODOLOGICAL & THEORETICAL REFERENCES ({len(retrieved_chunks)})", expanded=False):
        for idx, chunk in enumerate(retrieved_chunks, 1):
            st.markdown(
                f"""
                <div style="background: #F1F5F9; border-radius: 6px; padding: 8px 12px; margin-bottom: 6px; font-size: 13px; color: #475569; border: 1px solid rgba(0, 0, 0, 0.06);">
                    <b style="color: #0F172A;">{idx}. {chunk['citation']}</b>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_critical_events_timeline(events: List[Dict[str, Any]], title: str = "KEY EVENTS & DECISIVE ACTIONS", subtitle: str = "") -> None:
    """Renders a compact, responsive timeline of key decisive match events."""
    import json

    header_html = f'<div class="pro-card-header"><div class="pro-card-title">{title}</div><div class="pro-card-subtitle">{subtitle}</div></div>'

    if not events:
        empty_html = (
            f'<div class="pro-card">'
            f'{header_html}'
            f'<div style="padding: 24px 16px; text-align: center; color: #64748B; font-size: 13px;">'
            f'No major decisive events (goal, high-xG shot, fatal turnover) recorded in this window.'
            f'</div>'
            f'</div>'
        )
        st.markdown(empty_html, unsafe_allow_html=True)
        return

    cards_html = []
    for ev in events:
        raw = json.loads(ev.get("raw_data", "{}"))
        ev_type = ev.get("type", "")
        minute = ev.get("minute", 0)
        second = ev.get("second", 0)
        time_str = f"{minute:02d}:{second:02d}"
        team = ev.get("team", "")
        player = ev.get("player") or "Team Collective"

        # Classification of the event
        is_goal = ev_type == "Shot" and raw.get("shot_outcome") == "Goal"
        is_assist = raw.get("pass_goal_assist", False)
        is_penalty_foul = raw.get("foul_committed_penalty", False)
        is_shot = ev_type == "Shot"
        xg = raw.get("shot_statsbomb_xg")
        xg_str = f" · xG {xg:.2f}" if xg is not None else ""

        # Spatial zone detection
        x = ev.get("x")
        y = ev.get("y")
        zone_pill_html = ""
        if x is not None and y is not None:
            try:
                xf, yf = float(x), float(y)
                if 75 <= xf <= 95 and 26.67 <= yf <= 53.33:
                    zone_pill_html = '<span class="zone-pill">ZONE 14</span>'
                elif 60 <= xf <= 102 and (yf < 26.67 or yf > 53.33):
                    zone_pill_html = '<span class="zone-pill" style="color: #0284C7; background: #F0F9FF; border-color: rgba(2,132,199,0.25);">HALF-SPACE</span>'
                elif xf >= 80:
                    zone_pill_html = '<span class="zone-pill" style="color: #D97706; background: #FFFBEB; border-color: rgba(217,119,6,0.25);">ATT. 3RD</span>'
                elif xf <= 40:
                    zone_pill_html = '<span class="zone-pill" style="color: #64748B; background: #F8FAFC; border-color: rgba(100,116,139,0.25);">DEF. 3RD</span>'
            except (ValueError, TypeError):
                pass

        if is_goal:
            border_color = "#10B981"
            bg_color = "rgba(16, 185, 129, 0.08)"
            badge_text = "GOAL"
            badge_bg = "#065F46"
            badge_color = "#FFFFFF"
            detail = f"{player} ({team}){xg_str}"
        elif is_assist:
            border_color = "#D97706"
            bg_color = "rgba(217, 119, 6, 0.08)"
            badge_text = "ASSIST"
            badge_bg = "#FEF3C7"
            badge_color = "#92400E"
            detail = f"{player} ({team})"
        elif is_penalty_foul:
            border_color = "#E11D48"
            bg_color = "rgba(225, 29, 72, 0.08)"
            badge_text = "PENALTY"
            badge_bg = "#9F1239"
            badge_color = "#FFFFFF"
            detail = f"Foul by {player} ({team})"
        elif is_shot:
            outcome = raw.get("shot_outcome", "Shot")
            border_color = "#4F46E5"
            bg_color = "rgba(79, 70, 229, 0.06)"
            badge_text = outcome.upper()
            badge_bg = "#EEF2FF"
            badge_color = "#3730A3"
            detail = f"{player} ({team}){xg_str}"
        else:
            border_color = "#E11D48"
            bg_color = "rgba(225, 29, 72, 0.06)"
            badge_text = "TURNOVER"
            badge_bg = "#FFE4E6"
            badge_color = "#9F1239"
            detail = f"Turnover: {player} ({team}) in defensive third"

        card = (
            f'<div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; background: {bg_color}; border-left: 3.5px solid {border_color}; border-radius: 6px; padding: 7px 11px; margin-bottom: 6px; border-top: 1px solid rgba(0,0,0,0.03); border-right: 1px solid rgba(0,0,0,0.03); border-bottom: 1px solid rgba(0,0,0,0.03);">'
            f'<div style="display: flex; align-items: baseline; gap: 6px; min-width: 0; flex: 1;">'
            f'<span style="font-family: \'JetBrains Mono\', monospace; font-weight: 700; font-size: 11.5px; color: #4F46E5; flex-shrink: 0;">{time_str}\'</span>'
            f'<span style="font-size: 12.5px; font-weight: 600; color: #0F172A; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{detail}</span>'
            f'{zone_pill_html}'
            f'</div>'
            f'<span style="font-family: \'JetBrains Mono\', monospace; font-size: 9.5px; font-weight: 700; background: {badge_bg}; color: {badge_color}; padding: 2px 6px; border-radius: 4px; letter-spacing: 0.03em; flex-shrink: 0; white-space: nowrap;">{badge_text}</span>'
            f'</div>'
        )
        cards_html.append(card)

    container_html = (
        f'<div class="pro-card">'
        f'{header_html}'
        f'<div style="max-height: 480px; overflow-y: auto; padding-right: 4px;" class="custom-scroll">{"".join(cards_html)}</div>'
        f'</div>'
    )
    st.markdown(container_html, unsafe_allow_html=True)


def render_structured_report(report_text: str) -> None:
    """
    Renders the tactical report in expandable accordion sections (Hudl Pro Style Light).
    Enables coaches to collapse and expand each tactical part cleanly.
    """
    if not report_text:
        return

    clean_text = _strip_emojis(report_text)
    chunks = re.split(r"\n+(?=(?:#{1,4}\s*)?(?:Part\s*[123]|Volet\s*[123]|0[123]\.))", clean_text.strip(), flags=re.IGNORECASE)

    has_rendered = False
    for chunk in chunks:
        lines = [l for l in chunk.split("\n") if l.strip()]
        if not lines:
            continue

        header = lines[0].lower()
        body_lines = [l for l in lines[1:] if not l.strip().startswith("#") and not re.match(r"^(?:Part\s*[123]|Volet\s*[123]|0[123]\.)", l.strip(), re.IGNORECASE)]

        if not body_lines and len(lines) == 1:
            body_lines = lines

        if "part 1" in header or "volet 1" in header or "01." in header or "diagnostic" in header:
            title = "PART 1 · FACTUAL DIAGNOSIS & IDENTIFIED VULNERABILITIES"
            accent_border = "#E11D48"
            expanded = True
        elif "part 2" in header or "volet 2" in header or "02." in header or "principle" in header or "principe" in header or "theor" in header:
            title = "PART 2 · TACTICAL PRINCIPLES & GAME FOUNDATIONS"
            accent_border = "#6366F1"
            expanded = True
        elif "part 3" in header or "volet 3" in header or "03." in header or "prescription" in header or "drill" in header or "exercice" in header:
            title = "PART 3 · TRAINING DRILLS (UEFA PRO / FA STANDARD)"
            accent_border = "#10B981"
            expanded = True
        else:
            title = "STAFF TACTICAL SYNTHESIS"
            accent_border = "#3B82F6"
            expanded = True

        formatted_items = []
        for l in body_lines:
            item_html = _format_item(l)
            if item_html:
                formatted_items.append(item_html)

        if formatted_items:
            has_rendered = True
            html_items = "".join(formatted_items)
            with st.expander(title, expanded=expanded):
                st.markdown(
                    f"""
                    <div style="border-left: 3.5px solid {accent_border}; padding-left: 14px; margin: 4px 0;">
                        {html_items}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    if not has_rendered:
        with st.expander("STAFF TACTICAL SYNTHESIS", expanded=True):
            st.markdown(
                f"""
                <div style="border-left: 3.5px solid #6366F1; padding-left: 14px; margin: 4px 0;">
                    <div class="report-item">{clean_text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _strip_emojis(text: str) -> str:
    """Removes any emoji characters."""
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff]|"
        "[\u2600-\u27bf]|"
        "[\u2300-\u23ff]|"
        "[\u2b50-\u2b55]|"
        "[\u200d]|[\ufe0f]",
        flags=re.UNICODE
    )
    return emoji_pattern.sub("", text)


def _format_item(line: str) -> str:
    """Formats a bullet item with clean typography, highlighting deltas and citations."""
    raw_strip = line.strip()
    if not raw_strip:
        return ""

    indent = 0
    if line.startswith("    ") or line.startswith("\t"):
        indent = 20

    l = raw_strip
    if l.startswith("- ") or l.startswith("* "):
        l = l[2:].strip()

    # Deltas
    l = re.sub(r"(\+\d+(?:\.\d+)?%)", r'<span class="metric-pill">\1</span>', l)
    l = re.sub(r"(-\d+(?:\.\d+)?%)", r'<span class="metric-pill">\1</span>', l)

    # Formal citations
    l = re.sub(r"(\[[^\]]+,\s*\d{4}[^\]]*\])", r'<span style="color: #4338CA; font-size: 11.5px; font-weight: 700; font-family: \'JetBrains Mono\', monospace;">\1</span>', l)

    # Bold subheadings e.g. Drill Setup, Coaching Points
    l = re.sub(r"\*\*([^*]+)\*\*", r'<b style="color: #0F172A;">\1</b>', l)

    style = f"margin-left: {indent}px; margin-bottom: 6px;" if indent else "margin-bottom: 6px;"
    return f'<div class="report-item" style="{style}">• {l}</div>'
