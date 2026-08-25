from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from db.models import AuditEvent, CallSession

router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
)


@router.get("/sessions/{session_id}")
def get_session_metrics(
    session_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    call_session = db.get(
        CallSession,
        session_id,
    )

    if call_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    event_count = db.scalar(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.session_id == session_id
        )
    )

    successful_events = db.scalar(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.session_id == session_id,
            AuditEvent.success.is_(True),
        )
    )

    return {
        "session_id": session_id,
        "intent": call_session.intent,
        "outcome": call_session.outcome,
        "escalated": call_session.escalated,
        "event_count": event_count or 0,
        "successful_events": successful_events or 0,
    }
