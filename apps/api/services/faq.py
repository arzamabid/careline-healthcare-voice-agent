import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    Appointment,
    Clinic,
    FAQDocument,
)

STOP_WORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "am",
    "do",
    "does",
    "did",
    "what",
    "when",
    "where",
    "how",
    "which",
    "can",
    "could",
    "would",
    "will",
    "you",
    "your",
    "i",
    "me",
    "my",
    "we",
    "our",
    "to",
    "for",
    "of",
    "in",
    "on",
    "at",
    "it",
    "please",
    "tell",
    "know",
    "clinic",
    "clinics",
}


SYNONYMS = {
    "close": {
        "close",
        "closing",
        "closed",
        "hours",
        "open",
        "opening",
        "timing",
        "timings",
    },

    "open": {
        "open",
        "opening",
        "hours",
        "close",
        "closing",
        "timing",
        "timings",
    },

    "hours": {
        "hour",
        "hours",
        "open",
        "opening",
        "close",
        "closing",
        "timing",
        "timings",
    },

    "timing": {
        "timing",
        "timings",
        "hours",
        "open",
        "opening",
        "close",
        "closing",
    },

    "timings": {
        "timing",
        "timings",
        "hours",
        "open",
        "opening",
        "close",
        "closing",
    },

    "located": {
        "located",
        "location",
        "address",
        "directions",
    },

    "location": {
        "located",
        "location",
        "address",
        "directions",
    },

    "address": {
        "address",
        "location",
        "located",
        "directions",
    },

    "cancel": {
        "cancel",
        "cancellation",
        "cancelled",
    },

    "reschedule": {
        "reschedule",
        "rescheduling",
        "change",
    },
}


def _tokenize(
    text: str,
) -> set[str]:
    words = set(
        re.findall(
            r"[a-zA-Z]+",
            text.lower(),
        )
    )

    return {
        word
        for word in words
        if word not in STOP_WORDS
    }


def _expand_tokens(
    tokens: set[str],
) -> set[str]:
    expanded = set(tokens)

    for token in tokens:
        expanded.update(
            SYNONYMS.get(
                token,
                set(),
            )
        )

    return expanded


def _is_location_query(
    query: str,
) -> bool:
    query_lower = query.lower()

    keywords = (
        "where",
        "location",
        "located",
        "address",
        "direction",
        "directions",
    )

    return any(
        keyword in query_lower
        for keyword in keywords
    )


def _is_hours_query(
    query: str,
) -> bool:
    query_lower = query.lower()

    keywords = (
        "hour",
        "hours",
        "open",
        "opening",
        "close",
        "closing",
        "closed",

        # NEW
        "timing",
        "timings",

        # Useful for:
        # "what time does the clinic close?"
        "what time",
    )

    return any(
        keyword in query_lower
        for keyword in keywords
    )


def _find_named_clinic(
    db: Session,
    query: str,
) -> Clinic | None:
    """
    Detect an explicitly named clinic.

    Examples:

        "Where is West Clinic?"
        "What are Central Clinic opening hours?"
    """

    query_lower = query.lower()

    clinics = list(
        db.scalars(
            select(Clinic)
        ).all()
    )

    for clinic in clinics:
        if (
            clinic.name.lower()
            in query_lower
        ):
            return clinic

    return None


def _find_clinic_by_name(
    db: Session,
    clinic_name: str | None,
) -> Clinic | None:
    if not clinic_name:
        return None

    return db.scalar(
        select(Clinic)
        .where(
            Clinic.name == clinic_name
        )
    )


def _find_clinic_from_appointment(
    db: Session,
    appointment_id: int | None,
) -> Clinic | None:
    """
    Resolve clinic from the exact appointment
    currently stored in LangGraph state.
    """

    if appointment_id is None:
        return None

    appointment = db.get(
        Appointment,
        appointment_id,
    )

    if appointment is None:
        return None

    return db.get(
        Clinic,
        appointment.clinic_id,
    )


def _find_patient_latest_booked_clinic(
    db: Session,
    patient_id: int | None,
) -> Clinic | None:
    """
    Fallback when selected_appointment_id is unavailable.
    """

    if patient_id is None:
        return None

    appointment = db.scalar(
        select(Appointment)
        .where(
            Appointment.patient_id
            == patient_id,

            Appointment.status
            == "booked",
        )
        .order_by(
            Appointment.id.desc()
        )
        .limit(1)
    )

    if appointment is None:
        return None

    return db.get(
        Clinic,
        appointment.clinic_id,
    )


