from fastapi import APIRouter

from apps.api.confirmation import create_confirmation_token
from apps.api.schemas import (
    ConfirmationTokenRequest,
    ConfirmationTokenResponse,
)

router = APIRouter(
    prefix="/dev",
    tags=["development"],
)


@router.post(
    "/confirmation-token",
    response_model=ConfirmationTokenResponse,
)
def issue_confirmation_token(
    payload: ConfirmationTokenRequest,
) -> ConfirmationTokenResponse:
    token = create_confirmation_token(
        session_id=payload.session_id,
        patient_id=payload.patient_id,
        appointment_id=payload.appointment_id,
        action=payload.action,
        target_appointment_id=payload.target_appointment_id,
    )

    return ConfirmationTokenResponse(
        confirmation_token=token,
    )
