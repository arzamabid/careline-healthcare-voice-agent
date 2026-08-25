import re

# from agent.llm.response import generate_patient_response
from agent.state import CallState


def wrap_up_node(
        state: CallState,
) -> CallState:
    """
    Deterministic wrap-up after completed administrative
    actions.
    """

    tool_results = list(
        state.get(
            "tool_results",
            [],
        )
        or []
    )

    print(
        "WRAP UP TOOL RESULTS:",
        tool_results,
    )

    # -------------------------------------------------
    # Look through ALL successful tools instead of only
    # trusting the final list item.
    # -------------------------------------------------

    completed_tools = {
        result.get("tool")
        for result in tool_results
        if result.get(
            "success",
            True,
        )
    }

    latest_successful_tool = None

    for result in reversed(tool_results):
        if result.get("success") is True:
            latest_successful_tool = result.get("tool")
            break

    print(
        "WRAP UP LATEST SUCCESSFUL TOOL:",
        latest_successful_tool,
    )

    print(
        "WRAP UP COMPLETED TOOLS:",
        completed_tools,
    )

    # =================================================
    # Pre-visit intake completed
    # =================================================

    if (
            "store_previsit_intake"
            in completed_tools
    ):
        return {
            "response_text": (
                "Your pre-visit intake information "
                "has been saved successfully. "
                "Is there anything else "
                "I can help you with?"
            ),

            "active_workflow":
                None,

            "intent":
                None,

            "awaiting_more_help":
                True,

            "call_ended":
                False,

            "current_node":
                "wrap_up",
        }

    # =================================================
    # Appointment booked
    # =================================================

    if latest_successful_tool == "book_appointment":
        return {
            "response_text": (
                "Your appointment has been booked successfully. "
                "Is there anything else I can help you with?"
            ),

            "active_workflow": None,
            "intent": None,

            # Clear old booking request state so a new
            # appointment does not reuse the old specialty/date.
            "appointment_action": None,
            "appointment_specialty": None,
            "appointment_date": None,

            # Keep selected_appointment_id because FAQ questions
            # may need to refer to the appointment just booked.

            "pending_confirmation": None,
            "confirmation_required": False,
            "confirmation_received": False,
            "confirmation_token": None,

            "awaiting_more_help": True,
            "call_ended": False,

            "current_node": "wrap_up",
        }

    if latest_successful_tool == "cancel_appointment":
        return {
            "response_text": (
                "Your appointment has been cancelled successfully. "
                "Is there anything else I can help you with?"
            ),

            "active_workflow":
                None,

            "intent":
                None,

            "appointment_action":
                None,

            "appointment_specialty":
                None,

            "appointment_date":
                None,

            "selected_appointment_id":
                None,

            "pending_confirmation":
                None,

            "confirmation_required":
                False,

            "confirmation_received":
                False,

            "confirmation_token":
                None,

            "awaiting_more_help":
                True,

            "call_ended":
                False,

            "current_node":
                "wrap_up",
        }

    if latest_successful_tool == "reschedule_appointment":
        return {
            "response_text": (
                "Your appointment has been rescheduled successfully. "
                "Is there anything else I can help you with?"
            ),

            "active_workflow":
                None,

            "intent":
                None,

            "appointment_action":
                None,

            "appointment_specialty":
                None,

            "appointment_date":
                None,

            "selected_appointment_id":
                None,

            "pending_confirmation":
                None,

            "confirmation_required":
                False,

            "confirmation_received":
                False,

            "confirmation_token":
                None,

            "awaiting_more_help":
                True,

            "call_ended":
                False,

            "current_node":
                "wrap_up",
        }

    # =================================================
    # Safe deterministic fallback
    #
    # Do NOT ask the LLM to invent a completion message.
    # =================================================

    print(
        "WARNING: WRAP UP DID NOT FIND "
        "A COMPLETED ACTION"
    )

    return {
        "response_text": (
            "I've finished processing that request. "
            "Is there anything else "
            "I can help you with?"
        ),

        "active_workflow":
            None,

        "intent":
            None,

        "awaiting_more_help":
            True,

        "call_ended":
            False,

        "current_node":
            "wrap_up",
    }


