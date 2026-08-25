from typing import Any

from agent.tools.registry import (
    READ_ONLY_TOOL_REGISTRY,
)


class ToolNotAllowedError(Exception):
    pass


def execute_read_only_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    tool = READ_ONLY_TOOL_REGISTRY.get(
        tool_name
    )

    if tool is None:
        raise ToolNotAllowedError(
            f"Tool is not allowed: {tool_name}"
        )

    return tool.invoke(arguments)
