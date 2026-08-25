from collections.abc import Generator

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from db.models import CallSession
from db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def require_verified_session(
    session_id: int,
    patient_id: int,
    db: Session,
) -> CallSession:
    call_session = db.get(
        CallSession,
        session_id,
    )

    if call_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    if not call_session.verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patient verification required.",
        )

    if call_session.verified_patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verified patient does not match request.",
        )

    return call_session