from typing import Literal

from pydantic import BaseModel


class IntentClassification(BaseModel):
    intent: Literal[
        "appointment",
        "faq",
        "previsit_intake",
        "other",
    ]

    confidence: float
