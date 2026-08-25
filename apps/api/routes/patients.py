from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from apps.api.schemas import (
    PatientVerificationRequest,
    PatientVerificationResponse,
)
from apps.api.services.patients import (
    verify_patient_identifiers,
)
from db.models import CallSession

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post(
    "/verify",
    response_model=PatientVerificationResponse,
)
def verify_patient(
        payload: PatientVerificationRequest,
        db: Session = Depends(get_db),
) -> PatientVerificationResponse:
    # ----------------------------------------------------
    # 1. ADDED: Validate the session exists first
    # ----------------------------------------------------
    call_session = db.get(
        CallSession,
        payload.session_id,
    )

    if call_session is None:
        return PatientVerificationResponse(
            verified=False,
            patient_id=None,
            message="Session not found.",
        )

    # 2. Extract filtering payload fields
    supplied_fields = {
        key: value
        for key, value in payload.model_dump().items()
        if value is not None and key != "session_id"  # Exclude session_id from filtering Patient columns
    }

    if len(supplied_fields) < 2:
        return PatientVerificationResponse(
            verified=False,
            patient_id=None,
            message="At least two identifiers are required.",
        )

    # 3. Query the patient database table
    # stmt = select(Patient)
    #
    # for field_name, value in supplied_fields.items():
    #     stmt = stmt.where(
    #         getattr(Patient, field_name) == value
    #     )
    #
    # patient = db.scalar(stmt)
    
    identifiers = {
        key: value
        for key, value in payload.model_dump(
            exclude={"session_id"}
        ).items()
        if value is not None
    }

    if len(identifiers) < 2:
        return PatientVerificationResponse(
            verified=False,
            patient_id=None,
            message="At least two identifiers are required.",
        )

    patient = verify_patient_identifiers(
        db=db,
        identifiers=identifiers,
    )

    if patient is None:
        return PatientVerificationResponse(
            verified=False,
            patient_id=None,
            message="Identity could not be verified.",
        )


    if patient is None:
        return PatientVerificationResponse(
            verified=False,
            patient_id=None,
            message="Identity could not be verified.",
        )

    # ----------------------------------------------------
    # 4. ADDED: Update the session on success
    # ----------------------------------------------------
    call_session.verified = True
    call_session.verified_patient_id = patient.id

    db.commit()

    # 5. Return success
    return PatientVerificationResponse(
        verified=True,
        patient_id=patient.id,
        message="Identity verified.",
    )
