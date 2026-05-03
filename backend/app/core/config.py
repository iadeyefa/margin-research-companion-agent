import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ENV_PATH = _BACKEND_DIR / ".env"
_REPO_ROOT_ENV = _BACKEND_DIR.parent / ".env"

# Env vars that are optional secrets: an empty string in the shell must not mask backend/.env.
_OPTIONAL_SECRET_ENV_NAMES = (
    "CEREBRAS_API_KEY",
    "SEMANTIC_SCHOLAR_API_KEY",
    "OPENALEX_API_KEY",
    "CORE_API_KEY",
    "RESEARCH_CONTACT_EMAIL",
)


def _prepare_env_files() -> None:
    for name in _OPTIONAL_SECRET_ENV_NAMES:
        raw = os.environ.get(name)
        if raw is not None and not raw.strip():
            os.environ.pop(name, None)
    for path in (_ENV_PATH, _REPO_ROOT_ENV):
        if path.is_file():
            load_dotenv(path, override=False)


def _default_sqlite_url() -> str:
    # Anchor the DB file to the backend package root so cwd (e.g. repo root vs backend/)
    # does not silently switch which SQLite file is used after restart.
    db_path = (_BACKEND_DIR / "research_companion.db").as_posix()
    return f"sqlite:///{db_path}"


class Settings(BaseSettings):
    database_url: str = Field(default_factory=_default_sqlite_url)
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
        # Always load backend/.env regardless of shell cwd (uvicorn from repo root, IDE, etc.)
        env_file=_ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        # If the shell exports CEREBRAS_API_KEY= (empty), don't let it override a real value from .env.
        env_ignore_empty=True,
    )

    @field_validator(
        "cerebras_api_key",
        "semantic_scholar_api_key",
        "openalex_api_key",
        "core_api_key",
        "research_contact_email",
        mode="before",
    )
    @classmethod
    def strip_optional_secrets(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()


@lru_cache
def get_settings() -> Settings:
    _prepare_env_files()
    return Settings()


def settings_env_diagnostics() -> dict:
    """For health checks (non-secret): whether expected dotenv files exist."""
    return {
        "backend_env_path": str(_ENV_PATH),
        "backend_env_exists": _ENV_PATH.is_file(),
        "repo_root_env_exists": _REPO_ROOT_ENV.is_file(),
    }
