from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./research_companion.db"
    redis_url: str = "redis://localhost:6379"
    cerebras_api_key: str = ""
    cerebras_model: str = "llama3.1-8b"
    research_contact_email: str = ""
    semantic_scholar_api_key: str = ""
    openalex_api_key: str = ""
    core_api_key: str = ""
    jwt_secret: str = "dev-secret"
    port: int = 3000
    node_env: str = "development"
    frontend_url: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
