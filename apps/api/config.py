from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CareLine Healthcare Voice Agent"
    environment: str = "development"
    debug: bool = True

    database_url: str = (
        "postgresql+psycopg://careline:careline@localhost:5433/careline"
    )

    test_database_url: str = "sqlite:///./test.db"

    ollama_base_url: str = "http: // localhost: 11434"
    ollama_model: str = "qwen3:4b - instruct"

    livekit_url: str = "ws://localhost:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "devsecret"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
