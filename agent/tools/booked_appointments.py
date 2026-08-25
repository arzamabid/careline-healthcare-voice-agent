from typing import Any

from sqlalchemy import select

from db.models import Appointment, Clinician
from db.session import get_db_session

# =========================================================
# GET BOOKED APPOINTMENTS
# =========================================================


def get_patient_booked_appointments(
    patient_id: int,
) -> list[dict[str, Any]]:
    """
    Return all booked appointments for a verified patient.

    Only plain Python dictionaries are returned so that no
    SQLAlchemy ORM objects remain attached to a closed DB
    session.
    """

    results: list[dict[str, Any]] = []

    with get_db_session() as db:
        appointments = list(
            db.scalars(
                select(Appointment)
                .where(
                    Appointment.patient_id
                    == patient_id,

                    Appointment.status
                    == "booked",
                )
                .order_by(
                    Appointment.start_at
                )
            ).all()
        )

        for appointment in appointments:
            clinician = db.get(
                Clinician,
                appointment.clinician_id,
            )

            if clinician is None:
                continue

            results.append(
                {
                    "appointment_id":
                        appointment.id,

                    "clinician_id":
                        appointment.clinician_id,

                    "clinic_id":
                        appointment.clinic_id,

                    "clinician_name":
                        clinician.name,

                    "specialty":
                        clinician.specialty,

                    "start_at":
                        appointment.start_at.isoformat(),

                    "status":
                        appointment.status,
                }
            )

    return results


# =========================================================
# FORMAT APPOINTMENTS FOR VOICE
# =========================================================


def format_appointment_options(
    appointments: list[dict[str, Any]],
) -> str:
    """
    Convert booked appointments to natural spoken text.
    """

    if not appointments:
        return ""

    lines: list[str] = []

    number_words = {
        1: "First",
        2: "Second",
        3: "Third",
        4: "Fourth",
        5: "Fifth",
        6: "Sixth",
        7: "Seventh",
        8: "Eighth",
        9: "Ninth",
        10: "Tenth",
    }

    from datetime import datetime

    for index, appointment in enumerate(
        appointments,
        start=1,
    ):
        start_at = datetime.fromisoformat(
            appointment["start_at"]
        )

        position = number_words.get(
            index,
            f"Number {index}",
        )

        lines.append(
            f"{position}: "
            f"{appointment['specialty']} with "
            f"{appointment['clinician_name']} on "
            f"{start_at.strftime('%Y-%m-%d')} at "
            f"{start_at.strftime('%I:%M %p')}."
        )

    return " ".join(lines)


# =========================================================
# SELECT APPOINTMENT
# =========================================================


def select_appointment_from_text(
    caller_text: str,
    appointments: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Select one booked appointment from natural speech.

    Supports:
        first
        first one
        number one
        appointment one
        1

        second
        second one
        number two
        2

        Cardiology
        my cardiology appointment

        ENT
        family medicine
        etc.
    """

    if not caller_text:
        return None

    if not appointments:
        return None

    text = (
        caller_text
        .lower()
        .strip()
        .replace(",", "")
        .replace(".", "")
    )

    # -----------------------------------------------------
    # Position selection
    # -----------------------------------------------------

    position_phrases = {
        0: {
            "1",
            "one",
            "first",
            "first one",
            "number one",
            "number 1",
            "appointment one",
            "appointment 1",
            "the first",
            "the first one",
        },

        1: {
            "2",
            "two",
            "second",
            "second one",
            "number two",
            "number 2",
            "appointment two",
            "appointment 2",
            "the second",
            "the second one",
        },

        2: {
            "3",
            "three",
            "third",
            "third one",
            "number three",
            "number 3",
            "appointment three",
            "appointment 3",
            "the third",
            "the third one",
        },

        3: {
            "4",
            "four",
            "fourth",
            "fourth one",
            "number four",
            "number 4",
            "appointment four",
            "appointment 4",
        },

        4: {
            "5",
            "five",
            "fifth",
            "fifth one",
            "number five",
            "number 5",
            "appointment five",
            "appointment 5",
        },
    }

    for index, phrases in position_phrases.items():
        if (
            index < len(appointments)
            and (
                text in phrases
                or any(
                    phrase in text
                    for phrase in phrases
                    if len(phrase) > 3
                )
            )
        ):
            return appointments[index]

    # -----------------------------------------------------
    # Specialty selection
    # -----------------------------------------------------

    matching_specialties = []

    for appointment in appointments:
        specialty = str(
            appointment.get(
                "specialty",
                "",
            )
        )

        if (
            specialty
            and specialty.lower() in text
        ):
            matching_specialties.append(
                appointment
            )

    # Safe only when exactly one booked appointment
    # matches the requested specialty.
    if len(matching_specialties) == 1:
        return matching_specialties[0]

    # ENT needs word-style handling because we must not
    # accidentally match "ent" inside "appointment".
    words = set(
        text
        .replace("-", " ")
        .split()
    )

    if "ent" in words:
        ent_matches = [
            appointment
            for appointment in appointments
            if (
                str(
                    appointment.get(
                        "specialty",
                        "",
                    )
                ).lower()
                == "ent"
            )
        ]

        if len(ent_matches) == 1:
            return ent_matches[0]

    return None
