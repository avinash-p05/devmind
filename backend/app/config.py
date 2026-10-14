from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://devmind:devmind@localhost:5432/devmind"
    redis_url: str = "redis://localhost:6379/0"
    api_cors_origins: str = "http://localhost:5173"

    # ---- Chat model: any OpenAI-compatible API ----
    # Local development: Ollama (`ollama pull llama3.2`). Production: the OpenAI API, e.g.
    # LLM_BASE_URL=https://api.openai.com/v1, LLM_API_KEY=sk-..., LLM_MODEL=gpt-4o-mini.
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"  # Ollama ignores the key, but the SDK requires one
    llm_model: str = "llama3.2"

    # ---- Embeddings: "local" (fastembed, free, CPU) or "openai" (uses the LLM_* client) ----
    embedding_provider: str = "local"
    local_embedding_model: str = "BAAI/bge-small-en-v1.5"
    openai_embedding_model: str = "text-embedding-3-small"
    # The pgvector column is created with this size. Changing it requires re-indexing.
    # bge-small = 384; text-embedding-3-small is called with dimensions=384 to match.
    embedding_dimension: int = 384

    max_completion_tokens: int = 600  # per-answer cap so one question cannot run up cost
    llm_timeout_seconds: float = 30.0

    # ---- Chunking ----
    chunk_size: int = 1000  # characters per chunk
    chunk_overlap: int = 150  # characters shared between neighbouring chunks

    # ---- Retrieval ----
    top_k: int = 5
    # Below this best cosine similarity the agent refuses instead of calling the LLM.
    # Calibrated for bge-small on the eval set: off-topic questions top out at ~0.54, answerable
    # questions start at ~0.66. Re-tune whenever the embedding model changes.
    min_score: float = 0.60

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
