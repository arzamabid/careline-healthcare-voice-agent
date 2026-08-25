from agent.graph import build_graph


def base_state() -> dict:
    return {
        "session_id": "appointment-test",
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
        "confirmation_required": False,
        "confirmation_received": False,
    }


def test_booking_waits_for_confirmation() -> None:
    graph = build_graph()

    config = {
        "configurable": {
            "thread_id": "booking-confirmation-test",
        }
    }

    graph.invoke(
        base_state(),
        config=config,
    )

    graph.invoke(
        {
            "caller_text": (
                "CARE-00001 and 1001"
            ),
        },
        config=config,
    )

    result = graph.invoke(
        {
            "caller_text": (
                "Dermatology tomorrow"
            ),
        },
        config=config,
    )

    assert result[
        "confirmation_required"
    ] is True

    assert result[
        "selected_appointment_id"
    ] is not None

    assert result[
        "confirmation_received"
    ] is False


def test_no_confirmation_does_not_execute_booking() -> None:
    graph = build_graph()

    config = {
        "configurable": {
            "thread_id": "booking-no-test",
        }
    }

    graph.invoke(
        base_state(),
        config=config,
    )

    graph.invoke(
        {
            "caller_text": (
                "CARE-00001 and 1001"
            ),
        },
        config=config,
    )

    graph.invoke(
        {
            "caller_text": (
                "Dermatology tomorrow"
            ),
        },
        config=config,
    )

    result = graph.invoke(
        {
            "caller_text": "no",
        },
        config=config,
    )

    assert (
        result["confirmation_required"]
        is False
    )

    assert result[
        "pending_confirmation"
    ] is None

    assert not any(
        item.get("tool") == "book_appointment"
        for item in result.get(
            "tool_results",
            []
        )
    )
