from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://devmind:devmind@localhost:5432/devmind"
    redis_url: str = "redis://localhost:6379/0"
    api_cors_origins: str = "http://localhost:5173"
    persistence_enabled: bool = False
    embedding_provider: str = "local"
    embedding_model: str = "local-hash-v1"
    embedding_api_key: str | None = None
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_dimension: int = 1536
    llm_provider: str = "local"
    llm_model: str = "local-grounded-v1"
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: float = 30.0

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
