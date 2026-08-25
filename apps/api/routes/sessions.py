from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from apps.api.schemas import SessionCreateResponse
from db.models import CallSession

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionCreateResponse)
def create_session(
    db: Session = Depends(get_db),
) -> SessionCreateResponse:
    session = CallSession()

    db.add(session)
    db.commit()
    db.refresh(session)

    return SessionCreateResponse(
        session_id=session.id,
    )
