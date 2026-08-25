from agent.graph import build_graph


def test_graph_creates_checkpoint() -> None:
    graph = build_graph()

    config = {
        "configurable": {
            "thread_id": "persistence-test",
        }
    }

    graph.invoke(
        {
            "session_id": "persistence-test",
            "caller_text": "I need an appointment.",
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
        config=config,
    )

    snapshot = graph.get_state(
        config,
    )

    assert snapshot.values["intent"] == "appointment"

    assert (
        snapshot.values["session_id"]
        == "persistence-test"
    )
