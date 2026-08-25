from agent.graph import build_graph


def test_unknown_faq_does_not_fabricate() -> None:
    graph = build_graph()

    result = graph.invoke(
        {
            "session_id": "faq-test",
            "caller_text": (
                "Does the clinic provide helicopter transport?"
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
        },
        config={
            "configurable": {
                "thread_id": "faq-test",
            }
        },
    )

    assert result["intent"] == "faq"

    assert (
        "verified information"
        in result["response_text"].lower()
    )
