from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.confirmation import consume_confirmation_token
from apps.api.dependencies import get_db, require_verified_session
from apps.api.schemas import (
    AppointmentActionRequest,
    AppointmentAvailabilityItem,
    AppointmentRescheduleRequest,
)
from db.models import (
    Appointment,
    Clinician,
    IdempotencyRecord,
)

router = APIRouter(
    prefix="/appointments",
    tags=["appointments"],
)


@router.get(
    "/availability",
    response_model=list[AppointmentAvailabilityItem],
)
def get_availability(
        session_id: int,
        patient_id: int,
        specialty: str,
        target_date: date = Query(...),
        db: Session = Depends(get_db),
) -> list[AppointmentAvailabilityItem]:
    require_verified_session(
        session_id=session_id,
        patient_id=patient_id,
        db=db,
    )

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
            Appointment.clinician_id == Clinician.id,
        )
        .where(
            Appointment.status == "available",
            Appointment.start_at >= day_start,
            Appointment.start_at <= day_end,
            Clinician.specialty == specialty,
        )
    )

    rows = db.execute(stmt).all()

    return [
        AppointmentAvailabilityItem(
            appointment_id=appointment.id,
            clinician_id=appointment.clinician_id,
            clinic_id=appointment.clinic_id,
            specialty=clinician.specialty,
            start_at=appointment.start_at,
        )
        for appointment, clinician in rows
    ]


@router.post("/book")
def book_appointment(
        payload: AppointmentActionRequest,
        db: Session = Depends(get_db),
) -> dict[str, object]:
    require_verified_session(
        session_id=payload.session_id,
        patient_id=payload.patient_id,
        db=db,
    )

    # ----------------------------------------------------
    # 1. ADDED: Idempotency Check (Top of Endpoint)
    # ----------------------------------------------------
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.key == payload.idempotency_key
        )
    )

    if existing is not None:
        return existing.result_json

    # 2. Consume Confirmation Tokens & Perform Booking Logic
    confirmed = consume_confirmation_token(
        token=payload.confirmation_token,
        session_id=payload.session_id,
        patient_id=payload.patient_id,
        appointment_id=payload.appointment_id,
        action="book",
    )

    if not confirmed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Valid confirmation required.",
        )

    appointment = db.get(
        Appointment,
        payload.appointment_id,
    )

    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    if appointment.status != "available":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Appointment is no longer available.",
        )

    appointment.patient_id = payload.patient_id
    appointment.status = "booked"

    # ----------------------------------------------------
    # 3. ADDED: Record Transaction & Save (Bottom of Endpoint)
    # ----------------------------------------------------
    result = {
        "success": True,
        "appointment_id": appointment.id,
    }

    db.add(
        IdempotencyRecord(
            key=payload.idempotency_key,
            action="book",
            result_json=result,
        )
    )

    db.commit()

    return result


@router.post("/cancel")
def cancel_appointment(
        payload: AppointmentActionRequest,
        db: Session = Depends(get_db),
) -> dict[str, object]:
    require_verified_session(
        session_id=payload.session_id,
        patient_id=payload.patient_id,
        db=db,
    )

    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.key == payload.idempotency_key
        )
    )

    if existing is not None:
        return existing.result_json

    confirmed = consume_confirmation_token(
        token=payload.confirmation_token,
        session_id=payload.session_id,
        patient_id=payload.patient_id,
        appointment_id=payload.appointment_id,
        action="cancel",
    )

    if not confirmed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Valid confirmation required.",
        )

    appointment = db.get(
        Appointment,
        payload.appointment_id,
    )

    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    if appointment.patient_id != payload.patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Appointment does not belong to verified patient.",
        )

    if appointment.status != "booked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only booked appointments can be cancelled.",
        )

    appointment.status = "cancelled"

    result = {
        "success": True,
        "appointment_id": appointment.id,
        "status": "cancelled",
    }

    db.add(
        IdempotencyRecord(
            key=payload.idempotency_key,
            action="cancel",
            result_json=result,
        )
    )

    db.commit()

    return result

@router.post("/reschedule")
def reschedule_appointment(
    payload: AppointmentRescheduleRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    require_verified_session(
        session_id=payload.session_id,
        patient_id=payload.patient_id,
        db=db,
    )

    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.key == payload.idempotency_key
        )
    )

    if existing is not None:
        return existing.result_json

    confirmed = consume_confirmation_token(
        token=payload.confirmation_token,
        session_id=payload.session_id,
        patient_id=payload.patient_id,
        appointment_id=payload.current_appointment_id,
        action="reschedule",
        target_appointment_id=payload.new_appointment_id,
    )

    if not confirmed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Valid confirmation required.",
        )

    current_appointment = db.get(
        Appointment,
        payload.current_appointment_id,
    )

    new_appointment = db.get(
        Appointment,
        payload.new_appointment_id,
    )

    if current_appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current appointment not found.",
        )

    if new_appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="New appointment not found.",
        )

    if current_appointment.patient_id != payload.patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current appointment does not belong to verified patient.",
        )

    if current_appointment.status != "booked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Current appointment is not booked.",
        )

    if new_appointment.status != "available":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="New appointment is no longer available.",
        )

    current_appointment.status = "rescheduled"

    new_appointment.patient_id = payload.patient_id
    new_appointment.status = "booked"

    result = {
        "success": True,
        "previous_appointment_id": current_appointment.id,
        "appointment_id": new_appointment.id,
    }

    db.add(
        IdempotencyRecord(
            key=payload.idempotency_key,
            action="reschedule",
            result_json=result,
        )
    )

    db.commit()

    return result
