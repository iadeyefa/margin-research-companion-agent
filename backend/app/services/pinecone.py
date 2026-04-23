from typing import Any

from pinecone import Pinecone

from app.core.config import get_settings
from app.services.llm import embeddings


settings = get_settings()


def _get_index():
    if not settings.pinecone_api_key:
        raise RuntimeError("PINECONE_API_KEY is not configured")
    pc = Pinecone(api_key=settings.pinecone_api_key)
    return pc.Index(settings.pinecone_index_name)


async def store_game_data(game_id: str, game_data: str, metadata: dict[str, Any]) -> None:
    vector = await embeddings.aembed_query(game_data)
    index = _get_index()
    index.upsert(
        vectors=[
            {
                "id": game_id,
                "values": vector,
                "metadata": {**metadata, "text": game_data},
            }
        ]
    )


async def retrieve_similar_games(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    vector = await embeddings.aembed_query(query)
    index = _get_index()
    results = index.query(vector=vector, top_k=top_k, include_metadata=True)
    matches = getattr(results, "matches", None)
    if matches is None and isinstance(results, dict):
        matches = results.get("matches", [])
    matches = matches or []

    def _match_value(match: Any, key: str, default: Any = None) -> Any:
        if isinstance(match, dict):
            return match.get(key, default)
        return getattr(match, key, default)

    return [
        {
            "id": _match_value(match, "id"),
            "score": _match_value(match, "score"),
            "metadata": _match_value(match, "metadata", {}),
        }
        for match in matches
    ]


async def test_pinecone_connection() -> bool:
    try:
        _get_index().describe_index_stats()
        return True
    except Exception as exc:
        print(f"Pinecone connection failed: {exc}")
        return False
