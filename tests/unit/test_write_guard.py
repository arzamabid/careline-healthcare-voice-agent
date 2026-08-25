import pytest

from agent.tools.write_guard import (
    WriteAuthorizationError,
    authorize_confirmed_write,
)


def test_write_requires_verified_patient() -> None:
    state = {
        "verified_patient_id": None,
        "confirmation_received": True,
        "pending_confirmation": {
            "action": "book",
            "appointment_id": 10,
        },
    }

    with pytest.raises(
        WriteAuthorizationError
    ):
        authorize_confirmed_write(
            state,
            {
                "action": "book",
                "appointment_id": 10,
            },
        )


def test_write_requires_confirmation() -> None:
    state = {
        "verified_patient_id": 1,
        "confirmation_received": False,
        "pending_confirmation": {
            "action": "book",
            "appointment_id": 10,
        },
    }

    with pytest.raises(
        WriteAuthorizationError
    ):
        authorize_confirmed_write(
            state,
            {
                "action": "book",
                "appointment_id": 10,
            },
        )


def test_different_appointment_is_blocked() -> None:
    state = {
        "verified_patient_id": 1,
        "confirmation_received": True,
        "pending_confirmation": {
            "action": "book",
            "appointment_id": 10,
        },
    }

    with pytest.raises(
        WriteAuthorizationError
    ):
        authorize_confirmed_write(
            state,
            {
                "action": "book",
                "appointment_id": 999,
            },
        )


def test_confirmed_write_is_allowed() -> None:
    state = {
        "verified_patient_id": 1,
        "confirmation_received": True,
        "pending_confirmation": {
            "action": "book",
            "appointment_id": 10,
        },
    }

    authorize_confirmed_write(
        state,
        {
            "action": "book",
            "appointment_id": 10,
        },
    )
