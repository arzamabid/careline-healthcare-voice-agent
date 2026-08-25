from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date] = mapped_column(Date)

    phone_last4: Mapped[str] = mapped_column(String(4))
    member_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
    )

    preferred_language: Mapped[str] = mapped_column(
        String(30),
        default="English",
    )


class Clinician(Base):
    __tablename__ = "clinicians"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(150))
    specialty: Mapped[str] = mapped_column(String(100))

class Clinic(Base):
    __tablename__ = "clinics"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(150))
    address: Mapped[str] = mapped_column(String(250))
    opening_hours: Mapped[str] = mapped_column(String(250))

class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)

    patient_id: Mapped[int | None] = mapped_column(
        ForeignKey("patients.id"),
        nullable=True,
    )

    clinician_id: Mapped[int] = mapped_column(
        ForeignKey("clinicians.id"),
    )

    clinic_id: Mapped[int] = mapped_column(
        ForeignKey("clinics.id"),
    )

    start_at: Mapped[datetime] = mapped_column(DateTime)

    status: Mapped[str] = mapped_column(
        String(30),
        default="available",
    )

    reason_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    patient: Mapped[Patient | None] = relationship()
    clinician: Mapped[Clinician] = relationship()
    clinic: Mapped[Clinic] = relationship()


class FAQDocument(Base):
    __tablename__ = "faq_documents"

    id: Mapped[int] = mapped_column(primary_key=True)

    category: Mapped[str] = mapped_column(String(100))
    question: Mapped[str] = mapped_column(Text)
    approved_answer: Mapped[str] = mapped_column(Text)

    source_version: Mapped[str] = mapped_column(
        String(50),
        default="1.0",
    )


class CallSession(Base):
    __tablename__ = "call_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)

    patient_id: Mapped[int | None] = mapped_column(
        ForeignKey("patients.id"),
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    intent: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    outcome: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    escalated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    summary_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    verified_patient_id: Mapped[int | None] = mapped_column(
        ForeignKey("patients.id"),
        nullable=True,
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("call_sessions.id"),
        nullable=True,
    )

    event_type: Mapped[str] = mapped_column(String(100))

    node: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    tool_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    success: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[int] = mapped_column(primary_key=True)

    key: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
    )

    result_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
    )


class IntakeRecord(Base):
    __tablename__ = "intake_records"

    id: Mapped[int] = mapped_column(primary_key=True)

    session_id: Mapped[int] = mapped_column(
        ForeignKey("call_sessions.id"),
    )

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"),
    )

    answers_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
    )

    confirmed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
