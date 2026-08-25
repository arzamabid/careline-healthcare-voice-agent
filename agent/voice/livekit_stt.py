from livekit.agents import stt
from livekit.agents.types import APIConnectOptions
from livekit.agents.utils import AudioBuffer

from agent.voice.stt import get_whisper_model


class FasterWhisperSTT(stt.STT):
    def __init__(self) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(
                streaming=False,
                interim_results=False,
            )
        )

    @property
    def model(self) -> str:
        return "faster-whisper-base.en"

    @property
    def provider(self) -> str:
        return "local"

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language="en",
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        import tempfile
        import wave

        frame = buffer

        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=True,
        ) as tmp:
            with wave.open(tmp.name, "wb") as wav:
                wav.setnchannels(frame.num_channels)
                wav.setsampwidth(2)
                wav.setframerate(frame.sample_rate)
                wav.writeframes(frame.data)

            model = get_whisper_model()

            segments, _info = model.transcribe(
                tmp.name,
                beam_size=1,
            )

            text = " ".join(
                segment.text.strip()
                for segment in segments
            ).strip()

        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[
                stt.SpeechData(
                    language="en",
                    text=text,
                    confidence=1.0,
                )
            ],
        )
