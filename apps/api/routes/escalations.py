from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.dependencies import (
    get_db,
    require_verified_session,
)
from apps.api.schemas import (
    EscalationRequest,
    EscalationResponse,
)
from db.models import AuditEvent, CallSession

router = APIRouter(
    prefix="/escalations",
    tags=["escalations"],
)


@router.post(
    "",
    response_model=EscalationResponse,
)
def create_escalation(
    payload: EscalationRequest,
    db: Session = Depends(get_db),
) -> EscalationResponse:
    require_verified_session(
        session_id=payload.session_id,
        patient_id=payload.patient_id,
        db=db,
    )

    call_session = db.get(
        CallSession,
        payload.session_id,
    )

    if call_session is None:
        return EscalationResponse(
            created=False,
            reference="",
        )

    reference = (
        f"ESC-{uuid4().hex[:10].upper()}"
    )

    call_session.escalated = True

    db.add(
        AuditEvent(
            session_id=payload.session_id,
            event_type="escalation",
            success=True,
            metadata_json={
                "reference": reference,
                "reason": payload.reason,
            },
        )
    )

    db.commit()

    return EscalationResponse(
        created=True,
        reference=reference,
    )
