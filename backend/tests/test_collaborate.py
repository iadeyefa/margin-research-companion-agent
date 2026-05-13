from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_collaborate_opener():
    resp = client.post("/api/research/search/collaborate", json={"messages": [], "desired_catalog_count": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["phase"] == "asking"
    assert data["search"] is None
    assert isinstance(data["quick_replies"], list)
    assert len(data["assistant_message"]) > 10


def test_collaborate_rejects_when_last_turn_not_user():
    resp = client.post(
        "/api/research/search/collaborate",
        json={
            "messages": [{"role": "assistant", "content": "Only me."}],
            "desired_catalog_count": 2,
        },
    )
    assert resp.status_code == 400


def test_collaborate_heuristic_fallback_with_user_turn():
    """Without Cerebras, first substantive reply can finish in one ready turn."""
    resp = client.post(
        "/api/research/search/collaborate",
        json={
            "messages": [
                {"role": "assistant", "content": "Opening."},
                {
                    "role": "user",
                    "content": "Machine learning benchmarking for retrieval augmented generation models",
                },
            ],
            "desired_catalog_count": 2,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["phase"] in {"asking", "ready"}
    if data["phase"] == "ready":
        search = data["search"]
        assert search is not None
        assert search["query"]
        assert len(search["sources"]) <= 2
