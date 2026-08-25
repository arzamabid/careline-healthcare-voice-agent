import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from agent.state import CallState
from agent.tools.appointments import (
    extract_appointment_fields,
)
from agent.tools.booked_appointments import (
    format_appointment_options,
    get_patient_booked_appointments,
    select_appointment_from_text,
)
from agent.tools.confirmation import (
    parse_confirmation,
)
from apps.api.confirmation import (
    consume_confirmation_token,
    create_confirmation_token,
)
from apps.api.services.appointments import (
    find_available_appointments,
)
from db.models import (
    Appointment,
    Clinician,
    IdempotencyRecord,
)
from db.session import get_db_session

# =========================================================
# DATE PARSING
# =========================================================


def parse_appointment_date(
    caller_text: str,
) -> str | None:
    """
    Parse common spoken/STT appointment dates.

    Supports:
        tomorrow
        after tomorrow
        day after tomorrow

        2026-08-27
        2026/08/27
        2026 08 27

        20260827

        20 26 08 27
        20, 26, 0, 8, 27

    Uses UTC consistently.
    """

    if not isinstance(caller_text, str):
        return None

    text = caller_text.lower().strip()
    today = datetime.now(UTC).date()

    # Relative dates
    if (
        "day after tomorrow" in text
        or "after tomorrow" in text
    ):
        parsed = today + timedelta(days=2)
        print("PARSED RELATIVE DATE:", parsed.isoformat())
        return parsed.isoformat()

    if "tomorrow" in text:
        parsed = today + timedelta(days=1)
        print("PARSED RELATIVE DATE:", parsed.isoformat())
        return parsed.isoformat()

    # YYYY-MM-DD / YYYY MM DD / YYYY/MM/DD
    match = re.search(
        r"\b"
        r"(\d{4})"
        r"[\s,./\-]+"
        r"(\d{1,2})"
        r"[\s,./\-]+"
        r"(\d{1,2})"
        r"\b",
        text,
    )

    if match:
        try:
            parsed = date(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
            )
            print("PARSED EXPLICIT DATE:", parsed.isoformat())
            return parsed.isoformat()
        except ValueError:
            pass

    # Compact YYYYMMDD
    compact_match = re.search(r"\b(20\d{6})\b", text)

    if compact_match:
        value = compact_match.group(1)
        try:
            parsed = date(
                int(value[0:4]),
                int(value[4:6]),
                int(value[6:8]),
            )
            print("PARSED COMPACT DATE:", parsed.isoformat())
            return parsed.isoformat()
        except ValueError:
            pass

    # Whisper split digits
    numeric_chunks = re.findall(r"\d+", text)
    joined_digits = "".join(numeric_chunks)

    print("DATE NUMERIC CHUNKS:", numeric_chunks)
    print("DATE JOINED DIGITS:", joined_digits)

    if len(joined_digits) == 8:
        try:
            parsed = date(
                int(joined_digits[0:4]),
                int(joined_digits[4:6]),
                int(joined_digits[6:8]),
            )
            print("PARSED JOINED DATE:", parsed.isoformat())
            return parsed.isoformat()
        except ValueError:
            pass

    print(
        "NO APPOINTMENT DATE PARSED FROM:",
        repr(caller_text),
    )
    return None


# =========================================================
# HELPERS
# =========================================================


def _normalise_appointment_text(
    caller_text: str,
) -> str:
    text = caller_text.lower().strip()

    # Common faster-whisper error: cancel -> council
    text = text.replace(
        "council my appointment",
        "cancel my appointment",
    )
    text = text.replace(
        "council an appointment",
        "cancel an appointment",
    )
    text = text.replace(
        "council appointment",
        "cancel appointment",
    )

    return text


def _determine_action(
    state: CallState,
    caller_text: str,
) -> str:
    text = _normalise_appointment_text(caller_text)

    if "cancel" in text:
        return "cancel"

    if (
        "reschedule" in text
        or "move my appointment" in text
        or "change my appointment" in text
    ):
        return "reschedule"

    existing_action = state.get("appointment_action")

    if existing_action in {
        "book",
        "cancel",
        "reschedule",
    }:
        return existing_action

    return "book"


def _explicit_specialty_from_text(
    caller_text: str,
) -> str | None:
    """
    Extract a specialty only when it is explicitly spoken in the
    CURRENT caller utterance.

    Important: short specialty names such as ENT must use word
    boundaries. A plain substring check would incorrectly match
    "ent" inside words such as "appointment".
    """

    if not isinstance(caller_text, str):
        return None

    text = caller_text.lower().strip()

    patterns = (
        (r"\bdermatology\b|\bdermatologist\b", "Dermatology"),
        (r"\bcardiology\b|\bcardiologist\b", "Cardiology"),
        (r"\bfamily medicine\b|\bfamily doctor\b", "Family Medicine"),
        (r"\borthopedics\b|\borthopedic\b|\borthopaedic\b", "Orthopedics"),
        (
            r"\bent\b|\bear nose and throat\b|\bear nose throat\b|\be\s*(?:&|and)\s*[dt]\b",
            "ENT",
        ),
    )

    for pattern, specialty in patterns:
        if re.search(pattern, text):
            return specialty

    return None


