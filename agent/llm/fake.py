from agent.llm.schemas import IntentClassification


class FakeIntentClassifier:
    def classify(
        self,
        caller_text: str,
    ) -> IntentClassification:
        text = caller_text.lower()

        if "appointment" in text:
            intent = "appointment"

        elif "clinic" in text:
            intent = "faq"

        elif "intake" in text:
            intent = "previsit_intake"

        else:
            intent = "other"

        return IntentClassification(
            intent=intent,
            confidence=1.0,
        )
