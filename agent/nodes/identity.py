from typing import Any

from sqlalchemy import select

from agent.state import CallState
from agent.tools.identity import extract_identity_fields
from db.models import Patient
from db.session import get_db_session

MAX_VERIFICATION_ATTEMPTS = 3


def identity_check_node(
    state: CallState,
) -> CallState:
    """
    Verify the synthetic patient using:

        member_id
        +
        phone_last4

    Important behavior:

    - Remember a correctly extracted field across turns.
    - Ask only for whichever identifier is missing.
    - Do not count an incomplete utterance as a failed
      identity-verification attempt.
    - Only count a failure when both identifiers are present
      but do not match a patient.
    - Preserve the caller's original appointment request
      while identity verification happens.
    """

    caller_text = state.get(
        "caller_text",
        "",
    )

    print(
        "IDENTITY CALLER TEXT:",
        repr(caller_text),
        type(caller_text),
    )

    # =================================================
    # Preserve original appointment request
    #
    # Example:
    #
    # "I want to cancel my appointment."
    #
    # Identity verification happens after this.
    # Once verified, appointment_router should receive
    # the original request, NOT the member-ID utterance.
    # =================================================

    original_request_text = state.get(
        "original_request_text"
    )

    if (
        not original_request_text
        and state.get("intent") == "appointment"
    ):
        original_request_text = caller_text

        print(
            "SAVING ORIGINAL REQUEST:",
            repr(original_request_text),
        )

    # -------------------------------------------------
    # Existing fields from previous turns
    # -------------------------------------------------

    existing_fields: dict[str, Any] = (
        state.get(
            "verification_fields",
            {},
        )
        or {}
    )

    # -------------------------------------------------
    # Extract anything available in this turn
    # -------------------------------------------------

    extracted_fields: dict[str, str] = {}

    if isinstance(
        caller_text,
        str,
    ):
        extracted_fields = (
            extract_identity_fields(
                caller_text
            )
        )

    print(
        "EXTRACTED IDENTITY FIELDS:",
        extracted_fields,
    )

    # Keep information already captured previously.
    verification_fields = {
        **existing_fields,
        **extracted_fields,
    }

    print(
        "COMBINED IDENTITY FIELDS:",
        verification_fields,
    )

    member_id = verification_fields.get(
        "member_id"
    )

    phone_last4 = verification_fields.get(
        "phone_last4"
    )

    # =================================================
    # BOTH ARE MISSING
    # =================================================

    if (
        not member_id
        and not phone_last4
    ):
        return {
            "verification_fields":
                verification_fields,

            "identity_status":
                "needs_identifiers",

            "original_request_text":
                original_request_text,

            "response_text": (
                "Before I access patient-specific information, "
                "please provide your demo member ID and the "
                "last four digits of your phone number."
            ),

            "current_node":
                "identity_check",
        }

    # =================================================
    # MEMBER ID EXISTS, PHONE IS MISSING
    # =================================================

    if (
        member_id
        and not phone_last4
    ):
        print(
            "IDENTITY MEMBER ID CAPTURED:",
            member_id,
        )

        return {
            # IMPORTANT:
            # retain the valid member ID for the next turn
            "verification_fields":
                verification_fields,

            "identity_status":
                "needs_phone_last4",

            "original_request_text":
                original_request_text,

            "response_text": (
                "I have your member ID. "
                "I didn't get all four phone digits. "
                "Please provide the last four digits "
                "of your phone number, one digit at a time."
            ),

            "current_node":
                "identity_check",
        }

    # =================================================
    # PHONE EXISTS, MEMBER ID IS MISSING
    # =================================================

    if (
        phone_last4
        and not member_id
    ):
        print(
            "IDENTITY PHONE CAPTURED:",
            phone_last4,
        )

        return {
            # Keep the phone digits for the next turn.
            "verification_fields":
                verification_fields,

            "identity_status":
                "needs_member_id",

            "original_request_text":
                original_request_text,

            "response_text": (
                "I have the last four digits of your phone "
                "number. Please provide your demo member ID."
            ),

            "current_node":
                "identity_check",
        }

    # =================================================
    # BOTH IDENTIFIERS ARE AVAILABLE
    # =================================================

    print(
        "ATTEMPTING IDENTITY VERIFICATION:",
        {
            "member_id": member_id,
            "phone_last4": phone_last4,
        },
    )

    with get_db_session() as db:
        statement = (
            select(Patient)
            .where(
                Patient.member_id
                == member_id,

                Patient.phone_last4
                == phone_last4,
            )
        )

        patient = db.scalar(
            statement
        )

        patient_id = (
            patient.id
            if patient
            else None
        )

    # =================================================
    # VERIFIED
    # =================================================

    if patient_id is not None:
        print(
            "IDENTITY VERIFIED:",
            patient_id,
        )

        restored_caller_text = (
            original_request_text
            or caller_text
        )

        print(
            "RESTORING ORIGINAL REQUEST:",
            repr(restored_caller_text),
        )

        return {
            "verified_patient_id":
                patient_id,

            "verification_fields":
                verification_fields,

            "identity_status":
                "verified",

            "original_request_text":
                original_request_text,

            # Important:
            # send the ORIGINAL request back into the
            # appointment workflow after verification.
            "caller_text":
                restored_caller_text,

            "response_text": (
                "Thank you. Your identity has been verified."
            ),

            "current_node":
                "identity_check",
        }

    # =================================================
    # BOTH WERE PRESENT BUT DID NOT MATCH
    # =================================================

    attempts = (
        state.get(
            "verification_attempts",
            0,
        )
        + 1
    )

    print(
        "IDENTITY VERIFICATION FAILED. ATTEMPT:",
        attempts,
    )

    # -------------------------------------------------
    # Maximum failed attempts
    # -------------------------------------------------

    if attempts >= MAX_VERIFICATION_ATTEMPTS:
        return {
            "verified_patient_id":
                None,

            "verification_attempts":
                attempts,

            # Clear potentially incorrect values.
            "verification_fields":
                {},

            "identity_status":
                "failed_max",

            "original_request_text":
                original_request_text,

            "escalation_required":
                True,

            "safety_flags": (
                list(
                    state.get(
                        "safety_flags",
                        [],
                    )
                    or []
                )
                + [
                    "identity_verification_failed_max"
                ]
            ),

            "response_text": (
                "I wasn't able to verify your identity "
                "after three attempts. "
                "I'll need to escalate this request "
                "for human assistance."
            ),

            "current_node":
                "identity_check",
        }

    # -------------------------------------------------
    # Failed match, retry both identifiers.
    #
    # We clear both here because we do NOT know which
    # of the two supplied values was incorrect.
    # -------------------------------------------------

    return {
        "verified_patient_id":
            None,

        "verification_attempts":
            attempts,

        "verification_fields":
            {},

        "identity_status":
            "failed_retry",

        "original_request_text":
            original_request_text,

        "response_text": (
            "I couldn't verify those details. "
            "Please try again with your demo member ID "
            "and the last four digits of your phone number."
        ),

        "current_node":
            "identity_check",
    }