from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_verification_rejects_single_identifier() -> None:
    session_response = client.post("/sessions")

    assert session_response.status_code == 200

    session_id = session_response.json()["session_id"]

    response = client.post(
        "/patients/verify",
        json={
            "session_id": session_id,
            "member_id": "CARE-00001",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["verified"] is False

def test_verification_accepts_two_matching_identifiers() -> None:
    session_response = client.post("/sessions")

    session_id = session_response.json()["session_id"]

    response = client.post(
        "/patients/verify",
        json={
            "session_id": session_id,
            "member_id": "CARE-00001",
            "phone_last4": "1001",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["verified"] is True
    assert body["patient_id"] is not None
