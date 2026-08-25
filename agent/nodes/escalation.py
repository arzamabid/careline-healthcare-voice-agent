from agent.state import CallState


def escalation_node(
    state: CallState,
) -> CallState:
    """
    End the automated workflow after escalation.

    Once this node is reached, Careline should not
    continue normal patient-service processing.
    """

    return {
        "response_text": (
            "I'm unable to safely continue this request. "
            "I'll route it for human assistance. "
            "Thank you for calling Careline."
        ),

        # Keep the reason recorded.
        "escalation_required": True,

        # Stop any active business workflow.
        "active_workflow": None,
        "intent": "escalation",

        # Clear pending confirmations.
        "pending_confirmation": None,
        "confirmation_required": False,
        "confirmation_received": False,
        "confirmation_token": None,

        # Do not route into anything-else flow.
        "awaiting_more_help": False,

        # Important:
        # this conversation is finished.
        "call_ended": True,

        "current_node": "escalation",
    }