import re
from typing import Literal

ConfirmationResult = Literal[
    "yes",
    "no",
    "unknown",
]


YES_RESPONSES = {
    "yes",
    "yeah",
    "yep",
    "yup",
    "yes please",
    "sure",
    "okay",
    "ok",
    "correct",
    "thats correct",
    "that is correct",
    "yes thats correct",
    "yes that is correct",
    "yes thats great",
    "yes that is great",
    "thats great",
    "that is great",
    "looks good",
    "sounds good",
    "everything is correct",
    "the information is correct",
    "the provided facts are correct",
    "i confirm",
    "confirm",
    "confirmed",
}


NO_RESPONSES = {
    "no",
    "nope",
    "nah",
    "no thanks",
    "no thank you",
    "dont",
    "do not",
    "dont do it",
    "do not do it",
    "cancel",
    "cancel that",
    "never mind",
    "nevermind",
    "stop",
    "incorrect",
    "thats incorrect",
    "that is incorrect",
    "not correct",
}


def normalize_confirmation_text(
    text: str,
) -> str:
    """
    Normalize speech-to-text confirmation responses.

    Examples:

        "YES!" -> "yes"
        "Yes, please." -> "yes please"
        "No, thank you." -> "no thank you"
        "That's correct." -> "thats correct"
    """

    if not isinstance(text, str):
        return ""

    normalized = text.lower().strip()

    # Normalize smart apostrophes.
    normalized = normalized.replace(
        "’",
        "'",
    )

    # Convert contractions before punctuation removal.
    normalized = re.sub(
        r"\bdon't\b",
        "dont",
        normalized,
    )

    normalized = re.sub(
        r"\bthat's\b",
        "thats",
        normalized,
    )

    normalized = re.sub(
        r"\bit's\b",
        "its",
        normalized,
    )

    # Remove punctuation.
    normalized = re.sub(
        r"[^a-z0-9\s]",
        " ",
        normalized,
    )

    # Collapse multiple spaces.
    normalized = " ".join(
        normalized.split()
    )

    return normalized


def parse_confirmation(
    text: str,
) -> ConfirmationResult:
    """
    Return:

        "yes"
        "no"
        "unknown"

    This should be used anywhere Careline asks
    for an explicit yes/no confirmation.
    """

    normalized = normalize_confirmation_text(
        text
    )

    if not normalized:
        return "unknown"

    # Exact matches first.
    if normalized in YES_RESPONSES:
        return "yes"

    if normalized in NO_RESPONSES:
        return "no"

    # Natural affirmative sentences.
    positive_prefixes = (
        "yes ",
        "yeah ",
        "yep ",
        "yup ",
        "sure ",
        "correct ",
        "okay ",
        "ok ",
        "i confirm ",
        "go ahead ",
    )

    if normalized.startswith(
        positive_prefixes
    ):
        return "yes"

    # Natural negative sentences.
    negative_prefixes = (
        "no ",
        "nope ",
        "nah ",
        "dont ",
        "do not ",
        "cancel ",
        "incorrect ",
        "not correct ",
    )

    if normalized.startswith(
        negative_prefixes
    ):
        return "no"

    return "unknown"
