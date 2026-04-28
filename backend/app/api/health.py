from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.services.research_llm import is_research_llm_configured

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "services": {
                "api": "healthy",
                "research_llm": "configured" if is_research_llm_configured() else "not_configured",
            },
        },
    )
