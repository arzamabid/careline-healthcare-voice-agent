from typing import Any

from agent.state import CallState


class WriteAuthorizationError(Exception):
    pass


def authorize_confirmed_write(
    state: CallState,
    request: dict[str, Any],
) -> None:
    patient_id = state.get(
        "verified_patient_id"
    )

    if patient_id is None:
        raise WriteAuthorizationError(
            "Patient identity has not been verified."
        )

    if not state.get(
        "confirmation_received",
        False,
    ):
        raise WriteAuthorizationError(
            "Explicit confirmation is required."
        )

    pending = state.get(
        "pending_confirmation"
    ) or {}

    requested_action = request.get("action")

    if pending.get("action") != requested_action:
        raise WriteAuthorizationError(
            "Confirmed action does not match "
            "the requested action."
        )

    if requested_action == "book":
        confirmed_id = pending.get(
            "appointment_id"
        )

        requested_id = request.get(
            "appointment_id"
        )

        if (
            confirmed_id is not None
            and confirmed_id != requested_id
        ):
            raise WriteAuthorizationError(
                "Appointment does not match "
                "the confirmed appointment."
            )
