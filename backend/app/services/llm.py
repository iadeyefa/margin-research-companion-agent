from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_ollama import ChatOllama

from app.core.config import get_settings


settings = get_settings()

ollama = ChatOllama(
    base_url=settings.ollama_base_url,
    model=settings.ollama_model,
    temperature=0.3,
    num_ctx=2048,
)

sports_analysis_prompt = PromptTemplate.from_template(
    """
You are an expert sports analyst specializing in {sport}.
Provide detailed, data-driven analysis based on game statistics and context.

Context (recent games and stats):
{context}

User Question: {question}

Provide a comprehensive analysis with specific statistics and insights:
"""
)

analysis_chain = sports_analysis_prompt | ollama | StrOutputParser()


async def test_ollama_connection() -> bool:
    try:
        await ollama.ainvoke("Test connection. Reply with one word: working")
        return True
    except Exception as exc:
        print(f"Ollama connection failed: {exc}")
        return False
