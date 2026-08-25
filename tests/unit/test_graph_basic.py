from agent.graph import build_graph


def invoke_graph(
    caller_text: str,
    thread_id: str,
):
    graph = build_graph()

    return graph.invoke(
        {
            "session_id": thread_id,
            "caller_text": caller_text,
            "conversation": [],
            "verified_patient_id": None,
            "verification_attempts": 0,
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
        config={
            "configurable": {
                "thread_id": thread_id,
            }
        },
    )


def test_appointment_intent() -> None:
    result = invoke_graph(
        "I want to book an appointment.",
        "test-appointment",
    )

    assert result["intent"] == "appointment"


def test_faq_intent() -> None:
    result = invoke_graph(
        "What time does the clinic open?",
        "test-faq",
    )

    assert result["intent"] == "faq"


def test_previsit_intent() -> None:
    result = invoke_graph(
        "I need to complete my pre-visit intake.",
        "test-intake",
    )

    assert result["intent"] == "previsit_intake"
