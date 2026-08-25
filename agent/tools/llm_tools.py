from langchain_core.tools import tool

from apps.api.services.appointments import (
    find_available_appointments,
)
from apps.api.services.faq import (
    search_approved_faq,
)
from db.session import get_db_session


@tool
def search_appointment_availability(
    specialty: str,
    date: str,
) -> list[dict]:
    """
    Search available appointment slots for a specialty
    and date.

    This tool does not book or modify appointments.
    """
    with get_db_session() as db:
        appointments = find_available_appointments(
            db=db,
            specialty=specialty,
            target_date=date,
        )

        return [
            {
                "appointment_id": appointment.id,
                "specialty": specialty,
                "date": str(appointment.start_time.date()),
                "time": appointment.start_time.strftime(
                    "%H:%M"
                ),
            }
            for appointment in appointments[:5]
        ]


@tool
def search_clinic_faq(
    query: str,
) -> list[dict]:
    """
    Search the approved clinic administrative FAQ knowledge.

    This tool must only return approved FAQ content.
    """
    with get_db_session() as db:
        results = search_approved_faq(
            db=db,
            query=query,
            limit=5,
        )

        return [
            {
                "question": item.question,
                "answer": item.approved_answer,
            }
            for item in results
        ]
