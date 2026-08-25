from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionCreateResponse(BaseModel):
    session_id: int


class PatientVerificationRequest(BaseModel):
    session_id:int

    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    phone_last4: str | None = None
    member_id: str | None = None


class PatientVerificationResponse(BaseModel):
    verified: bool
    patient_id: int | None = None
    message: str


class AppointmentAvailabilityItem(BaseModel):
    appointment_id: int
    clinician_id: int
    clinic_id: int
    specialty: str
    start_at: datetime


class AppointmentActionRequest(BaseModel):
    session_id: int
    patient_id: int
    appointment_id: int
    confirmation_token: str
    idempotency_key: str = Field(min_length=8)


class FAQSearchResponse(BaseModel):
    id: int
    category: str
    question: str
    approved_answer: str


class EscalationRequest(BaseModel):
    session_id: int
    patient_id: int
    reason: str


class EscalationResponse(BaseModel):
    created: bool
    reference: str


class ConfirmationTokenRequest(BaseModel):
    session_id: int
    patient_id: int
    appointment_id: int
    action: str
    target_appointment_id: int | None = None


class ConfirmationTokenResponse(BaseModel):
    confirmation_token: str


class IntakeRequest(BaseModel):
    session_id: int
    patient_id: int
    answers: dict[str, Any]
    confirmed: bool


class IntakeResponse(BaseModel):
    success: bool
    intake_id: int


class AppointmentRescheduleRequest(BaseModel):
    session_id: int
    patient_id: int

    current_appointment_id: int
    new_appointment_id: int

    confirmation_token: str

    idempotency_key: str = Field(
        min_length=8,
    )


class SessionFinalizeRequest(BaseModel):
    patient_id: int
    intent: str
    outcome: str
    summary: dict[str, Any]


class SessionFinalizeResponse(BaseModel):
    success: bool
    session_id: int