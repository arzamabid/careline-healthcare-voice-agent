from functools import lru_cache

from livekit.plugins import silero


@lru_cache
def get_vad():
    return silero.VAD.load()
