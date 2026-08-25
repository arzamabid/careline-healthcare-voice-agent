from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_unverified_session_cannot_search_appointments() -> None:
    session_response = client.post("/sessions")

    session_id = session_response.json()["session_id"]

    response = client.get(
        "/appointments/availability",
        params={
            "session_id": session_id,
            "patient_id": 1,
            "specialty": "Dermatology",
            "target_date": "2030-01-01",
        },
    )

    assert response.status_code == 403

def test_booking_rejects_invalid_confirmation() -> None:
    session_response = client.post("/sessions")
    session_id = session_response.json()["session_id"]

    verification_response = client.post(
        "/patients/verify",
        json={
            "session_id": session_id,
            "member_id": "CARE-00001",
            "phone_last4": "1001",
        },
    )

    patient_id = verification_response.json()["patient_id"]

    response = client.post(
        "/appointments/book",
        json={
            "session_id": session_id,
            "patient_id": patient_id,
            "appointment_id": 1,
            "confirmation_token": "invalid-token",
            "idempotency_key": "invalid-booking-test-001",
        },
    )

    assert response.status_code == 403
