from agent.graph import build_graph


def main() -> None:
    graph = build_graph()

    config = {
        "configurable": {
            "thread_id": "identity-demo-001",
        }
    }

    first_turn = graph.invoke(
        {
            "session_id": "identity-demo-001",
            "caller_text": (
                "I want to book an appointment."
            ),
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
        },
        config=config,
    )

    print("TURN 1")
    print("Intent:", first_turn.get("intent"))
    print(
        "Identity:",
        first_turn.get("identity_status"),
    )
    print(
        "Response:",
        first_turn.get("response_text"),
    )

    second_turn = graph.invoke(
        {
            "caller_text": (
                # "My member ID is CARE-00001 "
                # "and my phone ends in 1001."
                "My member ID is CARE-99999 "
                "and my phone ends in 9999."
            ),
        },
        config=config,
    )

    print()
    print("TURN 2")
    print(
        "Intent:",
        second_turn.get("intent"),
    )
    print(
        "Patient:",
        second_turn.get(
            "verified_patient_id"
        ),
    )
    print(
        "Identity:",
        second_turn.get(
            "identity_status"
        ),
    )


if __name__ == "__main__":
    main()
