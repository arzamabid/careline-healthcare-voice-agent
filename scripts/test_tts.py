from agent.voice.tts import synthesize_speech


def main() -> None:
    output = synthesize_speech(
        text=(
            "Hello. Your dermatology appointment "
            "has been successfully booked for tomorrow."
        ),
        output_path="data/audio/tts_test.wav",
    )

    print("Created:")
    print(output)


if __name__ == "__main__":
    main()
