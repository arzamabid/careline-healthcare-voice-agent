from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Appointment, Clinician
from observability.tracing import trace_tool


@trace_tool(
    "find_available_appointments"
)
def find_available_appointments(
    db: Session,
    specialty: str,
    target_date: date,
    db_session_id: int | None = None,
) -> list[tuple[Appointment, Clinician]]:
    day_start = datetime.combine(
        target_date,
        time.min,
    )

    day_end = datetime.combine(
        target_date,
        time.max,
    )

    stmt = (
        select(Appointment, Clinician)
        .join(
            Clinician,
            Appointment.clinician_id
            == Clinician.id,
        )
        .where(
            Appointment.status == "available",
            Appointment.start_at >= day_start,
            Appointment.start_at <= day_end,
            Clinician.specialty == specialty,
        )
        .order_by(Appointment.start_at)
    )

    return list(
        db.execute(stmt).all()
    )
