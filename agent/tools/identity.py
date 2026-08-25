import re

NUMBER_WORDS = {
    "zero": "0",
    "oh": "0",
    "o": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}


def normalize_spoken_digits(
    text: str,
) -> str:
    """
    Normalize common STT variations and spoken digits.

    Examples:

        KER zero zero zero zero one
        -> care 0 0 0 0 1

        one zero zero one
        -> 1 0 0 1
    """

    if not isinstance(text, str):
        raise TypeError(
            "normalize_spoken_digits expected a string, "
            f"got {type(text).__name__}"
        )

    # Fix common Whisper transcription of CARE.
    text = re.sub(
        r"\b(?:ker|kerr|car)\b",
        "care",
        text,
        flags=re.IGNORECASE,
    )

    words = re.findall(
        r"[A-Za-z]+|\d+|-",
        text.lower(),
    )

    normalized_parts: list[str] = []

    for word in words:
        if word in NUMBER_WORDS:
            normalized_parts.append(
                NUMBER_WORDS[word]
            )
        else:
            normalized_parts.append(word)

    return " ".join(normalized_parts)


def _extract_member_id(
    normalized_text: str,
) -> str | None:
    """
    Supports:

        CARE-00001
        CARE 00001
        CARE 0 0 0 0 1
    """

    # Compact representation.
    match = re.search(
        r"\bcare[\s-]*(\d{5})\b",
        normalized_text,
        re.IGNORECASE,
    )

    if match:
        return f"CARE-{match.group(1)}"

    # Spaced representation.
    match = re.search(
        r"\bcare\b"
        r"[\s:-]*"
        r"(\d)"
        r"[\s-]*"
        r"(\d)"
        r"[\s-]*"
        r"(\d)"
        r"[\s-]*"
        r"(\d)"
        r"[\s-]*"
        r"(\d)",
        normalized_text,
        re.IGNORECASE,
    )

    if match:
        return (
            "CARE-"
            + "".join(match.groups())
        )

    return None


