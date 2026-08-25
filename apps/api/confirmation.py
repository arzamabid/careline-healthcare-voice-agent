import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass
class ConfirmationRecord:
    token: str
    session_id: int
    patient_id: int
    appointment_id: int
    action: str
    expires_at: datetime
    target_appointment_id: int | None = None


_confirmation_store: dict[str, ConfirmationRecord] = {}


def create_confirmation_token(
    session_id: int,
    patient_id: int,
    appointment_id: int,
    action: str,
    target_appointment_id: int | None = None,
) -> str:
    token = secrets.token_urlsafe(24)

    _confirmation_store[token] = ConfirmationRecord(
        token=token,
        session_id=session_id,
        patient_id=patient_id,
        appointment_id=appointment_id,
        action=action,
        expires_at=datetime.now(UTC) + timedelta(minutes=2),
        target_appointment_id=target_appointment_id,

    )

    return token

def consume_confirmation_token(
    token: str,
    session_id: int,
    patient_id: int,
    appointment_id: int,
    action: str,
    target_appointment_id: int | None = None,
) -> bool:
    record = _confirmation_store.pop(
        token,
        None,
    )

    if record is None:
        return False

    if datetime.now(UTC) > record.expires_at:
        return False

    return (
        record.session_id == session_id
        and record.patient_id == patient_id
        and record.appointment_id == appointment_id
        and record.action == action
        and record.target_appointment_id == target_appointment_id
    )