def _find_booked_appointment(
    patient_id: int,
    specialty: str | None,
):
    """
    Find the patient's currently booked appointment.

    If specialty is supplied, only return a booked appointment
    for that specialty.
    """

    with get_db_session() as db:
        appointments = list(
            db.scalars(
                select(Appointment)
                .where(
                    Appointment.patient_id == patient_id,
                    Appointment.status == "booked",
                )
                .order_by(Appointment.start_at)
            ).all()
        )

        for appointment in appointments:
            clinician = db.get(
                Clinician,
                appointment.clinician_id,
            )

            if clinician is None:
                continue

            if (
                specialty is None
                or clinician.specialty.lower()
                == specialty.lower()
            ):
                appointment_data = {
                    "id": appointment.id,
                    "clinician_id": appointment.clinician_id,
                    "clinic_id": appointment.clinic_id,
                    "start_at": appointment.start_at,
                    "status": appointment.status,
                }

                clinician_data = {
                    "name": clinician.name,
                    "specialty": clinician.specialty,
                }

                return appointment_data, clinician_data

    return None, None


# =========================================================
# APPOINTMENT ROUTER
# =========================================================


def appointment_router_node(
    state: CallState,
) -> CallState:
    conversation = list(
        state.get("conversation", [])
    )

    caller_text = state.get(
        "caller_text",
        "",
    )

    print(
        "APPOINTMENT ROUTER INPUT:",
        repr(caller_text),
    )

    # -------------------------------------------------
    # Allow caller to abandon an unfinished appointment
    # workflow. Do this BEFORE determining the old action,
    # otherwise phrases such as "no thanks" inherit
    # appointment_action="reschedule" and loop forever.
    # -------------------------------------------------

    normalized_for_exit = (
        caller_text
        .lower()
        .strip()
        .replace(",", "")
        .replace(".", "")
    )

    appointment_exit_phrases = {
        "nothing else",
        "nothing more",
        "no thanks",
        "no thank you",
        "never mind",
        "nevermind",
        "forget it",
        "stop",
        "thats all",
        "that is all",
    }

    should_exit_appointment = any(
        normalized_for_exit == phrase
        or normalized_for_exit.startswith(phrase + " ")
        for phrase in appointment_exit_phrases
    )

    if (
        not state.get(
            "confirmation_required",
            False,
        )
        and should_exit_appointment
    ):
        response = (
            "Okay. I won't make any further appointment changes. "
            "Thank you for calling Careline. Have a good day. Goodbye."
        )

        conversation.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        return {
            "current_node": "appointment_router",
            "active_workflow": None,
            "intent": "end_call",
            "appointment_action": None,
            "appointment_specialty": None,
            "appointment_date": None,
            "selected_appointment_id": None,
            "pending_confirmation": None,
            "confirmation_required": False,
            "confirmation_received": False,
            "confirmation_token": None,
            "awaiting_more_help": False,
            "call_ended": True,
            "response_text": response,
            "conversation": conversation,
        }

    action = _determine_action(
        state,
        caller_text,
    )

    print(
        "DETECTED APPOINTMENT ACTION:",
        action,
    )

    extracted = extract_appointment_fields(
        state
    )

    print(
        "EXTRACTED APPOINTMENT FIELDS:",
        extracted,
    )

    # -------------------------------------------------
    # Specialty
    # -------------------------------------------------

    explicit_specialty = (
        _explicit_specialty_from_text(
            caller_text
        )
    )

    normalized_text = (
        _normalise_appointment_text(
            caller_text
        )
    )

    starts_new_cancel = (
        "cancel" in normalized_text
    )

    starts_new_reschedule = (
        "reschedule" in normalized_text
        or "change my appointment" in normalized_text
        or "move my appointment" in normalized_text
    )

    if action in {
        "cancel",
        "reschedule",
    }:
        if explicit_specialty is not None:
            specialty = explicit_specialty
        elif (
            starts_new_cancel
            or starts_new_reschedule
        ):
            # New cancel/reschedule request with no explicitly
            # spoken specialty. Never reuse stale specialty.
            specialty = None
        else:
            # Continuation of current workflow, e.g. after the
            # caller already said "Cardiology" and now says
            # "tomorrow".
            specialty = state.get(
                "appointment_specialty"
            )
    else:
        specialty = (
            explicit_specialty
            or state.get(
                "appointment_specialty"
            )
        )

        # # LLM extraction is allowed only for booking.
        # if specialty is None:
        #     specialty = extracted.get(
        #         "specialty"
        #     )

    # -------------------------------------------------
    # Date
    # -------------------------------------------------

    newly_parsed_date = (
        parse_appointment_date(
            caller_text
        )
    )

    if newly_parsed_date is not None:
        target_date = newly_parsed_date
        print(
            "USING NEW CALLER DATE:",
            target_date,
        )
    else:
        target_date = (
            extracted.get("target_date")
            or state.get("appointment_date")
        )

    print(
        "FINAL APPOINTMENT SPECIALTY:",
        specialty,
    )
    print(
        "FINAL APPOINTMENT DATE:",
        target_date,
    )

    # =================================================
    # CANCEL
    # =================================================

    if action == "cancel":
        patient_id = state.get(
            "verified_patient_id"
        )

        if patient_id is None:
            return {
                "current_node":
                    "appointment_router",

                "response_text": (
                    "I need to verify your identity before "
                    "accessing booked appointments."
                ),
            }

        appointment_stage = state.get(
            "appointment_stage"
        )

        appointment_options = list(
            state.get(
                "appointment_options",
                [],
            )
            or []
        )

        # -------------------------------------------------
        # STEP 1:
        # Generic cancellation request.
        # Show the patient's appointments.
        # -------------------------------------------------

        if (
                specialty is None
                and appointment_stage
                != "select_existing"
        ):
            appointment_options = (
                get_patient_booked_appointments(
                    patient_id
                )
            )

            if not appointment_options:
                response = (
                    "I couldn't find any booked appointments "
                    "for you. Is there anything else I can "
                    "help you with?"
                )

                conversation.append(
                    {
                        "role": "assistant",
                        "content": response,
                    }
                )

                return {
                    "current_node":
                        "appointment_router",

                    "active_workflow":
                        None,

                    "appointment_action":
                        None,

                    "appointment_stage":
                        None,

                    "appointment_options":
                        [],

                    "awaiting_more_help":
                        True,

                    "response_text":
                        response,

                    "conversation":
                        conversation,
                }

            options_text = (
                format_appointment_options(
                    appointment_options
                )
            )

            response = (
                f"I found {len(appointment_options)} "
                f"booked appointment"
                f"{'s' if len(appointment_options) != 1 else ''}. "
                f"{options_text} "
                "Which appointment would you like to cancel? "
                "You can say first, second, third, "
                "or say the specialty."
            )

            conversation.append(
                {
                    "role": "assistant",
                    "content": response,
                }
            )

            return {
                "current_node":
                    "appointment_router",

                "active_workflow":
                    "appointment",

                "appointment_action":
                    "cancel",

                "appointment_stage":
                    "select_existing",

                "appointment_options":
                    appointment_options,

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

                "response_text":
                    response,

                "conversation":
                    conversation,
            }

        # -------------------------------------------------
        # STEP 2:
        # Caller is choosing from the list.
        # -------------------------------------------------

        if (
                appointment_stage
                == "select_existing"
        ):
            selected = (
                select_appointment_from_text(
                    caller_text,
                    appointment_options,
                )
            )

            if selected is None:
                options_text = (
                    format_appointment_options(
                        appointment_options
                    )
                )

                response = (
                    "I didn't catch which appointment you "
                    "want to cancel. "
                    f"{options_text} "
                    "Please say first, second, third, "
                    "or the specialty."
                )

                conversation.append(
                    {
                        "role": "assistant",
                        "content": response,
                    }
                )

                return {
                    "current_node":
                        "appointment_router",

                    "active_workflow":
                        "appointment",

                    "appointment_action":
                        "cancel",

                    "appointment_stage":
                        "select_existing",

                    "appointment_options":
                        appointment_options,

                    "response_text":
                        response,

                    "conversation":
                        conversation,
                }

            appointment_id = selected[
                "appointment_id"
            ]

            specialty = selected[
                "specialty"
            ]

            start_at = datetime.fromisoformat(
                selected["start_at"]
            )

            response = (
                f"You selected your {specialty} "
                f"appointment with "
                f"{selected['clinician_name']} on "
                f"{start_at.strftime('%Y-%m-%d')} at "
                f"{start_at.strftime('%I:%M %p')}. "
                "Would you like me to cancel this appointment?"
            )

            conversation.append(
                {
                    "role": "assistant",
                    "content": response,
                }
            )

            return {
                "current_node":
                    "appointment_router",

                "active_workflow":
                    "appointment",

                "appointment_action":
                    "cancel",

                "appointment_stage":
                    None,

                "appointment_options":
                    [],

                "appointment_specialty":
                    specialty,

                "selected_appointment_id":
                    appointment_id,

                "pending_confirmation": {
                    "action":
                        "cancel",

                    "appointment_id":
                        appointment_id,

                    "specialty":
                        specialty,

                    "start_at":
                        selected["start_at"],
                },

                "confirmation_required":
                    True,

                "confirmation_received":
                    False,

                "response_text":
                    response,

                "conversation":
                    conversation,
            }

        # -------------------------------------------------
        # Explicit specialty in original request.
        #
        # Example:
        # "Cancel my Cardiology appointment."
        #
        # We can still directly resolve this.
        # -------------------------------------------------

        appointment, clinician = (
            _find_booked_appointment(
                patient_id=patient_id,
                specialty=specialty,
            )
        )

        if appointment is None:
            response = (
                f"I couldn't find a booked "
                f"{specialty} appointment for you."
            )

            return {
                "active_workflow":
                    None,

                "appointment_action":
                    None,

                "appointment_stage":
                    None,

                "response_text":
                    response,

                "awaiting_more_help":
                    True,

                "current_node":
                    "appointment_router",
            }

        appointment_id = appointment["id"]
        start_at = appointment["start_at"]

        response = (
            f"You want to cancel your "
            f"{clinician['specialty']} appointment with "
            f"{clinician['name']} on "
            f"{start_at.strftime('%Y-%m-%d')} at "
            f"{start_at.strftime('%I:%M %p')}. "
            "Would you like me to cancel it?"
        )

        return {
            "current_node":
                "appointment_router",

            "active_workflow":
                "appointment",

            "appointment_action":
                "cancel",

            "appointment_stage":
                None,

            "appointment_options":
                [],

            "appointment_specialty":
                clinician["specialty"],

            "selected_appointment_id":
                appointment_id,

            "pending_confirmation": {
                "action":
                    "cancel",

                "appointment_id":
                    appointment_id,

                "specialty":
                    clinician["specialty"],

                "start_at":
                    start_at.isoformat(),
            },

            "confirmation_required":
                True,

            "confirmation_received":
                False,

            "response_text":
                response,
        }

    # =================================================
    # RESCHEDULE
    # =================================================

    if action == "reschedule":
        patient_id = state.get(
            "verified_patient_id"
        )

        if patient_id is None:
            return {
                "current_node":
                    "appointment_router",

                "response_text": (
                    "I need to verify your identity before "
                    "accessing booked appointments."
                ),
            }

        appointment_stage = state.get(
            "appointment_stage"
        )

        appointment_options = list(
            state.get(
                "appointment_options",
                [],
            )
            or []
        )

        # -------------------------------------------------
        # STEP 1:
        # Show current booked appointments.
        # -------------------------------------------------

        if (
                specialty is None
                and appointment_stage
                != "select_existing"
        ):
            appointment_options = (
                get_patient_booked_appointments(
                    patient_id
                )
            )

            if not appointment_options:
                response = (
                    "I couldn't find any booked appointments "
                    "for you. Is there anything else I can "
                    "help you with?"
                )

                return {
                    "current_node":
                        "appointment_router",

                    "active_workflow":
                        None,

                    "appointment_action":
                        None,

                    "appointment_stage":
                        None,

                    "appointment_options":
                        [],

                    "awaiting_more_help":
                        True,

                    "response_text":
                        response,
                }

            options_text = (
                format_appointment_options(
                    appointment_options
                )
            )

            response = (
                f"I found {len(appointment_options)} "
                f"booked appointment"
                f"{'s' if len(appointment_options) != 1 else ''}. "
                f"{options_text} "
                "Which appointment would you like to reschedule? "
                "You can say first, second, third, "
                "or say the specialty."
            )

            conversation.append(
                {
                    "role": "assistant",
                    "content": response,
                }
            )

            return {
                "current_node":
                    "appointment_router",

                "active_workflow":
                    "appointment",

                "appointment_action":
                    "reschedule",

                "appointment_stage":
                    "select_existing",

                "appointment_options":
                    appointment_options,

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

                "response_text":
                    response,

                "conversation":
                    conversation,
            }

        # -------------------------------------------------
        # STEP 2:
        # Caller chooses existing appointment.
        # -------------------------------------------------

        if (
                appointment_stage
                == "select_existing"
        ):
            selected = (
                select_appointment_from_text(
                    caller_text,
                    appointment_options,
                )
            )

            if selected is None:
                options_text = (
                    format_appointment_options(
                        appointment_options
                    )
                )

                response = (
                    "I didn't catch which appointment you "
                    "want to reschedule. "
                    f"{options_text} "
                    "Please say first, second, third, "
                    "or the specialty."
                )

                return {
                    "current_node":
                        "appointment_router",

                    "active_workflow":
                        "appointment",

                    "appointment_action":
                        "reschedule",

                    "appointment_stage":
                        "select_existing",

                    "appointment_options":
                        appointment_options,

                    "response_text":
                        response,
                }

            appointment_id = selected[
                "appointment_id"
            ]

            specialty = selected[
                "specialty"
            ]

            start_at = datetime.fromisoformat(
                selected["start_at"]
            )

            response = (
                f"You selected your {specialty} "
                f"appointment with "
                f"{selected['clinician_name']} on "
                f"{start_at.strftime('%Y-%m-%d')} at "
                f"{start_at.strftime('%I:%M %p')}. "
                "What new date would you prefer?"
            )

            conversation.append(
                {
                    "role": "assistant",
                    "content": response,
                }
            )

            return {
                "current_node":
                    "appointment_router",

                "active_workflow":
                    "appointment",

                "appointment_action":
                    "reschedule",

                "appointment_stage":
                    "select_new_date",

                "appointment_options":
                    [],

                "appointment_specialty":
                    specialty,

                "appointment_date":
                    None,

                # Existing appointment that will be moved.
                "selected_appointment_id":
                    appointment_id,

                "pending_confirmation": {
                    "action":
                        "reschedule_select_date",

                    "old_appointment_id":
                        appointment_id,
                },

                "confirmation_required":
                    False,

                "confirmation_received":
                    False,

                "response_text":
                    response,

                "conversation":
                    conversation,
            }

        # -------------------------------------------------
        # STEP 3:
        # Existing appointment already selected.
        # Collect the new date.
        # -------------------------------------------------

        if (
                appointment_stage
                == "select_new_date"
        ):
            old_appointment_id = (
                state.get(
                    "selected_appointment_id"
                )
            )

            specialty = state.get(
                "appointment_specialty"
            )

            if target_date is None:
                response = (
                    f"What new date would you prefer "
                    f"for your {specialty} appointment?"
                )

                return {
                    "current_node":
                        "appointment_router",

                    "active_workflow":
                        "appointment",

                    "appointment_action":
                        "reschedule",

                    "appointment_stage":
                        "select_new_date",

                    "appointment_specialty":
                        specialty,

                    "appointment_date":
                        None,

                    "selected_appointment_id":
                        old_appointment_id,

                    "response_text":
                        response,
                }

            return {
                "current_node":
                    "appointment_router",

                "active_workflow":
                    "appointment",

                "appointment_action":
                    "reschedule",

                "appointment_stage":
                    "search_new_slot",

                "appointment_specialty":
                    specialty,

                "appointment_date":
                    target_date,

                "selected_appointment_id":
                    old_appointment_id,

                "pending_confirmation": {
                    "action":
                        "reschedule_search",

                    "old_appointment_id":
                        old_appointment_id,
                },

                "confirmation_required":
                    False,

                "confirmation_received":
                    False,
            }

        # -------------------------------------------------
        # Explicit specialty request.
        #
        # Example:
        # "Reschedule my Cardiology appointment."
        # -------------------------------------------------

        old_appointment, clinician = (
            _find_booked_appointment(
                patient_id=patient_id,
                specialty=specialty,
            )
        )

        if old_appointment is None:
            response = (
                f"I couldn't find a booked "
                f"{specialty} appointment for you."
            )

            return {
                "active_workflow":
                    None,

                "appointment_action":
                    None,

                "appointment_stage":
                    None,

                "awaiting_more_help":
                    True,

                "response_text":
                    response,

                "current_node":
                    "appointment_router",
            }

        old_id = old_appointment["id"]

        if target_date is None:
            response = (
                f"I found your {specialty} appointment "
                f"with {clinician['name']} on "
                f"{old_appointment['start_at'].strftime('%Y-%m-%d')} "
                f"at "
                f"{old_appointment['start_at'].strftime('%I:%M %p')}. "
                "What new date would you prefer?"
            )

            return {
                "current_node":
                    "appointment_router",

                "active_workflow":
                    "appointment",

                "appointment_action":
                    "reschedule",

                "appointment_stage":
                    "select_new_date",

                "appointment_specialty":
                    specialty,

                "appointment_date":
                    None,

                "selected_appointment_id":
                    old_id,

                "pending_confirmation": {
                    "action":
                        "reschedule_select_date",

                    "old_appointment_id":
                        old_id,
                },

                "confirmation_required":
                    False,

                "confirmation_received":
                    False,

                "response_text":
                    response,
            }

        return {
            "current_node":
                "appointment_router",

            "active_workflow":
                "appointment",

            "appointment_action":
                "reschedule",

            "appointment_stage":
                "search_new_slot",

            "appointment_specialty":
                specialty,

            "appointment_date":
                target_date,

            "selected_appointment_id":
                old_id,

            "pending_confirmation": {
                "action":
                    "reschedule_search",

                "old_appointment_id":
                    old_id,
            },

            "confirmation_required":
                False,

            "confirmation_received":
                False,
        }

    # =================================================
    # BOOK
    # =================================================

    if specialty is None:
        response = (
            "Which specialty would you like "
            "the appointment for?"
        )

        conversation.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        return {
            "current_node": "appointment_router",
            "active_workflow": "appointment",
            "appointment_action": "book",
            "appointment_specialty": None,
            "appointment_date": None,
            "response_text": response,
            "conversation": conversation,
        }

    if target_date is None:
        response = (
            f"What date would you prefer "
            f"for {specialty}?"
        )

        conversation.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        return {
            "current_node": "appointment_router",
            "active_workflow": "appointment",
            "appointment_action": "book",
            "appointment_specialty": specialty,
            "appointment_date": None,
            "response_text": response,
            "conversation": conversation,
        }

    return {
        "current_node": "appointment_router",
        "active_workflow": "appointment",
        "appointment_action": "book",
        "appointment_specialty": specialty,
        "appointment_date": target_date,
    }


