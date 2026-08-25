from agent.graph import build_graph


def invoke(
    graph,
    config,
    caller_text: str,
    initial: bool = False,
):
    state = {
        "caller_text": caller_text,
    }

    if initial:
        state.update(
            {
                "session_id": "appointment-demo-001",
                "conversation": [],
                "greeted": False,
                "verified_patient_id": None,
                "verification_attempts": 0,
                "verification_fields": {},
                "identity_status": None,
                "intent": None,
                "active_workflow": None,
                "collected_fields": {},
                "pending_confirmation": None,
                "tool_results": [],
                "safety_flags": [],
                "escalation_required": False,
                "call_summary": None,
                "metrics": {},
                "confirmation_required": False,
                "confirmation_received": False,
            }
        )

    result = graph.invoke(
        state,
        config=config,
    )

    print()
    print("CALLER:", caller_text)
    print(
        "NODE:",
        result.get("current_node"),
    )
    print(
        "RESPONSE:",
        result.get("response_text"),
    )

    return result


def main() -> None:
    graph = build_graph()

    config = {
        "configurable": {
            "thread_id": "appointment-demo-001",
        }
    }

    invoke(
        graph,
        config,
        # "I want to book an appointment.",
        "I need to move my dermatology visit to next week.",
        initial=True,
    )

    invoke(
        graph,
        config,
        "CARE-00001 and 1001",
    )

    invoke(
        graph,
        config,
        "Dermatology tomorrow",
    )

    invoke(
        graph,
        config,
        "yes",
    )


if __name__ == "__main__":
    main()
