from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./sports_agent.db"
    redis_url: str = "redis://localhost:6379"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    embeddings_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    pinecone_api_key: str = ""
    pinecone_index_name: str = "sports-analysis"
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
