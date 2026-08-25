from agent.voice.stt import transcribe_audio


def main() -> None:
    # audio_path = "data/audio/stt_test.aiff"
    audio_path = "data/audio/my_voice.m4a"
    print("Transcribing...")
    text = transcribe_audio(audio_path)

    print()
    print("TRANSCRIPT:")
    print(text)


if __name__ == "__main__":
    main()
