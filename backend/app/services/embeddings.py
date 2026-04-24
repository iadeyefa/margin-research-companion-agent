import asyncio

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings


settings = get_settings()
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embeddings_model)
    return _model


def _embed_text_sync(text: str) -> list[float]:
    vector = _get_model().encode(text, normalize_embeddings=True)
    return vector.tolist()


def _embed_texts_sync(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    vectors = _get_model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    return [vector.tolist() for vector in vectors]


async def embed_text(text: str) -> list[float]:
    return await asyncio.to_thread(_embed_text_sync, text)


async def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    return await asyncio.to_thread(_embed_texts_sync, texts, batch_size)
