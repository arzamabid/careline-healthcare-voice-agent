from functools import lru_cache

from langchain_ollama import ChatOllama

from apps.api.config import get_settings


@lru_cache
def get_ollama_model() -> ChatOllama:
    settings = get_settings()

    if not settings.ollama_model:
        raise RuntimeError(
            "OLLAMA_MODEL is not configured."
        )

    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0,
    )