def _appointment_from_options(
    appointment_id: int,
    options: list[dict],
) -> dict | None:
    for option in options:
        if (
            option.get(
                "appointment_id"
            )
            == appointment_id
        ):
            return option

    return None


# =========================================================
# SEARCH AVAILABILITY
# =========================================================
def search_availability_node(
    state: CallState,
) -> CallState:
    action = state.get(
        "appointment_action",
        "book",
    )

    specialty = state.get(
        "appointment_specialty"
    )

    appointment_date = state.get(
        "appointment_date"
    )

    if (
        specialty is None
        or appointment_date is None
    ):
        return {
            "current_node": "search_availability",
            "response_text": (
                "I still need the specialty and date."
            ),
        }

    target_date = date.fromisoformat(
        appointment_date
    )

    db = get_db_session()

    conversation = list(
        state.get("conversation", [])
    )

    db = get_db_session()

    try:
        results = find_available_appointments(
            db=db,
            specialty=specialty,
            target_date=target_date,
            db_session_id=state.get(
                "db_session_id"
            ),
        )

    except Exception: # noqa: BLE001
        response = (
            "I'm sorry, I couldn't check appointment "
            "availability right now. "
            "Please try again later or I can help route "
            "you to human assistance."
        )

        conversation.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        tool_results = list(
            state.get(
                "tool_results",
                [],
            )
            or []
        )

        tool_results.append(
            {
                "tool":
                    "find_available_appointments",
                "success":
                    False,
                "error":
                    "appointment_service_unavailable",
            }
        )

        return {
            "current_node":
                "search_availability",

            "intent":
                "appointment",

            "active_workflow":
                "appointment",

            "appointment_action":
                action,

            "appointment_specialty":
                specialty,

            "appointment_date":
                appointment_date,

            "confirmation_required":
                False,

            "confirmation_received":
                False,

            "response_text":
                response,

            "conversation":
                conversation,

            "tool_results":
                tool_results,
        }

    finally:
        db.close()

    if not results:
        response = (
            f"I couldn't find an available "
            f"{specialty} appointment on "
            f"{appointment_date}. "
            "Please give me another date."
        )

        conversation.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        return {
            "current_node": "search_availability",
            "active_workflow": "appointment",
            "appointment_action": action,
            "appointment_specialty": specialty,
            "appointment_date": None,
            "confirmation_required": False,
            "confirmation_received": False,
            "response_text": response,
            "conversation": conversation,
        }

    appointment, clinician = results[0]

    # RESCHEDULE SEARCH RESULT
    if action == "reschedule":
        old_appointment_id = state.get(
            "selected_appointment_id"
        )

        if old_appointment_id is None:
            return {
                "current_node": "search_availability",
                "response_text": (
                    "I couldn't identify the appointment "
                    "that should be rescheduled."
                ),
            }

        response = (
            f"I found a new {specialty} slot with "
            f"{clinician.name} at "
            f"{appointment.start_at.strftime('%I:%M %p')} "
            f"on {appointment.start_at.strftime('%Y-%m-%d')}. "
            "Would you like me to reschedule your "
            "appointment to this slot?"
        )

        conversation.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        return {
            "current_node": "search_availability",
            "active_workflow": "appointment",
            "appointment_action": "reschedule",
            # selected_appointment_id becomes the NEW slot.
            "selected_appointment_id": appointment.id,
            "pending_confirmation": {
                "action": "reschedule",
                "old_appointment_id": old_appointment_id,
                "new_appointment_id": appointment.id,
                "specialty": specialty,
                "start_at": appointment.start_at.isoformat(),
            },
            "confirmation_required": True,
            "confirmation_received": False,
            "response_text": response,
            "conversation": conversation,
        }

    # NORMAL BOOK SEARCH RESULT
    response = (
        f"I found {specialty} with "
        f"{clinician.name} at "
        f"{appointment.start_at.strftime('%I:%M %p')} "
        f"on {appointment.start_at.strftime('%Y-%m-%d')}. "
        "Would you like me to book this appointment?"
    )

    conversation.append(
        {
            "role": "assistant",
            "content": response,
        }
    )

    return {
        "current_node": "search_availability",
        "active_workflow": "appointment",
        "appointment_action": "book",
        "selected_appointment_id": appointment.id,
        "pending_confirmation": {
            "action": "book",
            "appointment_id": appointment.id,
            "specialty": specialty,
            "start_at": appointment.start_at.isoformat(),
        },
        "confirmation_required": True,
        "confirmation_received": False,
        "response_text": response,
        "conversation": conversation,
    }


