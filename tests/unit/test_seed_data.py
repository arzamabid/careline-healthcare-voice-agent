from scripts.seed_db import (
    create_clinicians,
    create_clinics,
    create_faqs,
    create_patients,
)


def test_seed_contains_required_patient_count() -> None:
    patients = create_patients()

    assert len(patients) >= 30


def test_seed_contains_exactly_five_clinicians() -> None:
    clinicians = create_clinicians()

    assert len(clinicians) == 5


def test_seed_contains_exactly_three_clinics() -> None:
    clinics = create_clinics()

    assert len(clinics) == 3


def test_seed_contains_at_least_thirty_faqs() -> None:
    faqs = create_faqs()

    assert len(faqs) >= 30