def _remove_member_id(
    normalized_text: str,
    member_id: str,
) -> str:
    """
    Remove member ID before looking for phone digits.
    """

    member_digits = member_id.replace(
        "CARE-",
        "",
    )

    text = normalized_text

    # Compact form:
    # care 00001
    text = re.sub(
        rf"\bcare[\s-]*{re.escape(member_digits)}\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    # Spaced form:
    # care 0 0 0 0 1
    spaced_pattern = (
        r"\bcare\b[\s:-]*"
        + r"[\s-]*".join(
            re.escape(digit)
            for digit in member_digits
        )
    )

    text = re.sub(
        spaced_pattern,
        " ",
        text,
        flags=re.IGNORECASE,
    )

    return text


def _digits_from_numeric_section(
    text: str,
) -> str | None:
    """
    Return a phone last-four value ONLY when the
    numeric section contains exactly four digits.

    Accept:
        1001
        1 0 0 1
        10 01
        1 001

    Reject:
        101
        10001
    """

    numeric_chunks = re.findall(
        r"\d+",
        text,
    )

    if not numeric_chunks:
        return None

    digits = "".join(
        numeric_chunks
    )

    if len(digits) != 4:
        return None

    return digits


def _extract_phone_last4(
    normalized_text: str,
    member_id: str | None,
) -> str | None:
    """
    Extract exactly four phone digits.

    A 3-digit value like 101 must NOT be accepted.
    """

    text = normalized_text

    if member_id:
        text = _remove_member_id(
            normalized_text=text,
            member_id=member_id,
        )

    # -----------------------------------------
    # Prefer phone-related wording.
    # -----------------------------------------

    phone_context = re.search(
        r"(?:"
        r"last\s+four\s+digits"
        r"|last\s+4\s+digits"
        r"|last\s+four"
        r"|last\s+4"
        r"|phone\s+number"
        r"|phone"
        r"|mobile\s+number"
        r"|mobile"
        r")"
        r"(.*)$",
        text,
        re.IGNORECASE,
    )

    if phone_context:
        phone_section = (
            phone_context.group(1)
        )

        digits = (
            _digits_from_numeric_section(
                phone_section
            )
        )

        if digits is not None:
            return digits

        # Important:
        # phone wording was found, but it did NOT
        # contain exactly four digits.
        #
        # Do not fall through and accidentally accept
        # some other numeric value.
        return None

    # -----------------------------------------
    # Compact exact 4-digit fallback.
    # -----------------------------------------

    compact_matches = re.findall(
        r"\b\d{4}\b",
        text,
    )

    if compact_matches:
        return compact_matches[-1]

    # -----------------------------------------
    # General numeric fallback.
    #
    # Only accept if ALL numeric chunks together
    # contain exactly four digits.
    # -----------------------------------------

    numeric_chunks = re.findall(
        r"\d+",
        text,
    )

    if numeric_chunks:
        digits = "".join(
            numeric_chunks
        )

        if len(digits) == 4:
            return digits

    return None


def _extract_phone_last4(
    normalized_text: str,
    member_id: str | None,
) -> str | None:
    """
    Extract exactly four phone digits.

    Accepts:
        1001
        1 0 0 1
        10 01
        1 001
        one zero zero one

    Rejects:
        101
        10001

    Important:
    The "4" in phrases such as "last 4 digits"
    must never become part of the phone number.
    """

    text = normalized_text

    # -------------------------------------------------
    # Remove member ID first.
    # -------------------------------------------------

    if member_id:
        text = _remove_member_id(
            normalized_text=text,
            member_id=member_id,
        )

    # -------------------------------------------------
    # PHONE CONTEXT
    #
    # Capture ONLY the text AFTER the complete phrase.
    #
    # Example:
    #
    # "last 4 digits of my phone number are 1 0 1"
    #
    # captured:
    # "of my phone number are 1 0 1"
    #
    # NOT:
    # "4 digits ... 1 0 1"
    # -------------------------------------------------

    phone_context_patterns = [
        r"\blast\s+4\s+digits\b(.*)$",
        r"\blast\s+four\s+digits\b(.*)$",
        r"\blast\s+4\b(.*)$",
        r"\blast\s+four\b(.*)$",
        r"\bphone\s+number\b(.*)$",
        r"\bmobile\s+number\b(.*)$",
        r"\bphone\b(.*)$",
        r"\bmobile\b(.*)$",
    ]

    for pattern in phone_context_patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if not match:
            continue

        phone_section = match.group(1)

        # -------------------------------------------------
        # If we matched "last 4 digits", the remaining
        # sentence may contain another phrase:
        #
        # "of my phone number are ..."
        #
        # That's fine. We only collect numeric chunks
        # AFTER the complete marker.
        # -------------------------------------------------

        numeric_chunks = re.findall(
            r"\d+",
            phone_section,
        )

        digits = "".join(
            numeric_chunks
        )

        print(
            "PHONE SECTION:",
            repr(phone_section),
        )

        print(
            "PHONE DIGITS FOUND:",
            repr(digits),
        )

        # EXACTLY four digits required.
        if len(digits) == 4:
            return digits

        # We found explicit phone context but it did
        # not contain exactly four digits.
        #
        # Do NOT fall through to generic extraction,
        # because that could pick up unrelated numbers.
        return None

    # -------------------------------------------------
    # No phone wording was found.
    #
    # This fallback is useful when the agent already
    # has the member ID and asks:
    #
    # "Please provide the last four digits."
    #
    # Caller may simply respond:
    #
    # "1 0 0 1"
    # -------------------------------------------------

    numeric_chunks = re.findall(
        r"\d+",
        text,
    )

    digits = "".join(
        numeric_chunks
    )

    if len(digits) == 4:
        return digits

    return None


def extract_identity_fields(
    caller_text: str,
) -> dict[str, str]:
    """
    Extract member ID and phone last-four digits.
    """

    if not isinstance(
        caller_text,
        str,
    ):
        raise TypeError(
            "extract_identity_fields expected caller_text "
            f"to be str, got {type(caller_text).__name__}"
        )

    normalized = normalize_spoken_digits(
        caller_text
    )

    print(
        "NORMALIZED IDENTITY TEXT:",
        repr(normalized),
    )

    fields: dict[str, str] = {}

    member_id = _extract_member_id(
        normalized
    )

    if member_id:
        fields["member_id"] = member_id

    phone_last4 = _extract_phone_last4(
        normalized_text=normalized,
        member_id=member_id,
    )

    if phone_last4:
        fields["phone_last4"] = (
            phone_last4
        )

    return fields