def get_clinic_information(
    db: Session,
    query: str,
    appointment_id: int | None = None,
    patient_id: int | None = None,
    last_referenced_clinic: str | None = None,
) -> tuple[str, str] | None:
    """
    Return:

        (
            response_text,
            clinic_name,
        )

    Resolution priority:

    1. Explicit clinic named in THIS question.
    2. Clinic from previous conversational context.
    3. Clinic belonging to the selected appointment.
    4. Patient's latest booked appointment.
    5. No guessing.

    Response wording depends on WHY the clinic
    was selected.

    If caller explicitly asks about West Clinic,
    we do NOT claim the appointment is there.
    """

    if not (
        _is_location_query(query)
        or _is_hours_query(query)
    ):
        return None

    # =================================================
    # 1. Explicit clinic in current utterance
    # =================================================

    named_clinic = _find_named_clinic(
        db=db,
        query=query,
    )

    if named_clinic is not None:

        if _is_location_query(query):
            return (
                (
                    f"{named_clinic.name} is located at "
                    f"{named_clinic.address}."
                ),
                named_clinic.name,
            )

        if _is_hours_query(query):
            return (
                (
                    f"{named_clinic.name} is open "
                    f"{named_clinic.opening_hours}."
                ),
                named_clinic.name,
            )

    # =================================================
    # 2. Continue talking about previously named clinic
    #
    # Example:
    #
    # User:
    # "Where is West Clinic?"
    #
    # User:
    # "What are the timings of the clinic?"
    #
    # -> West Clinic
    # =================================================

    context_clinic = _find_clinic_by_name(
        db=db,
        clinic_name=last_referenced_clinic,
    )

    if context_clinic is not None:

        if _is_location_query(query):
            return (
                (
                    f"{context_clinic.name} is located at "
                    f"{context_clinic.address}."
                ),
                context_clinic.name,
            )

        if _is_hours_query(query):
            return (
                (
                    f"{context_clinic.name} is open "
                    f"{context_clinic.opening_hours}."
                ),
                context_clinic.name,
            )

    # =================================================
    # 3. Exact appointment clinic
    # =================================================

    appointment_clinic = (
        _find_clinic_from_appointment(
            db=db,
            appointment_id=appointment_id,
        )
    )

    if appointment_clinic is not None:

        if _is_location_query(query):
            return (
                (
                    f"Your appointment is at "
                    f"{appointment_clinic.name}, "
                    f"located at "
                    f"{appointment_clinic.address}."
                ),
                appointment_clinic.name,
            )

        if _is_hours_query(query):
            return (
                (
                    f"{appointment_clinic.name}, "
                    f"where your appointment is booked, "
                    f"is open "
                    f"{appointment_clinic.opening_hours}."
                ),
                appointment_clinic.name,
            )

    # =================================================
    # 4. Verified patient's latest booked appointment
    # =================================================

    patient_clinic = (
        _find_patient_latest_booked_clinic(
            db=db,
            patient_id=patient_id,
        )
    )

    if patient_clinic is not None:

        if _is_location_query(query):
            return (
                (
                    f"Your appointment is at "
                    f"{patient_clinic.name}, "
                    f"located at "
                    f"{patient_clinic.address}."
                ),
                patient_clinic.name,
            )

        if _is_hours_query(query):
            return (
                (
                    f"{patient_clinic.name}, "
                    f"where your appointment is booked, "
                    f"is open "
                    f"{patient_clinic.opening_hours}."
                ),
                patient_clinic.name,
            )

    return None


def search_approved_faq(
    db: Session,
    query: str,
    limit: int = 5,
) -> list[FAQDocument]:
    """
    Search approved FAQ rows only.

    Results must have meaningful query coverage.
    A single incidental token match must not be enough
    to return an unrelated FAQ answer.
    """

    if not query.strip():
        return []

    documents = list(
        db.scalars(
            select(FAQDocument)
        ).all()
    )

    # Keep the original query tokens separately.
    #
    # We use these for coverage calculation so synonym
    # expansion does not artificially increase the
    # denominator.
    base_query_tokens = _tokenize(
        query
    )

    if not base_query_tokens:
        return []

    expanded_query_tokens = (
        _expand_tokens(
            base_query_tokens
        )
    )

    scored_results: list[
        tuple[
            float,
            int,
            FAQDocument,
        ]
    ] = []

    for document in documents:
        searchable_text = (
            f"{document.question} "
            f"{document.approved_answer}"
        )

        base_document_tokens = (
            _tokenize(
                searchable_text
            )
        )

        expanded_document_tokens = (
            _expand_tokens(
                base_document_tokens
            )
        )

        # ---------------------------------------------
        # Determine how much of the caller's actual
        # query is supported by this FAQ.
        # ---------------------------------------------

        matched_query_tokens = {
            token
            for token in base_query_tokens
            if (
                token
                in expanded_document_tokens
            )
        }

        matched_count = len(
            matched_query_tokens
        )

        query_coverage = (
            matched_count
            / len(base_query_tokens)
        )

        # Expanded overlap is useful only for ranking
        # candidates that already passed the relevance
        # threshold.
        expanded_overlap = len(
            expanded_query_tokens
            & expanded_document_tokens
        )

        # ---------------------------------------------
        # Relevance gate
        # ---------------------------------------------
        #
        # Examples:
        #
        # "What are the opening hours?"
        # -> strong coverage
        #
        # "Friday?"
        # -> 1/1, still valid
        #
        # "Does North Clinic provide free private
        # helicopter transport?"
        # -> likely only "north" overlaps, therefore
        # weak coverage and must be rejected.
        # ---------------------------------------------

        if (
            matched_count == 0
            or query_coverage < 0.5
        ):
            continue

        scored_results.append(
            (
                query_coverage,
                expanded_overlap,
                document,
            )
        )

    # Highest percentage of the caller's query wins.
    # Expanded token overlap breaks ties.
    scored_results.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    return [
        document
        for _, _, document
        in scored_results[:limit]
    ]