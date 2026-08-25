from agent.llm.ollama import get_ollama_model
from agent.llm.schemas import IntentClassification


class OllamaIntentClassifier:
    def classify(
        self,
        caller_text: str,
    ) -> IntentClassification:
        return classify_intent_with_llm(
            caller_text
        )

def classify_intent_with_llm(
    caller_text: str,
) -> IntentClassification:
    try:
        model = get_ollama_model()

        structured_model = model.with_structured_output(
            IntentClassification
        )

        prompt = f"""
You classify healthcare patient-services requests.

Choose exactly one intent:

appointment
- booking
- rescheduling
- cancelling
- appointment availability

faq
- clinic hours
- locations
- policies
- preparation
- general clinic information

previsit_intake
- pre-visit questions
- intake information

other
- anything else

Caller:
{caller_text}
"""

        return structured_model.invoke(prompt)

    except Exception:  # noqa: BLE001
        return IntentClassification(
            intent="other",
            confidence=0.0,
        )
