from typing import Any

from pinecone import Pinecone

from app.core.config import get_settings
from app.services.embeddings import embed_text, embed_texts


settings = get_settings()


def _get_index():
    if not settings.pinecone_api_key:
        raise RuntimeError("PINECONE_API_KEY is not configured")
    pc = Pinecone(api_key=settings.pinecone_api_key)
    return pc.Index(settings.pinecone_index_name)


async def store_game_data(game_id: str, game_data: str, metadata: dict[str, Any]) -> None:
    vector = await embed_text(game_data)
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


async def store_text_records(
    records: list[dict[str, Any]],
    batch_size: int = 100,
    namespace: str | None = None,
) -> int:
    if not records:
        return 0

    index = _get_index()
    total = 0

    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        vectors = await embed_texts([record["text"] for record in batch])
        pinecone_vectors = [
            {
                "id": record["id"],
                "values": vector,
                "metadata": {**record.get("metadata", {}), "text": record["text"]},
            }
            for record, vector in zip(batch, vectors, strict=True)
        ]
        index.upsert(vectors=pinecone_vectors, namespace=namespace)
        total += len(pinecone_vectors)

    return total


async def retrieve_similar_games(
    query: str,
    top_k: int = 5,
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    vector = await embed_text(query)
    index = _get_index()
    results = index.query(
        vector=vector,
        top_k=top_k,
        include_metadata=True,
        filter=metadata_filter,
    )
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
