from agent.tools.dispatcher import (
    ToolNotAllowedError,
    execute_read_only_tool,
)


def main() -> None:
    print("ALLOWED TOOL TEST")

    result = execute_read_only_tool(
        "search_clinic_faq",
        {
            "query": "opening hours",
        },
    )

    print(result)

    print()
    print("BLOCKED TOOL TEST")

    try:
        execute_read_only_tool(
            "delete_patient",
            {
                "patient_id": 1,
            },
        )

    except ToolNotAllowedError as exc:
        print("BLOCKED:", exc)


if __name__ == "__main__":
    main()
