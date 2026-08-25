from agent.llm.intent import (
    classify_intent_with_llm,
)


def test(text: str) -> None:
    result = classify_intent_with_llm(text)

    print()
    print("TEXT:", text)
    print("INTENT:", result.intent)
    print("CONFIDENCE:", result.confidence)


def main() -> None:
    test(
        "I want to move my dermatology visit "
        "to next Tuesday."
    )

    test(
        "What time does the North Clinic close?"
    )

    test(
        "I need to complete the questions "
        "before my visit."
    )

    test(
        "Can you tell me tomorrow's weather?"
    )


if __name__ == "__main__":
    main()
