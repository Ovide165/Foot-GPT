"""
Test de fumee de l'interface Streamlit (harnais AppTest), sans cle API : mode demonstration.
"""

import pytest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.llm_factory import DEMO_MODE_BANNER

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


@pytest.fixture
def app(monkeypatch):
    for var in ("GROQ_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.setenv(var, "")      # defini mais vide : load_dotenv() ne le remplace pas
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    return AppTest.from_file(str(APP_PATH), default_timeout=150).run()


def test_app_starts_in_demo_mode_with_real_counts(app):
    assert not app.exception
    assert DEMO_MODE_BANNER in [e.value for e in app.error]
    assert any("4 MATCHES AVAILABLE" in m.value for m in app.markdown)
    assert len([b for b in app.button if b.label.startswith("Analyze")]) == 4   # aucun match masque


def test_analysis_shows_the_critic_verdict(app):
    next(b for b in app.button if b.label.startswith("Analyze")).click()
    app.run()
    assert not app.exception
    assert any("Critic verdict: PASS" in s.value for s in app.success)
