import re

from agent.llm.intent import OllamaIntentClassifier
from agent.state import CallState

classifier = OllamaIntentClassifier()


def _looks_like_faq(
    caller_text: str,
) -> bool:
    """
    Deterministic detection of obvious informational
    clinic questions.

    These should NOT require identity verification.
    """

    if not isinstance(
        caller_text,
        str,
    ):
        return False

    text = caller_text.lower().strip()

    # Remove punctuation for easier matching.
    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    text = " ".join(
        text.split()
    )

    # =================================================
    # Strong FAQ phrases
    #
    # A single one of these is enough.
    # =================================================

    strong_patterns = (
        # Appointment preparation
        "what should i bring",
        "what do i bring",
        "what should i take",
        "what do i need to bring",

        # Identification/documents
        "do i need identification",
        "do i need id",
        "previous records",
        "medical records",
        "documents should i bring",

        # Opening hours
        "opening hours",
        "opening hour",
        "what time do you open",
        "what time does the clinic open",
        "what time does the clinic close",
        "clinic timing",
        "clinic timings",

        # Location
        "where is the clinic",
        "where is west clinic",
        "where is central clinic",
        "where is north clinic",
        "clinic location",
        "clinic address",

        # Appointment general information
        "how early should i arrive",
        "how early do i arrive",

        # Friday / Saturday
        "open on friday",
        "open friday",
        "closed on friday",
        "closed friday",
        "open on saturday",
        "open saturday",
        "closed on saturday",
        "closed saturday",
    )

    if any(
        pattern in text
        for pattern in strong_patterns
    ):
        return True

    # =================================================
    # Explicitly named clinic + information request
    # =================================================

    clinic_names = (
        "north clinic",
        "central clinic",
        "west clinic",
    )

    clinic_info_words = (
        "open",
        "opening",
        "close",
        "closed",
        "hours",
        "hour",
        "timing",
        "timings",
        "where",
        "address",
        "location",
        "located",
    )

    if (
        any(
            clinic in text
            for clinic in clinic_names
        )
        and any(
            word in text
            for word in clinic_info_words
        )
    ):
        return True

    # =================================================
    # General FAQ keyword combinations
    # =================================================

    faq_keywords = {
        "friday",
        "saturday",
        "open",
        "opening",
        "closed",
        "close",
        "hours",
        "hour",
        "timing",
        "timings",
        "where",
        "located",
        "location",
        "address",
        "parking",
        "records",
        "identification",
    }

    matches = sum(
        1
        for keyword in faq_keywords
        if keyword in text
    )

    return matches >= 2


def classify_intent_node(
    state: CallState,
) -> CallState:
    """
    Classify a caller request.

    Deterministic FAQ recognition happens before
    the LLM classifier.
    """

    caller_text = state.get(
        "caller_text",
        "",
    )

    # =================================================
    # 1. Preserve intent while identity is incomplete
    # =================================================

    identity_status = state.get(
        "identity_status"
    )

    existing_intent = state.get(
        "intent"
    )

    if (
        existing_intent is not None
        and state.get(
            "verified_patient_id"
        )
        is None
        and identity_status
        in {
            "needs_identifiers",
            "needs_phone_last4",
            "needs_member_id",
            "failed_retry",
        }
    ):
        return {
            "intent":
                existing_intent,

            "current_node":
                "classify_intent",
        }

    # =================================================
    # 2. FAQ deterministic fast-path
    # =================================================

    if _looks_like_faq(
        caller_text
    ):
        print(
            "DETERMINISTIC FAQ INTENT:",
            repr(caller_text),
        )

        return {
            "intent":
                "faq",

            "current_node":
                "classify_intent",
        }

    # =================================================
    # 3. LLM classifier
    # =================================================

    result = classifier.classify(
        caller_text,
    )

    print(
        "LLM INTENT RESULT:",
        result.intent,
        result.confidence,
    )

    # =================================================
    # 4. Unknown
    # =================================================

    if result.intent == "other":
        return {
            "intent":
                "unknown",

            "active_workflow":
                None,

            "response_text": (
                "I'm sorry, I didn't quite understand that. "
                "Could you please rephrase your request?"
            ),

            "current_node":
                "classify_intent",

            "metrics": {
                **state.get(
                    "metrics",
                    {},
                ),
                "intent_confidence":
                    result.confidence,
            },
        }

    # =================================================
    # 5. Recognized intent
    # =================================================

    return {
        "intent":
            result.intent,

        "current_node":
            "classify_intent",

        "metrics": {
            **state.get(
                "metrics",
                {},
            ),
            "intent_confidence":
                result.confidence,
        },
    }