from agent.graph import build_graph
from db.models import CallSession
from db.session import get_db_session


def create_db_session() -> int:
    db = get_db_session()

    try:
        call_session = CallSession()
        db.add(call_session)
        db.commit()
        db.refresh(call_session)

        return call_session.id
    finally:
        db.close()


def invoke(
    graph,
    config,
    caller_text: str,
    initial: bool = False,
    db_session_id: int | None = None,
):
    state = {
        "caller_text": caller_text,
    }

    if initial:
        state.update(
            {
                "session_id": "intake-demo-001",
                "db_session_id": db_session_id,
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
                "intake_index": 0,
                "intake_answers": {},
                "intake_review_required": False,
                "intake_confirmed": False,
            }
        )

    result = graph.invoke(
        state,
        config=config,
    )

    print()
    print("CALLER:", caller_text)
    print("NODE:", result.get("current_node"))
    print("RESPONSE:", result.get("response_text"))
    print("INTAKE INDEX:", result.get("intake_index"))
    print("INTAKE ANSWERS:", result.get("intake_answers"))
    print(
        "REVIEW REQUIRED:",
        result.get("intake_review_required"),
    )

    return result


def main() -> None:
    graph = build_graph()

    db_session_id = create_db_session()

    config = {
        "configurable": {
            "thread_id": "intake-demo-001",
        }
    }

    invoke(
        graph,
        config,
        "I need to complete my pre-visit intake.",
        initial=True,
        db_session_id=db_session_id,
    )

    invoke(
        graph,
        config,
        "CARE-00001 and 1001",
    )

    answers = [
        "Routine follow-up",
        "No known allergies",
        "No current medications",
        "No previous major conditions",
        "No recent procedures",
        "No mobility assistance needed",
        "No interpreter needed",
        "Phone",
        "No transportation assistance needed",
        "Nothing else",
    ]

    for answer in answers:
        invoke(
            graph,
            config,
            answer,
        )

    invoke(
        graph,
        config,
        "yes",
    )


if __name__ == "__main__":
    main()