# =========================================================
# CONFIRMATION
# =========================================================


def confirm_appointment_action_node(
    state: CallState,
) -> CallState:
    caller_text = state.get(
        "caller_text",
        "",
    )

    print(
        "APPOINTMENT CONFIRMATION:",
        repr(caller_text),
    )

    decision = parse_confirmation(
        caller_text
    )

    print(
        "APPOINTMENT CONFIRMATION RESULT:",
        decision,
    )

    if decision == "yes":
        return {
            "confirmation_received": True,
            "confirmation_required": False,
            # Keep pending_confirmation; execution needs it.
            "current_node": "confirm_appointment_action",
            "response_text": (
                "Thank you. I'll proceed with "
                "the confirmed appointment action."
            ),
        }

    if decision == "no":
        return {
            "confirmation_received": False,
            "confirmation_required": False,
            "confirmation_token": None,
            "pending_confirmation": None,
            "active_workflow": None,
            # "appointment_action": None,
            # "appointment_specialty": None,
            # "appointment_date": None,
            # "selected_appointment_id": None,
            "appointment_stage":
                None,

            "appointment_options":
                [],
            "intent": None,
            "awaiting_more_help": True,
            "call_ended": False,
            "response_text": (
                "Okay. I won't make that appointment change. "
                "Is there anything else I can help you with?"
            ),
            "current_node": "confirm_appointment_action",
        }

    return {
        "confirmation_received": False,
        "confirmation_required": True,
        "response_text": (
            "Please confirm the appointment action "
            "with yes or no."
        ),
        "current_node": "confirm_appointment_action",
    }


