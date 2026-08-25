from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel


@lru_cache
def get_whisper_model() -> WhisperModel:
    return WhisperModel(
        "base.en",
        device="cpu",
        compute_type="int8",
    )


def transcribe_audio(
    audio_path: str | Path,
) -> str:
    model = get_whisper_model()

    segments, _ = model.transcribe(
        str(audio_path),
        beam_size=1,
        vad_filter=False,
    )

    text_parts = [
        segment.text.strip()
        for segment in segments
        if segment.text.strip()
    ]

    return " ".join(text_parts).strip()
