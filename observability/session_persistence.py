from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from agent.state import CallState
from db.models import CallSession
from db.session import get_db_session

# =========================================================
# INTERNAL HELPERS
# =========================================================


def _utc_now_naive() -> datetime:
    """
    Store UTC consistently while remaining compatible
    with the project's existing timezone-naive DateTime
    database columns.
    """

    return (
        datetime.now(UTC)
        .replace(tzinfo=None)
    )


def _successful_tools(
    state: CallState,
) -> list[str]:
    tool_results = (
        state.get(
            "tool_results",
            [],
        )
        or []
    )

    return [
        str(result.get("tool"))
        for result in tool_results
        if (
            isinstance(result, dict)
            and result.get("success") is True
            and result.get("tool")
        )
    ]


def _infer_session_intent(
    state: CallState,
    existing_intent: str | None,
) -> str | None:
    """
    Preserve a meaningful business intent.

    Do not overwrite:
        appointment
        faq
        previsit_intake

    with terminal routing values such as:
        end_call
        unknown
    """

    current_intent = state.get(
        "intent"
    )

    if current_intent in {
        "appointment",
        "faq",
        "previsit_intake",
    }:
        return current_intent

    tools = set(
        _successful_tools(state)
    )

    if tools & {
        "book_appointment",
        "cancel_appointment",
        "reschedule_appointment",
    }:
        return "appointment"

    if (
        "store_previsit_intake"
        in tools
    ):
        return "previsit_intake"

    current_node = state.get(
        "current_node"
    )

    if current_node == "faq_search":
        return "faq"

    # Keep the useful intent already stored in DB rather
    # than replacing it with end_call / unknown / None.
    return existing_intent


def _infer_outcome(
    state: CallState,
) -> str | None:
    """
    Produce a compact machine-readable call outcome.
    """

    if state.get(
        "escalation_required",
        False,
    ):
        return "escalated"

    tools = _successful_tools(
        state
    )

    if tools:
        latest_tool = tools[-1]

        mapping = {
            "book_appointment":
                "appointment_booked",

            "cancel_appointment":
                "appointment_cancelled",

            "reschedule_appointment":
                "appointment_rescheduled",

            "store_previsit_intake":
                "intake_completed",
        }

        if latest_tool in mapping:
            return mapping[
                latest_tool
            ]

    if (
        state.get("call_ended", False)
    ):
        return "completed"

    return None


def _build_summary(
    state: CallState,
) -> dict[str, Any]:
    """
    Build a structured, privacy-conscious call summary.

    Do NOT save:
    - full transcripts
    - member IDs
    - phone numbers
    - hidden prompts
    """

    successful_tools = (
        _successful_tools(state)
    )

    return {
        "verified":
            state.get(
                "verified_patient_id"
            )
            is not None,

        "final_node":
            state.get(
                "current_node"
            ),

        "call_ended":
            bool(
                state.get(
                    "call_ended",
                    False,
                )
            ),

        "escalated":
            bool(
                state.get(
                    "escalation_required",
                    False,
                )
            ),

        "escalation_reason":
            state.get(
                "escalation_reason"
            ),

        "successful_tools":
            successful_tools,

        "appointment_action_completed":
            successful_tools[-1]
            if successful_tools
            else None,

        "intake_completed":
            (
                "store_previsit_intake"
                in successful_tools
            ),

        "conversation_turns":
            len(
                state.get(
                    "conversation",
                    [],
                )
                or []
            ),
    }


# =========================================================
# PERSIST CALL SESSION
# =========================================================


def persist_call_session(
    state: CallState,
    *,
    finalize: bool = False,
) -> None:
    """
    Synchronize LangGraph call state into CallSession.

    This function should never break the voice call if
    observability persistence itself fails.
    """

    db_session_id = state.get(
        "db_session_id"
    )

    if db_session_id is None:
        return

    try:
        with get_db_session() as db:
            call_session = db.get(
                CallSession,
                db_session_id,
            )

            if call_session is None:
                print(
                    "CALL SESSION NOT FOUND:",
                    db_session_id,
                )
                return

            verified_patient_id = (
                state.get(
                    "verified_patient_id"
                )
            )

            if verified_patient_id is not None:
                call_session.patient_id = (
                    verified_patient_id
                )

                call_session.verified_patient_id = (
                    verified_patient_id
                )

                call_session.verified = True

            call_session.intent = (
                _infer_session_intent(
                    state,
                    call_session.intent,
                )
            )

            outcome = _infer_outcome(
                state
            )

            if outcome is not None:
                call_session.outcome = outcome

            call_session.escalated = bool(
                state.get(
                    "escalation_required",
                    False,
                )
            )

            call_session.summary_json = (
                _build_summary(
                    state
                )
            )

            if (
                finalize
                or state.get(
                    "call_ended",
                    False,
                )
            ):
                call_session.ended_at = (
                    _utc_now_naive()
                )

                # A normal call with no tool mutation can
                # still finish successfully.
                if call_session.outcome is None:
                    call_session.outcome = (
                        "completed"
                    )

            db.commit()

    except Exception as exc: # noqa: BLE001
        print(
            "CALL SESSION PERSIST FAILED:",
            type(exc).__name__,
            str(exc),
        )
