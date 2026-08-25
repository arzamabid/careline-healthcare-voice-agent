from functools import lru_cache
from pathlib import Path

import soundfile as sf
from kokoro import KPipeline


@lru_cache
def get_tts_pipeline() -> KPipeline:
    return KPipeline(
        lang_code="a",
    )


def synthesize_speech(
    text: str,
    output_path: str | Path,
    voice: str = "af_heart",
) -> Path:
    pipeline = get_tts_pipeline()

    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    audio_parts = []

    generator = pipeline(
        text,
        voice=voice,
        speed=1.0,
    )

    for _, _, audio in generator:
        audio_parts.append(audio)

    if not audio_parts:
        raise RuntimeError(
            "Kokoro did not generate audio."
        )

    import numpy as np

    combined_audio = np.concatenate(
        audio_parts
    )

    sf.write(
        output_path,
        combined_audio,
        24000,
    )

    return output_path
