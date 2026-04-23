from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.services.llm import test_ollama_connection
from app.services.pinecone import test_pinecone_connection

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    ollama_healthy = await test_ollama_connection()
    pinecone_healthy = await test_pinecone_connection()
    all_healthy = ollama_healthy and pinecone_healthy

    return JSONResponse(
        status_code=status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if all_healthy else "degraded",
            "services": {
                "ollama": "healthy" if ollama_healthy else "unhealthy",
                "pinecone": "healthy" if pinecone_healthy else "unhealthy",
            },
        },
    )
