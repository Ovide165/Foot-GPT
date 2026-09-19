"""
Package des composants UI pour foot-GPT.
"""

from src.ui.components.admin_dashboard import (
    render_knowledge_base_explorer,
    render_model_benchmark_panel,
    render_sql_query_console,
    render_telemetry_metrics,
)
from src.ui.components.report_renderer import (
    render_citations_panel,
    render_facts_table,
    render_structured_report,
)

__all__ = [
    "render_facts_table",
    "render_citations_panel",
    "render_structured_report",
    "render_telemetry_metrics",
    "render_knowledge_base_explorer",
    "render_sql_query_console",
    "render_model_benchmark_panel",
]
