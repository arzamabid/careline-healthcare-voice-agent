from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.dependencies import (
    get_db,
    require_verified_session,
)
from apps.api.schemas import IntakeRequest, IntakeResponse
from db.models import IntakeRecord

router = APIRouter(
    prefix="/intake",
    tags=["intake"],
)


@router.post(
    "",
    response_model=IntakeResponse,
)
def store_intake(
    payload: IntakeRequest,
    db: Session = Depends(get_db),
) -> IntakeResponse:
    require_verified_session(
        session_id=payload.session_id,
        patient_id=payload.patient_id,
        db=db,
    )

    if not payload.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Intake must be reviewed and confirmed before storage.",
        )

    record = IntakeRecord(
        session_id=payload.session_id,
        patient_id=payload.patient_id,
        answers_json=payload.answers,
        confirmed=True,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return IntakeResponse(
        success=True,
        intake_id=record.id,
    )
