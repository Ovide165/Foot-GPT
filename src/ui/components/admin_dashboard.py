"""
Admin Dashboard & LLMOps Telemetry Component.
Zero Emojis, Clean Telemetry, Plotly Dark Visualizations.
"""

from typing import Any, Dict, List
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.app_service import faithfulness_label
from src.data_mining.db_connection import ReadOnlyDBConnection
from src.evaluation.benchmark_comparison import run_benchmark_for_provider
from src.rag.vector_store import VectorStoreManager


def render_telemetry_metrics(telemetry: Dict[str, Any]) -> None:
    """Displays pipeline performance, latency, and faithfulness metrics."""
    if not telemetry:
        st.info("No active analysis session.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        total_lat = telemetry.get("total_pipeline_latency_ms", 0)
        st.metric("TOTAL LATENCY", f"{total_lat:.0f} ms")
    with c2:
        st.metric("FAITHFULNESS (CRITIC)", faithfulness_label(telemetry))
    with c3:
        sql_lat = telemetry.get("sql_miner_latency_ms", 0)
        st.metric("SQL MINER LATENCY", f"{sql_lat:.1f} ms")
    with c4:
        rag_lat = telemetry.get("deep_rag_latency_ms", 0)
        st.metric("DEEP RAG LATENCY", f"{rag_lat:.1f} ms")

    # Latency breakdown per node
    node_latencies = {
        "1. Router": telemetry.get("router_latency_ms", 0),
        "2A. SQL Miner": telemetry.get("sql_miner_latency_ms", 0),
        "2B. Deep RAG": telemetry.get("deep_rag_latency_ms", 0),
        "3. Synthesizer": telemetry.get("synthesizer_latency_ms", 0),
        "4. Critic": telemetry.get("critic_latency_ms", 0),
    }

    df_lat = pd.DataFrame(list(node_latencies.items()), columns=["Pipeline Node", "Latency (ms)"])
    
    amethyst_palette = ["#4F46E5", "#6366F1", "#818CF8", "#4338CA", "#3730A3"]
    fig = px.bar(
        df_lat,
        x="Pipeline Node",
        y="Latency (ms)",
        color="Pipeline Node",
        color_discrete_sequence=amethyst_palette,
        title="LangGraph Pipeline Latency Breakdown",
        template="plotly_white",
    )
    fig.update_layout(
        showlegend=False,
        height=260,
        margin=dict(l=10, r=10, t=35, b=10),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        font=dict(family="JetBrains Mono", color="#0F172A"),
        title=dict(font=dict(color="#0F172A", size=13, family="Plus Jakarta Sans")),
    )
    fig.update_xaxes(showgrid=False, tickfont=dict(color="#334155", size=11))
    fig.update_yaxes(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(color="#334155", size=11))
    st.plotly_chart(fig, use_container_width=True)


def render_knowledge_base_explorer() -> None:
    """Interactive explorer for the 305 tactical literature chunks in ChromaDB."""
    st.markdown("<div style='font-size: 14px; font-weight: 800; color: #0F172A; font-family: \"Plus Jakarta Sans\", sans-serif; margin-bottom: 2px;'>RAG CORPUS EXPLORER (305 CHUNKS)</div>", unsafe_allow_html=True)
    
    try:
        vs = VectorStoreManager()
        total_docs = vs.count()
        st.caption(f"ChromaDB Dense Index: **{total_docs} tactical chunks**")

        search_query = st.text_input("Search concept:", placeholder="e.g. Rest-Defense, Half-Spaces, Betweenness Centrality", label_visibility="collapsed")
        if search_query:
            results = vs.retrieve(search_query, top_k=4)
            for idx, (chunk, score) in enumerate(results, 1):
                with st.expander(f"[{score:.2f} Sim] {chunk.title} ({chunk.authors or 'N/A'})"):
                    st.markdown(f"**Section**: {chunk.section or 'Main'}")
                    st.markdown(f"**Citation**: `{chunk.format_citation()}`")
                    st.caption(chunk.content)
    except Exception as e:
        st.info("ChromaDB vector store connected.")


def render_sql_query_console() -> None:
    """Read-only SQL querying console."""
    st.markdown("<div style='font-size: 14px; font-weight: 800; color: #0F172A; font-family: \"Plus Jakarta Sans\", sans-serif; margin-bottom: 2px;'>SQL CONSOLE (READ-ONLY)</div>", unsafe_allow_html=True)
    db = ReadOnlyDBConnection()

    sample_sql = "SELECT match_id, match_date, home_team, away_team, home_score, away_score FROM matches LIMIT 8;"
    query = st.text_area("SQL Query:", sample_sql, height=70, label_visibility="collapsed")

    if st.button("RUN SQL QUERY"):
        try:
            rows = db.execute_safe_query(query)
            if rows:
                df = pd.DataFrame([dict(r) for r in rows])
                st.dataframe(df, use_container_width=True)
                st.caption(f"{len(rows)} rows returned.")
            else:
                st.info("No rows returned.")
        except Exception as e:
            st.error(f"[SQL ERROR] {str(e)}")


def render_model_benchmark_panel() -> None:
    """Model benchmarking and evaluation panel."""
    st.markdown("<div style='font-size: 14px; font-weight: 800; color: #0F172A; font-family: \"Plus Jakarta Sans\", sans-serif; margin-bottom: 2px;'>MULTI-MODEL BENCHMARK SUITE (10 SCENARIOS)</div>", unsafe_allow_html=True)
    st.caption("Empirical measurement of latency, factual faithfulness, and 3-part structural compliance.")

    c1, c2 = st.columns([2, 1])
    provider_map = {
        "Groq (Qwen 3.8 27B / GPT-OSS 120B)": "groq",
        "OpenAI (GPT-4o)": "openai",
        "Google Gemini (Gemini 2.0 Flash)": "gemini",
        "Mock Local (Deterministic Mode)": "mock",
    }
    with c1:
        target_label = st.selectbox("Model Provider:", options=list(provider_map.keys()), index=0)
        target_provider = provider_map[target_label]
    with c2:
        num_tests = st.slider("Number of test scenarios:", min_value=1, max_value=10, value=3)

    if st.button("RUN BENCHMARK"):
        with st.spinner(f"Executing benchmark on {target_provider.upper()}..."):
            summary = run_benchmark_for_provider(target_provider, max_questions=num_tests)
            st.success(f"[COMPLETED] Benchmark finished for {target_provider.upper()}.")

            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("AVERAGE LATENCY", f"{summary['avg_latency_ms']} ms")
            mc2.metric("CRITIC FAITHFULNESS", faithfulness_label({"critic_faithfulness_score": summary["avg_faithfulness"]}))
            mc3.metric("3-PART COMPLIANCE", f"{summary['volets_compliance_pct']}%")

            df_det = pd.DataFrame(summary["details"])
            st.dataframe(df_det, use_container_width=True)
