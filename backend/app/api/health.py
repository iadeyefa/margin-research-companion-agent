from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings, settings_env_diagnostics
from app.services.research_llm import is_research_llm_configured

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    settings = get_settings()
    llm_ok = is_research_llm_configured()
    content: dict = {
        "status": "healthy",
        "services": {
            "api": "healthy",
            "research_llm": "configured" if llm_ok else "not_configured",
        },
    }
    if not llm_ok and settings.node_env == "development":
        content["config_hints"] = {
            **settings_env_diagnostics(),
            "message": (
                "LLM_PROVIDER auto tries Google when GOOGLE_API_KEY is set, then Ollama. "
                "Configure backend/.env and restart — see README (Environment variables)."
            ),
        }
    return JSONResponse(status_code=status.HTTP_200_OK, content=content)
