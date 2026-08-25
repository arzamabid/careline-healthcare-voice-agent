from langchain_core.tools import tool


@tool
def request_book_appointment(
    appointment_id: int,
) -> dict:
    """
    Request booking of an available appointment.

    This tool does NOT modify the database.
    """
    return {
        "action": "book",
        "appointment_id": appointment_id,
    }


@tool
def request_cancel_appointment(
    appointment_id: int,
) -> dict:
    """
    Request cancellation of an existing appointment.

    This tool does NOT modify the database.
    """
    return {
        "action": "cancel",
        "appointment_id": appointment_id,
    }


@tool
def request_reschedule_appointment(
    current_appointment_id: int,
    new_appointment_id: int,
) -> dict:
    """
    Request moving an existing appointment to
    another available appointment slot.

    This tool does NOT modify the database.
    """
    return {
        "action": "reschedule",
        "current_appointment_id":
            current_appointment_id,
        "new_appointment_id":
            new_appointment_id,
    }
