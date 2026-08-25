from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from db.base import Base
from db.models import Patient


def test_patient_can_be_persisted_with_sqlite() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
    )

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        patient = Patient(
            first_name="Test",
            last_name="Patient",
            date_of_birth=date(1990, 1, 1),
            phone_last4="1234",
            member_id="TEST-00001",
            preferred_language="English",
        )

        session.add(patient)
        session.commit()
        session.refresh(patient)

        assert patient.id is not None

        stored = session.get(Patient, patient.id)

        assert stored is not None
        assert stored.first_name == "Test"
        assert stored.member_id == "TEST-00001"
