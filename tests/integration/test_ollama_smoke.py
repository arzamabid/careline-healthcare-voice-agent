import pytest

from agent.llm.intent import (
    classify_intent_with_llm,
)
from apps.api.config import get_settings


@pytest.mark.integration
def test_ollama_classifies_appointment() -> None:
    settings = get_settings()

    if not settings.ollama_model:
        pytest.skip(
            "OLLAMA_MODEL not configured"
        )

    result = classify_intent_with_llm(
        "I need to move my clinic visit "
        "to another day."
    )

    assert result.intent == "appointment"
