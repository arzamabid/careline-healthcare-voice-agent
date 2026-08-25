from unittest.mock import patch

from agent.llm.response import (
    generate_patient_response,
)


def test_response_falls_back_when_llm_fails() -> None:
    with patch(
        "agent.llm.response.get_ollama_model"
    ) as mocked:
        mocked.side_effect = RuntimeError(
            "Ollama unavailable"
        )

        result = generate_patient_response(
            instruction="Confirm completion.",
            fallback="Action completed.",
        )

    assert result == "Action completed."


