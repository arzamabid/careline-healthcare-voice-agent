from agent.graph import graph


def main() -> None:
    config = {
        "configurable": {
            "thread_id": "demo-session-001",
        }
    }

    initial_state = {
        "session_id": "demo-session-001",
        "caller_text": (
        #     "I would like to book an appointment."
        # "What time does the clinic open?"
        #     "I'm having chest pain and I can't breathe."
            "Can you diagnose what is wrong with me?"
        ),
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
    }

    result = graph.invoke(
        initial_state,
        config=config,
    )

    print()
    print("Current node:")
    print(result["current_node"])

    print()
    print("Intent:")
    print(result["intent"])

    print()
    print("Response:")
    print(result["response_text"])

    print()
    print("Conversation:")
    for message in result["conversation"]:
        print(
            f"{message['role']}: "
            f"{message['content']}"
        )


if __name__ == "__main__":
    main()
