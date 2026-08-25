from agent.llm.tool_model import get_tool_model


def main() -> None:
    model = get_tool_model()

    response = model.invoke(
        """
You are an administrative healthcare assistant.

Use an available tool when the user is asking for
information that requires clinic data.

User:
Find dermatology appointments for 2026-08-25.
"""
    )

    print("CONTENT:")
    print(response.content)

    print()
    print("TOOL CALLS:")
    print(response.tool_calls)


if __name__ == "__main__":
    main()
