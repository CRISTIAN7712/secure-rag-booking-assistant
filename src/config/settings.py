from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated environment configuration."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")
    postgres_user: str = "vector_user"
    postgres_password: str = "change_me"
    postgres_db: str = "vector_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = Field(default=800, ge=100)
    chunk_overlap: int = Field(default=120, ge=0)
    log_level: str = "INFO"
    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_name: str = "pgvector-rag-chatbot"
    openrouter_site_url: str = "http://localhost:8000"
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_max_context_chars: int = Field(default=12_000, ge=1_000, le=100_000)
    admin_api_key: str = ""
    privacy_mode: bool = True
    expose_source_text: bool = False

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