# =========================================================
# EXECUTE WRITE
# =========================================================


def execute_appointment_action_node(
    state: CallState,
) -> CallState:
    if not state.get(
        "confirmation_received",
        False,
    ):
        return {
            "current_node": "execute_appointment_action",
            "response_text": (
                "Appointment confirmation is required."
            ),
        }

    patient_id = state.get(
        "verified_patient_id"
    )

    pending = (
        state.get("pending_confirmation")
        or {}
    )

    action = pending.get("action")

    session_id = str(
        state.get("session_id", "")
    )

    if patient_id is None:
        return {
            "current_node": "execute_appointment_action",
            "response_text": (
                "I cannot safely complete the appointment "
                "because the patient is not verified."
            ),
        }

    # =================================================
    # BOOK
    # =================================================

    if action == "book":
        appointment_id = pending.get(
            "appointment_id"
        )

        if appointment_id is None:
            return {
                "current_node": "execute_appointment_action",
                "response_text": (
                    "I cannot safely identify the "
                    "appointment to book."
                ),
            }

        token = create_confirmation_token(
            session_id=session_id,
            patient_id=patient_id,
            appointment_id=appointment_id,
            action="book",
        )

        db = get_db_session()

        try:
            confirmed = consume_confirmation_token(
                token=token,
                session_id=session_id,
                patient_id=patient_id,
                appointment_id=appointment_id,
                action="book",
            )

            if not confirmed:
                return {
                    "current_node": "execute_appointment_action",
                    "response_text": (
                        "The appointment confirmation "
                        "could not be validated."
                    ),
                }

            appointment = db.get(
                Appointment,
                appointment_id,
            )

            if appointment is None:
                return {
                    "current_node": "execute_appointment_action",
                    "response_text": (
                        "The appointment could not be found."
                    ),
                }

            if appointment.status != "available":
                return {
                    "current_node": "execute_appointment_action",
                    "response_text": (
                        "That appointment is no longer available."
                    ),
                }

            appointment.patient_id = patient_id
            appointment.status = "booked"

            idempotency_key = (
                f"graph-book-{session_id}-{appointment_id}"
            )

            existing = db.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.key
                    == idempotency_key
                )
            )

            if existing is None:
                db.add(
                    IdempotencyRecord(
                        key=idempotency_key,
                        action="book",
                        result_json={
                            "success": True,
                            "appointment_id": appointment_id,
                        },
                    )
                )

            db.commit()

        finally:
            db.close()

        response = (
            "Your appointment has been booked successfully."
        )

        result = {
            "tool": "book_appointment",
            "success": True,
            "appointment_id": appointment_id,
        }

    # =================================================
    # CANCEL
    # =================================================

    elif action == "cancel":
        appointment_id = pending.get(
            "appointment_id"
        )

        if appointment_id is None:
            return {
                "current_node": "execute_appointment_action",
                "response_text": (
                    "I cannot safely identify the "
                    "appointment to cancel."
                ),
            }

        token = create_confirmation_token(
            session_id=session_id,
            patient_id=patient_id,
            appointment_id=appointment_id,
            action="cancel",
        )

        db = get_db_session()

        try:
            confirmed = consume_confirmation_token(
                token=token,
                session_id=session_id,
                patient_id=patient_id,
                appointment_id=appointment_id,
                action="cancel",
            )

            if not confirmed:
                return {
                    "current_node": "execute_appointment_action",
                    "response_text": (
                        "The cancellation confirmation "
                        "could not be validated."
                    ),
                }

            appointment = db.get(
                Appointment,
                appointment_id,
            )

            if appointment is None:
                return {
                    "current_node": "execute_appointment_action",
                    "response_text": (
                        "The appointment could not be found."
                    ),
                }

            if (
                appointment.patient_id != patient_id
                or appointment.status != "booked"
            ):
                return {
                    "current_node": "execute_appointment_action",
                    "response_text": (
                        "That booked appointment could "
                        "not be cancelled."
                    ),
                }

            appointment.patient_id = None
            appointment.status = "available"

            idempotency_key = (
                f"graph-cancel-{session_id}-{appointment_id}"
            )

            existing = db.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.key
                    == idempotency_key
                )
            )

            if existing is None:
                db.add(
                    IdempotencyRecord(
                        key=idempotency_key,
                        action="cancel",
                        result_json={
                            "success": True,
                            "appointment_id": appointment_id,
                        },
                    )
                )

            db.commit()

        finally:
            db.close()

        response = (
            "Your appointment has been cancelled successfully."
        )

        result = {
            "tool": "cancel_appointment",
            "success": True,
            "appointment_id": appointment_id,
        }

    # =================================================
    # RESCHEDULE
    # =================================================

    elif action == "reschedule":
        old_appointment_id = pending.get(
            "old_appointment_id"
        )
        new_appointment_id = pending.get(
            "new_appointment_id"
        )

        if (
            old_appointment_id is None
            or new_appointment_id is None
        ):
            return {
                "current_node": "execute_appointment_action",
                "response_text": (
                    "I cannot safely identify both "
                    "appointments for the reschedule."
                ),
            }

        token = create_confirmation_token(
            session_id=session_id,
            patient_id=patient_id,
            appointment_id=new_appointment_id,
            action="reschedule",
        )

        db = get_db_session()

        try:
            confirmed = consume_confirmation_token(
                token=token,
                session_id=session_id,
                patient_id=patient_id,
                appointment_id=new_appointment_id,
                action="reschedule",
            )

            if not confirmed:
                return {
                    "current_node": "execute_appointment_action",
                    "response_text": (
                        "The reschedule confirmation "
                        "could not be validated."
                    ),
                }

            old_appointment = db.get(
                Appointment,
                old_appointment_id,
            )
            new_appointment = db.get(
                Appointment,
                new_appointment_id,
            )

            if (
                old_appointment is None
                or new_appointment is None
            ):
                return {
                    "current_node": "execute_appointment_action",
                    "response_text": (
                        "One of the appointment slots "
                        "could not be found."
                    ),
                }

            if (
                old_appointment.patient_id != patient_id
                or old_appointment.status != "booked"
            ):
                return {
                    "current_node": "execute_appointment_action",
                    "response_text": (
                        "The original appointment is "
                        "no longer booked for this patient."
                    ),
                }

            if new_appointment.status != "available":
                return {
                    "current_node": "execute_appointment_action",
                    "response_text": (
                        "The new appointment slot is "
                        "no longer available."
                    ),
                }

            # Release old slot and book new slot in the same
            # transaction.
            old_appointment.patient_id = None
            old_appointment.status = "available"

            new_appointment.patient_id = patient_id
            new_appointment.status = "booked"

            idempotency_key = (
                f"graph-reschedule-"
                f"{session_id}-"
                f"{old_appointment_id}-"
                f"{new_appointment_id}"
            )

            existing = db.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.key
                    == idempotency_key
                )
            )

            if existing is None:
                db.add(
                    IdempotencyRecord(
                        key=idempotency_key,
                        action="reschedule",
                        result_json={
                            "success": True,
                            "old_appointment_id": old_appointment_id,
                            "new_appointment_id": new_appointment_id,
                        },
                    )
                )

            db.commit()

        finally:
            db.close()

        response = (
            "Your appointment has been rescheduled successfully."
        )

        result = {
            "tool": "reschedule_appointment",
            "success": True,
            "old_appointment_id": old_appointment_id,
            "new_appointment_id": new_appointment_id,
        }

    else:
        return {
            "current_node": "execute_appointment_action",
            "response_text": (
                "I couldn't identify the confirmed "
                "appointment action."
            ),
        }

    # =================================================
    # SUCCESS
    # =================================================

    conversation = list(
        state.get("conversation", [])
    )

    conversation.append(
        {
            "role": "assistant",
            "content": response,
        }
    )

    return {
        "current_node": "execute_appointment_action",
        "active_workflow": None,
        "confirmation_required": False,
        "confirmation_received": True,
        "pending_confirmation": None,
        # "appointment_action": None,
        # "appointment_specialty": None,
        # "appointment_date": None,
        # "selected_appointment_id": None,
        "appointment_stage":
            None,

        "appointment_options":
            [],
        "response_text": response,
        "conversation": conversation,
        "tool_results": [
            *state.get("tool_results", []),
            result,
        ],
    }