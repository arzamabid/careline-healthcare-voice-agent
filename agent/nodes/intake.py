from agent.state import CallState
from agent.tools.confirmation import parse_confirmation
from agent.tools.intake import INTAKE_QUESTIONS
from db.models import IntakeRecord
from db.session import get_db_session
from observability.tracing import trace_tool


def _spoken_intake_value(
    value: str | None,
) -> str:
    """
    Convert short intake answers into natural speech.

    This avoids TTS reading:

        "No."

    as something like:

        "Number."
    """

    if value is None:
        return "not provided"

    normalized = (
        value
        .strip()
        .lower()
        .rstrip(".,;:")
    )

    if normalized in {
        "no",
        "nope",
        "none",
        "no thanks",
        "no thank you",
    }:
        return "none"

    if normalized in {
        "yes",
        "yeah",
        "yep",
        "yup",
    }:
        return "yes"

    return (
        value
        .strip()
        .rstrip(".,;:")
    )


@trace_tool(
    "store_previsit_intake"
)
def store_intake_node(
    state: CallState,
    db_session_id: int | None = None
) -> CallState:
    db_session_id = state.get(
        "db_session_id"
    ),
    """
    Save confirmed pre-visit intake information.
    """

    print(
        "===== STORE INTAKE ENTERED ====="
    )

    print(
        "STORE PATIENT ID:",
        state.get(
            "verified_patient_id"
        ),
    )

    print(
        "STORE DB SESSION ID:",
        state.get(
            "db_session_id"
        ),
    )

    print(
        "INTAKE CONFIRMED:",
        state.get(
            "intake_confirmed"
        ),
    )

    if not state.get(
        "intake_confirmed",
        False,
    ):
        return {
            "current_node":
                "store_intake",

            "response_text": (
                "Intake confirmation is required."
            ),
        }

    patient_id = state.get(
        "verified_patient_id"
    )

    if patient_id is None:
        return {
            "current_node":
                "store_intake",

            "escalation_required":
                True,

            "response_text": (
                "I cannot safely save the intake "
                "without a verified patient."
            ),
        }

    # -------------------------------------------------
    # Database call-session ID
    # -------------------------------------------------

    db_session_id = state.get(
        "db_session_id"
    )

    if db_session_id is None:
        return {
            "current_node":
                "store_intake",

            "escalation_required":
                True,

            "response_text": (
                "The session could not be identified."
            ),
        }

    intake_answers = dict(
        state.get(
            "intake_answers",
            {},
        )
    )

    db = get_db_session()

    try:
        record = IntakeRecord(
            session_id=db_session_id,
            patient_id=patient_id,
            answers_json=intake_answers,
            confirmed=True,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        print(
            "INTAKE RECORD SAVED:",
            record.id,
        )

        record_id = record.id

    finally:
        db.close()

    conversation = list(
        state.get(
            "conversation",
            [],
        )
    )

    response = (
        "Your pre-visit intake information "
        "has been saved successfully."
    )

    conversation.append(
        {
            "role": "assistant",
            "content": response,
        }
    )

    return {
        "intake_confirmed":
            True,

        "intake_review_required":
            False,

        # Intake workflow is complete.
        "active_workflow":
            None,

        # Remove stale intent.
        "intent":
            None,

        "confirmation_required":
            False,

        "confirmation_received":
            False,

        "pending_confirmation":
            None,

        "confirmation_token":
            None,

        "tool_results": [
            *state.get(
                "tool_results",
                [],
            ),
            {
                "tool":
                    "store_previsit_intake",

                "success":
                    True,

                "patient_id":
                    patient_id,

                "intake_record_id":
                    record_id,
            },
        ],

        "response_text":
            response,

        "conversation":
            conversation,

        "current_node":
            "store_intake",
    }


def previsit_intake_node(
    state: CallState,
) -> CallState:
    """
    Ask deterministic pre-visit intake questions
    one at a time.
    """

    conversation = list(
        state.get(
            "conversation",
            [],
        )
    )

    answers = dict(
        state.get(
            "intake_answers",
            {},
        )
    )

    index = state.get(
        "intake_index",
        0,
    )

    active_workflow = state.get(
        "active_workflow"
    )

    # =================================================
    # First entry into intake
    # =================================================

    if (
        active_workflow
        != "previsit_intake"
    ):
        index = 0
        answers = {}

    # =================================================
    # Save answer from previous question
    # =================================================

    if (
        active_workflow
        == "previsit_intake"
        and index > 0
    ):
        previous_field = (
            INTAKE_QUESTIONS[
                index - 1
            ][0]
        )

        # Only store if this field has not already
        # been captured.
        if previous_field not in answers:
            caller_answer = (
                state.get(
                    "caller_text",
                    "",
                )
                .strip()
            )

            answers[
                previous_field
            ] = caller_answer

    # =================================================
    # All questions completed
    # =================================================

    if index >= len(
        INTAKE_QUESTIONS
    ):
        return {
            "current_node":
                "previsit_intake",

            "active_workflow":
                "previsit_intake",

            "intake_answers":
                answers,

            "intake_index":
                index,

            "intake_review_required":
                True,
        }

    # =================================================
    # Ask next question
    # =================================================

    _field_name, question = (
        INTAKE_QUESTIONS[
            index
        ]
    )

    conversation.append(
        {
            "role": "assistant",
            "content": question,
        }
    )

    return {
        "current_node":
            "previsit_intake",

        "active_workflow":
            "previsit_intake",

        "intake_answers":
            answers,

        "intake_index":
            index + 1,

        "response_text":
            question,

        "conversation":
            conversation,
    }


def review_intake_node(
    state: CallState,
) -> CallState:
    """
    Read the captured intake back in natural spoken form
    and request explicit confirmation.
    """

    intake_answers = dict(
        state.get(
            "intake_answers",
            {},
        )
    )

    conversation = list(
        state.get(
            "conversation",
            [],
        )
    )

    if not intake_answers:
        response = (
            "I don't have any intake answers "
            "to review."
        )

        return {
            "current_node":
                "review_intake",

            "response_text":
                response,
        }

    # =================================================
    # Convert values for TTS
    # =================================================

    reason = _spoken_intake_value(
        intake_answers.get(
            "reason_for_visit"
        )
    )

    allergies = _spoken_intake_value(
        intake_answers.get(
            "allergies"
        )
    )

    medications = _spoken_intake_value(
        intake_answers.get(
            "current_medications"
        )
    )

    previous_conditions = (
        _spoken_intake_value(
            intake_answers.get(
                "previous_conditions"
            )
        )
    )

    recent_procedures = (
        _spoken_intake_value(
            intake_answers.get(
                "recent_procedures"
            )
        )
    )

    mobility_support = (
        _spoken_intake_value(
            intake_answers.get(
                "mobility_support"
            )
        )
    )

    interpreter_needed = (
        _spoken_intake_value(
            intake_answers.get(
                "interpreter_needed"
            )
        )
    )

    contact_preference = (
        _spoken_intake_value(
            intake_answers.get(
                "contact_preference"
            )
        )
    )

    transportation_support = (
        _spoken_intake_value(
            intake_answers.get(
                "transportation_support"
            )
        )
    )

    additional_notes = (
        _spoken_intake_value(
            intake_answers.get(
                "additional_notes"
            )
        )
    )

    # =================================================
    # Natural spoken summary
    # =================================================

    response = (
        "Here is the intake information I collected. "

        f"Reason for visit: {reason}. "

        f"Known allergies: {allergies}. "

        f"Current medications: {medications}. "

        f"Previous medical conditions: "
        f"{previous_conditions}. "

        f"Recent procedures or surgeries: "
        f"{recent_procedures}. "

        f"Mobility support needed: "
        f"{mobility_support}. "

        f"Interpreter needed: "
        f"{interpreter_needed}. "

        f"Preferred contact method: "
        f"{contact_preference}. "

        f"Transportation support needed: "
        f"{transportation_support}. "

        f"Additional notes: "
        f"{additional_notes}. "

        "Is this information correct?"
    )

    conversation.append(
        {
            "role": "assistant",
            "content": response,
        }
    )

    return {
        "current_node":
            "review_intake",

        "active_workflow":
            "previsit_intake",

        "intake_review_required":
            False,

        "confirmation_required":
            True,

        "confirmation_received":
            False,

        "intake_confirmed":
            False,

        "pending_confirmation": {
            "action":
                "confirm_intake",
        },

        "awaiting_more_help":
            False,

        "call_ended":
            False,

        "response_text":
            response,

        "conversation":
            conversation,
    }


def confirm_intake_node(
    state: CallState,
) -> CallState:
    """
    Handle explicit confirmation of the reviewed
    pre-visit intake information.
    """

    caller_text = state.get(
        "caller_text",
        "",
    )

    print(
        "INTAKE CONFIRMATION:",
        repr(caller_text),
    )

    decision = parse_confirmation(
        caller_text
    )

    print(
        "INTAKE CONFIRMATION RESULT:",
        decision,
    )

    # =================================================
    # YES
    # =================================================

    if decision == "yes":
        return {
            "intake_confirmed":
                True,

            "confirmation_received":
                True,

            "confirmation_required":
                False,

            "intake_review_required":
                False,

            # Keep intake active until store_intake_node
            # has actually written the record.
            "active_workflow":
                "previsit_intake",

            "response_text": (
                "Thank you. I'll save your "
                "pre-visit intake information."
            ),

            "current_node":
                "confirm_intake",
        }

    # =================================================
    # NO
    # =================================================

    if decision == "no":
        return {
            "intake_confirmed":
                False,

            "confirmation_received":
                False,

            "confirmation_required":
                False,

            "intake_review_required":
                False,

            "pending_confirmation":
                None,

            "confirmation_token":
                None,

            "active_workflow":
                None,

            "intent":
                None,

            "awaiting_more_help":
                True,

            "response_text": (
                "Okay. I won't save the intake "
                "information as confirmed. "
                "Is there anything else "
                "I can help you with?"
            ),

            "current_node":
                "confirm_intake",
        }

    # =================================================
    # UNKNOWN
    # =================================================

    return {
        "intake_confirmed":
            False,

        "confirmation_received":
            False,

        "confirmation_required":
            True,

        "intake_review_required":
            False,

        "active_workflow":
            "previsit_intake",

        "pending_confirmation": {
            "action":
                "confirm_intake",
        },

        "awaiting_more_help":
            False,

        "call_ended":
            False,

        "response_text": (
            "Please confirm whether the intake "
            "information is correct with yes or no."
        ),

        "current_node":
            "confirm_intake",
    }