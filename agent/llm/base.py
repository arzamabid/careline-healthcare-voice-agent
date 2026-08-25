from typing import Protocol

from agent.llm.schemas import IntentClassification


class IntentClassifier(Protocol):
    def classify(
        self,
        caller_text: str,
    ) -> IntentClassification:
        ...

