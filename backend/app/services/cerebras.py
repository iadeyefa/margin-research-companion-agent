import httpx

from app.core.config import get_settings


settings = get_settings()
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"


def is_cerebras_configured() -> bool:
    return bool(settings.cerebras_api_key)


async def generate_sports_analysis(question: str, context: str, sport: str = "NBA") -> str:
    if not settings.cerebras_api_key:
        raise RuntimeError("CEREBRAS_API_KEY is not configured")

    prompt = f"""
You are an expert {sport} analyst. Use only the provided context when making factual claims.
If the context is incomplete, say what the retrieved records show and avoid pretending to know more.
For prediction questions, do not present certainty. Give a grounded lean, name the evidence, and clearly state the limits of the available data.
Do not let one team dominate the answer unless the retrieved context strongly supports that. Compare the teams present in the context.

Retrieved context:
{context}

User question:
{question}

Write a clear, concise analysis with specific stats from the context. If the question asks who will win, include a short "Best grounded answer" line.
"""

    payload = {
        "model": settings.cerebras_model,
        "messages": [
            {
                "role": "system",
                "content": "You are a careful sports analyst who grounds answers in retrieved data.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 700,
    }

    headers = {
        "Authorization": f"Bearer {settings.cerebras_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(CEREBRAS_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    return data["choices"][0]["message"]["content"]
