from agent.llm.ollama import get_ollama_model


def main() -> None:
    model = get_ollama_model()

    response = model.invoke(
        "Reply with exactly the word OK."
    )

    print(response.content)


if __name__ == "__main__":
    main()
