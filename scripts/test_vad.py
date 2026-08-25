from agent.voice.vad import get_vad


def main() -> None:
    print("Loading Silero VAD...")

    vad = get_vad()

    print("Loaded:")
    print(type(vad).__name__)


if __name__ == "__main__":
    main()
