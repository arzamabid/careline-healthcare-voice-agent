import pytest

from agent.tools.dispatcher import (
    ToolNotAllowedError,
    execute_read_only_tool,
)


def test_unknown_tool_is_rejected() -> None:
    with pytest.raises(
        ToolNotAllowedError
    ):
        execute_read_only_tool(
            "delete_patient",
            {
                "patient_id": 1,
            },
        )
