from agent.state import CallState


def greeting_node(state: CallState) -> CallState:
    conversation = list(
        state.get("conversation", [])
    )

    response = (
        "Hello, I'm CareLine, the clinic's AI patient-services "
        "assistant. This demo uses synthetic patient data. "
        "How can I help you today?"
    )

    conversation.append(
        {
            "role": "assistant",
            "content": response,
        }
    )

    return {
        "conversation": conversation,
        "response_text": response,
        "current_node": "greeting",
        "greeted": True,
        "verification_attempts": state.get(
            "verification_attempts",
            0,
        ),
        "safety_flags": state.get(
            "safety_flags",
            [],
        ),
        "escalation_required": state.get(
            "escalation_required",
            False,
        ),
    }
