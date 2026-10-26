"""
Tests unitaires pour la LLMFactory et les modes de fallback.
"""

import pytest
from src.llm_factory import LLMFactory, MockChatModel
from src.schemas.router import TacticalPlan


def test_llm_factory_initialization():
    """Vérifie que la factory retourne des modèles valides."""
    fast_model = LLMFactory.get_fast_model()
    assert fast_model is not None

    reasoning_model = LLMFactory.get_reasoning_model()
    assert reasoning_model is not None


def test_mock_chat_model_structured_output():
    """Vérifie le fonctionnement du mode Mock avec structured output."""
    mock = MockChatModel()
    structured = mock.with_structured_output(TacticalPlan)
    plan = structured.invoke("Test query")
    assert isinstance(plan, TacticalPlan)
    assert len(plan.time_windows) > 0


import logging
import sys
import types

from src.llm_factory import DEMO_MODE_BANNER, _is_usable_key


@pytest.fixture
def no_keys(monkeypatch):
    for var in ("GROQ_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "groq")


def test_mock_fallback_is_not_silent(no_keys, caplog):
    with caplog.at_level(logging.WARNING, logger="src.llm_factory"):
        model = LLMFactory.get_fast_model()
    assert isinstance(model, MockChatModel)
    assert any(DEMO_MODE_BANNER in r.getMessage() for r in caplog.records)


def test_demo_mode_is_detected_without_logging(no_keys, caplog):
    with caplog.at_level(logging.WARNING, logger="src.llm_factory"):
        assert LLMFactory.is_demo_mode() is True
    assert caplog.records == []  # la sonde du bandeau ne pollue pas les logs


def test_demo_banner_text_and_app_wiring():
    assert DEMO_MODE_BANNER == "MODE DÉMONSTRATION : aucun LLM réel"
    from pathlib import Path
    source = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
    assert "if LLMFactory.is_demo_mode():" in source and "st.error(DEMO_MODE_BANNER)" in source


def test_real_gemini_key_starting_with_aiza_is_accepted(monkeypatch):
    class FakeGemini:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_module = types.ModuleType("langchain_google_genai")
    fake_module.ChatGoogleGenerativeAI = FakeGemini
    monkeypatch.setitem(sys.modules, "langchain_google_genai", fake_module)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyFAKE_but_well_formed_key_123")
    for factory_method in (LLMFactory.get_fast_model, LLMFactory.get_reasoning_model):
        model = factory_method()
        assert isinstance(model, FakeGemini)
        assert model.kwargs["google_api_key"] == "AIzaSyFAKE_but_well_formed_key_123"
    assert LLMFactory.is_demo_mode() is False


def test_example_placeholders_are_rejected_for_every_provider():
    for key in ("gsk_votre_cle_groq_ici", "sk-votre_cle", "AIza_votre_cle_gemini", "", None):
        assert _is_usable_key(key) is False
    assert _is_usable_key("gsk_real_looking_key") is True
