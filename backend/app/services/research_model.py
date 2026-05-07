from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import get_settings


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).strip()
    return str(content or "").strip()


def _build_google_chat(temperature: float):
    from langchain_google_genai import ChatGoogleGenerativeAI

    settings = get_settings()
    if not settings.google_api_key:
        return None
    return ChatGoogleGenerativeAI(
        model=settings.google_model,
        google_api_key=settings.google_api_key,
        temperature=temperature,
    )


def _build_ollama_chat(temperature: float):
    from langchain_ollama import ChatOllama

    settings = get_settings()
    key = settings.ollama_api_key.strip()
    client_kwargs: dict[str, Any] = {}
    if key:
        # Ollama Cloud and other hosted endpoints expect Bearer auth (local Ollama ignores this).
        client_kwargs["headers"] = {"Authorization": f"Bearer {key}"}
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=temperature,
        client_kwargs=client_kwargs or {},
    )


def llm_configured() -> bool:
    settings = get_settings()
    if settings.llm_provider == "google":
        return bool(settings.google_api_key)
    # auto / ollama always attemptable; google requires a key.
    return True


async def invoke_research_llm(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> tuple[str, str]:
    settings = get_settings()

    provider = (settings.llm_provider or "auto").strip().lower()
    candidates: list[tuple[str, Any]] = []
    if provider == "google":
        chat = _build_google_chat(temperature)
        if chat is not None:
            candidates.append(("google", chat))
    elif provider == "ollama":
        candidates.append(("ollama", _build_ollama_chat(temperature)))
    else:
        # auto: prefer Google Flash Lite if key exists, then local Ollama.
        g = _build_google_chat(temperature)
        if g is not None:
            candidates.append(("google", g))
        candidates.append(("ollama", _build_ollama_chat(temperature)))

    if not candidates:
        raise RuntimeError("No LLM providers are configured.")

    errors: list[str] = []
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    for name, chat in candidates:
        try:
            result = await chat.ainvoke(messages)
            text = _text_from_content(getattr(result, "content", ""))
            if text:
                return text, name
            errors.append(f"{name}: empty response")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")

    raise RuntimeError("All LLM providers failed: " + " | ".join(errors))
