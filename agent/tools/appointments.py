from datetime import UTC, datetime, timedelta

from agent.state import CallState

KNOWN_SPECIALTIES = {
    "dermatology": "Dermatology",
    "cardiology": "Cardiology",
    "family medicine": "Family Medicine",
    "orthopedics": "Orthopedics",
    "ent": "ENT",
}


def extract_appointment_fields(
    state: CallState,
) -> dict[str, str]:
    caller_text = state.get(
        "caller_text",
        "",
    ).lower()

    fields: dict[str, str] = {}

    for keyword, specialty in KNOWN_SPECIALTIES.items():
        if keyword in caller_text:
            fields["specialty"] = specialty
            break

    today = datetime.now(UTC).date()
    if "tomorrow" in caller_text:
        fields["target_date"] = str(
            today + timedelta(days=1)
        )

    elif "today" in caller_text:
        fields["target_date"] = str(today)

    return fields
