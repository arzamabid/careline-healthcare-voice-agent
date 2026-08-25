from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Patient


def verify_patient_identifiers(
    db: Session,
    identifiers: dict[str, Any],
) -> Patient | None:
    supplied = {
        key: value
        for key, value in identifiers.items()
        if value is not None
    }

    if len(supplied) < 2:
        return None

    stmt = select(Patient)

    for field_name, value in supplied.items():
        stmt = stmt.where(
            getattr(Patient, field_name) == value
        )

    return db.scalar(stmt)

