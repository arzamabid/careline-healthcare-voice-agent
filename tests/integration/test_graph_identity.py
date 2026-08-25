from agent.graph import build_graph


def initial_state() -> dict:
    return {
        "session_id": "identity-test",
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
    }


def test_identity_verification_across_turns() -> None:
    graph = build_graph()

    config = {
        "configurable": {
            "thread_id": "identity-success",
        }
    }

    first = graph.invoke(
        initial_state(),
        config=config,
    )

    assert first["intent"] == "appointment"

    assert (
        first["identity_status"]
        == "needs_identifiers"
    )

    second = graph.invoke(
        {
            "caller_text": (
                "CARE-00001 and 1001"
            ),
        },
        config=config,
    )

    assert (
        second["verified_patient_id"]
        is not None
    )

    assert (
        second["identity_status"]
        == "verified"
    )

    assert (
        second["intent"]
        == "appointment"
    )


def test_three_failed_verifications_escalate() -> None:
    graph = build_graph()

    config = {
        "configurable": {
            "thread_id": "identity-failure",
        }
    }

    graph.invoke(
        initial_state(),
        config=config,
    )

    for _ in range(3):
        result = graph.invoke(
            {
                "caller_text": (
                    "CARE-99999 and 9999"
                ),
            },
            config=config,
        )

    assert (
        result["verification_attempts"]
        == 3
    )

    assert (
        result["escalation_required"]
        is True
    )

    assert (
        result["current_node"]
        == "escalation"
    )
