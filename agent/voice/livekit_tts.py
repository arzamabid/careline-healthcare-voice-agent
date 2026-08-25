import asyncio
import tempfile

import soundfile as sf
from livekit.agents import tts, utils
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    APIConnectOptions,
)

from agent.voice.tts import synthesize_speech


class KokoroTTS(tts.TTS):
    def __init__(self) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(
                streaming=False,
            ),
            sample_rate=24000,
            num_channels=1,
        )

    @property
    def model(self) -> str:
        return "kokoro"

    @property
    def provider(self) -> str:
        return "local"

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ):
        return KokoroChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
        )


class KokoroChunkedStream(tts.ChunkedStream):
    def __init__(
        self,
        *,
        tts: KokoroTTS,
        input_text: str,
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(
            tts=tts,
            input_text=input_text,
            conn_options=conn_options,
        )

        self._tts = tts

    async def _run(
        self,
        output_emitter: tts.AudioEmitter,
    ) -> None:
        with tempfile.NamedTemporaryFile(
            suffix=".wav"
        ) as tmp:
            await asyncio.to_thread(
                synthesize_speech,
                self._input_text,
                tmp.name,
            )

            audio, sample_rate = sf.read(
                tmp.name,
                dtype="int16",
            )

            output_emitter.initialize(
                request_id=utils.shortuuid(),
                sample_rate=sample_rate,
                num_channels=1,
                mime_type="audio/pcm",
            )

            output_emitter.push(
                audio.tobytes()
            )
