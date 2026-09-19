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
