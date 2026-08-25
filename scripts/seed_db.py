from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, text

from db.models import (
    Appointment,
    AuditEvent,
    CallSession,
    Clinic,
    Clinician,
    FAQDocument,
    IdempotencyRecord,
    IntakeRecord,
    Patient,
)
from db.session import get_db_session

PATIENT_FIRST_NAMES = [
    "Ahmed",
    "Sara",
    "Omar",
    "Aisha",
    "Yousef",
    "Mariam",
    "Khalid",
    "Noor",
    "Faisal",
    "Lina",
]

PATIENT_LAST_NAMES = [
    "Ali",
    "Hassan",
    "Khan",
]


def create_patients() -> list[Patient]:
    patients = []

    counter = 1

    for first_name in PATIENT_FIRST_NAMES:
        for last_name in PATIENT_LAST_NAMES:
            patients.append(
                Patient(
                    first_name=first_name,
                    last_name=last_name,
                    date_of_birth=date(
                        1980 + (counter % 25),
                        ((counter - 1) % 12) + 1,
                        ((counter - 1) % 27) + 1,
                    ),
                    phone_last4=f"{1000 + counter:04d}",
                    member_id=f"CARE-{counter:05d}",
                    preferred_language="English",
                )
            )

            counter += 1

    return patients


def create_clinicians() -> list[Clinician]:
    return [
        Clinician(
            name="Dr. Amal Rahman",
            specialty="Dermatology",
        ),
        Clinician(
            name="Dr. Omar Saeed",
            specialty="Cardiology",
        ),
        Clinician(
            name="Dr. Lina Hassan",
            specialty="Family Medicine",
        ),
        Clinician(
            name="Dr. Yusuf Karim",
            specialty="Orthopedics",
        ),
        Clinician(
            name="Dr. Sara Nadeem",
            specialty="ENT",
        ),
    ]


def create_clinics() -> list[Clinic]:
    return [
        Clinic(
            name="North Clinic",
            address="100 Demo North Road",
            opening_hours="Sunday-Thursday 08:00-17:00",
        ),
        Clinic(
            name="Central Clinic",
            address="200 Demo Central Road",
            opening_hours="Sunday-Thursday 08:00-18:00",
        ),
        Clinic(
            name="West Clinic",
            address="300 Demo West Road",
            opening_hours="Sunday-Thursday 09:00-17:00",
        ),
    ]


def create_faqs() -> list[FAQDocument]:
    categories = {
        "hours": [
            (
                "What are your opening hours?",
                (
                "Clinic opening hours vary by location. "
                "North Clinic is open Sunday through Thursday "
                "from 8 AM to 5 PM."
                ),
            ),
            (
                "Are clinics open on Friday?",
                (
                "The demo clinics are closed on Friday."
                ),
            ),
            (
                "Are clinics open on Saturday?",
                (
                "The demo clinics are closed on Saturday."
                ),
            ),
        ],
        "appointments": [
            (
                "How early should I arrive?",
                (
                "Please arrive 15 minutes before your appointment."
                ),
            ),
            (
                "Can I reschedule an appointment?",
                (
                "Yes. Verified patients may request rescheduling "
                "subject to available slots."
                ),
            ),
            (
                "Can I cancel an appointment?",
                (
                "Yes. Verified patients may cancel an appointment."
                ),
            ),
        ],
        "documents": [
            (
                "What should I bring?",
                (
                "Bring the identification and documents requested "
                "for your demo appointment."
                ),
            ),
            (
                "Do I need identification?",
                (
                "Identification details may be required for the "
                "synthetic verification workflow."
                ),
            ),
            (
                "Should I bring previous records?",
                (
                "If applicable, bring records requested in your "
                "appointment preparation instructions."
                ),
            ),
        ],
    }

    base_entries = []

    for category, entries in categories.items():
        for question, answer in entries:
            base_entries.append(
                FAQDocument(
                    category=category,
                    question=question,
                    approved_answer=answer,
                    source_version="1.0",
                )
            )

    faq_entries = []

    for index in range(30):
        template = base_entries[index % len(base_entries)]

        faq_entries.append(
            FAQDocument(
                category=template.category,
                question=f"{template.question} [Demo FAQ {index + 1}]",
                approved_answer=template.approved_answer,
                source_version="1.0",
            )
        )

    return faq_entries


def create_appointments(
        clinicians: list[Clinician],
        clinics: list[Clinic],
) -> list[Appointment]:
    appointments = []

    # start_date = date.today() + timedelta(days=1)
    # To this:
    start_date = datetime.now(UTC).date() + timedelta(days=1)

    times = [
        time(9, 0),
        time(10, 30),
        time(13, 0),
        time(15, 0),
    ]

    for day_offset in range(14):
        slot_date = start_date + timedelta(days=day_offset)

        for clinician_index, clinician in enumerate(clinicians):
            clinic = clinics[clinician_index % len(clinics)]

            for slot_time in times:
                appointments.append(
                    Appointment(
                        patient_id=None,
                        clinician_id=clinician.id,
                        clinic_id=clinic.id,
                        start_at=datetime.combine(
                            slot_date,
                            slot_time,
                        ),
                        status="available",
                        reason_code=None,
                    )
                )

    return appointments


def seed_database() -> None:
    session = get_db_session()

    try:
        # session.execute(delete(AuditEvent))
        # session.execute(delete(CallSession))
        # session.execute(delete(Appointment))
        # session.execute(delete(FAQDocument))
        # session.execute(delete(Patient))
        # session.execute(delete(Clinician))
        # session.execute(delete(Clinic))

        # --- CHANGE THIS SECTION TO DELETE IN THE CORRECT ORDER ---
        # First delete from tables that contain Foreign Keys pointing elsewhere
        session.execute(delete(IntakeRecord))  # <--- Add this FIRST to clear child dependencies
        session.execute(delete(IdempotencyRecord))
        session.execute(delete(AuditEvent))
        session.execute(delete(Appointment))

        # Now it is completely safe to delete the parent rows
        session.execute(delete(CallSession))
        session.execute(delete(Clinician))
        session.execute(delete(Clinic))
        session.execute(delete(Patient))
        session.execute(delete(FAQDocument))

        # 2. ADD THIS: Force Postgres to reset the sequence counters back to 1
        session.execute(text("ALTER SEQUENCE appointments_id_seq RESTART WITH 1;"))
        session.execute(text("ALTER SEQUENCE call_sessions_id_seq RESTART WITH 1;"))
        session.execute(text("ALTER SEQUENCE patients_id_seq RESTART WITH 1;"))

        session.commit()

        patients = create_patients()
        clinicians = create_clinicians()
        clinics = create_clinics()
        faqs = create_faqs()

        session.add_all(patients)
        session.add_all(clinicians)
        session.add_all(clinics)
        session.add_all(faqs)

        session.flush()

        appointments = create_appointments(
            clinicians=clinicians,
            clinics=clinics,
        )

        session.add_all(appointments)

        session.commit()

        print(f"Patients: {len(patients)}")
        print(f"Clinicians: {len(clinicians)}")
        print(f"Clinics: {len(clinics)}")
        print(f"Appointments: {len(appointments)}")
        print(f"FAQ entries: {len(faqs)}")

    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
