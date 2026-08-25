from agent.llm.fake import (
    FakeIntentClassifier,
)


def test_fake_model_is_deterministic() -> None:
    classifier = FakeIntentClassifier()

    first = classifier.classify(
        "I need an appointment."
    )

    second = classifier.classify(
        "I need an appointment."
    )

    assert first == second
    assert first.intent == "appointment"