def _normalize_text(
        text: str,
) -> str:
    normalized = re.sub(
        r"[^a-zA-Z0-9\s]",
        "",
        text.lower(),
    )

    return " ".join(
        normalized.split()
    )


def _remove_affirmative_prefix(
        caller_text: str,
) -> str:
    """
    Convert:

        "Yes, what time does the clinic close?"

    into:

        "what time does the clinic close?"
    """

    text = caller_text.strip()

    patterns = [
        r"^\s*yes\s+please[,\s]+",
        r"^\s*yes[,\s]+",
        r"^\s*yeah[,\s]+",
        r"^\s*yep[,\s]+",
        r"^\s*yup[,\s]+",
        r"^\s*sure[,\s]+",
        r"^\s*okay[,\s]+",
        r"^\s*ok[,\s]+",
    ]

    for pattern in patterns:
        updated = re.sub(
            pattern,
            "",
            text,
            count=1,
            flags=re.IGNORECASE,
        )

        if updated != text:
            return updated.strip()

    return text


def closing_decision_node(
        state: CallState,
) -> CallState:
    """
    Handle the caller's response to:

        "Is there anything else I can help you with?"
    """

    caller_text = state.get(
        "caller_text",
        "",
    )

    print(
        "CLOSING TRANSCRIPT:",
        repr(caller_text),
    )

    normalized = _normalize_text(
        caller_text
    )

    # =================================================
    # Closing phrases
    # =================================================

    closing_responses = {
        "no",
        "nope",
        "nah",

        "no thanks",
        "no thank you",

        "okay thanks",
        "okay thank you",
        "ok thanks",
        "ok thank you",

        "alright thanks",
        "alright thank you",

        "nothing",
        "nothing else",
        "nothing more",

        "thats all",
        "that is all",
        "thats it",
        "that is it",

        "no thats all",
        "no that is all",
        "no thats it",
        "no that is it",

        "im good",
        "i am good",
        "all good",

        "thanks",
        "thank you",

        "thanks bye",
        "thank you bye",

        "thanks goodbye",
        "thank you goodbye",

        "bye",
        "goodbye",
        "good bye",
    }

    closing_prefixes = (
        "no thanks",
        "no thank you",

        "nothing else",
        "nothing more",

        "thank you",
        "thanks",

        "okay thank you",
        "okay thanks",
        "ok thank you",
        "ok thanks",

        "alright thank you",
        "alright thanks",

        "thats all",
        "that is all",
    )

    is_closing = (
            normalized in closing_responses
            or normalized.startswith(
        closing_prefixes
    )
    )

    # =================================================
    # Caller is finished
    # =================================================

    if is_closing:
        return {
            "awaiting_more_help": False,
            "call_ended": True,

            "intent": "end_call",
            "active_workflow": None,

            "pending_confirmation": None,
            "confirmation_required": False,
            "confirmation_received": False,
            "confirmation_token": None,

            "response_text": (
                "You're welcome. "
                "Thank you for calling Careline. "
                "Have a good day. Goodbye."
            ),

            "current_node":
                "closing_decision",
        }

    # =================================================
    # Caller has another request
    # =================================================

    new_request_text = (
        _remove_affirmative_prefix(
            caller_text
        )
    )

    print(
        "NEW REQUEST AFTER CLOSING:",
        repr(new_request_text),
    )

    return {
        "awaiting_more_help": False,
        "call_ended": False,

        # The previous workflow is finished.
        "intent": None,
        "active_workflow": None,

        # Classify this as a brand-new request.
        "caller_text": new_request_text,

        # Don't accidentally replay the old response.
        "response_text": "",

        "current_node":
            "closing_decision",
    }


def finalize_call_node(
        state: CallState,
) -> CallState:
    """
    Build a small final summary after the caller
    finishes the conversation.
    """

    tool_results = state.get(
        "tool_results",
        [],
    ) or []

    summary = {
        "completed_actions": len(
            tool_results
        ),

        "escalated": state.get(
            "escalation_required",
            False,
        ),

        "final_intent": state.get(
            "intent",
        ),
    }

    return {
        "call_summary": summary,
        "call_ended": True,
        "current_node": "finalize_call",
    }
