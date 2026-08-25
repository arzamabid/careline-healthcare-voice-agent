from agent.state import CallState

EMERGENCY_TERMS = {
    "chest pain",
    "can't breathe",
    "cannot breathe",
    "difficulty breathing",
    "severe bleeding",
    "unconscious",
    "passed out",
    "heart attack",
    "stroke",
    "suicide",
    "kill myself",
    "self harm",
    "self-harm",
}


CLINICAL_ADVICE_TERMS = {
    "diagnose",
    "diagnosis",
    "what disease",
    "what condition",
    "what medication",
    "what medicine",
    "what dose",
    "dosage",
    "should i take",

    "should i stop",
    "should i stop taking",
    "can i stop",
    "can i stop taking",
    "stop taking my",
    "should i discontinue",
    "can i discontinue",

    "treatment",
    "is this cancer",
    "what is wrong with me",

    # Diagnosis phrasing
    "do these symptoms mean",
    "does this symptom mean",
    "does this mean i have",
    "symptoms mean i have",
    "could these symptoms mean",
    "might these symptoms mean",
    "tell me whether these symptoms",
}


def safety_gate_node(state: CallState) -> CallState:
    caller_text = state.get(
        "caller_text",
        "",
    ).lower()

    safety_flags = list(
        state.get("safety_flags", [])
    )

    emergency_detected = any(
        term in caller_text
        for term in EMERGENCY_TERMS
    )

    clinical_advice_detected = any(
        term in caller_text
        for term in CLINICAL_ADVICE_TERMS
    )

    if emergency_detected:
        if "emergency" not in safety_flags:
            safety_flags.append("emergency")

        return {
            "current_node": "safety_gate",
            "safety_flags": safety_flags,
            "escalation_required": True,
            "response_text": "",
        }

    if clinical_advice_detected:
        if "clinical_advice" not in safety_flags:
            safety_flags.append("clinical_advice")

        return {
            "current_node": "safety_gate",
            "safety_flags": safety_flags,
            "escalation_required": True,
            "response_text": "",
        }

    return {
        "current_node": "safety_gate",
        "safety_flags": safety_flags,
        "escalation_required": False,
    }
