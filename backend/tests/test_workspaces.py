from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_workspace_brief_create_read_delete():
    created_workspace = client.post("/api/workspaces/", json={"title": "Test workspace"})
    assert created_workspace.status_code == 201
    workspace_id = created_workspace.json()["id"]

    paper = {
        "source": "arxiv",
        "external_id": "1234.5678",
        "title": "Test Paper",
        "abstract": "A test abstract.",
        "authors": ["A. Author"],
        "venue": "arXiv",
        "year": 2026,
        "publication_date": None,
        "doi": "10.1234/example",
        "url": "https://example.com/paper",
        "pdf_url": None,
        "citation_count": 1,
        "open_access": True,
    }

    created = client.post(
        f"/api/workspaces/{workspace_id}/briefs",
        json={
            "mode": "summary",
            "style": "concise",
            "title": "Summary",
            "body": "Overview\n\nA concise summary [1].",
            "source_papers": [paper],
        },
    )
    assert created.status_code == 201
    brief_id = created.json()["id"]

    detail = client.get(f"/api/workspaces/{workspace_id}")
    assert detail.status_code == 200
    briefs = detail.json()["briefs"]
    assert len(briefs) == 1
    assert briefs[0]["style"] == "concise"
    assert briefs[0]["source_papers"][0]["title"] == "Test Paper"

    deleted = client.delete(f"/api/workspaces/{workspace_id}/briefs/{brief_id}")
    assert deleted.status_code == 204

    detail_after_delete = client.get(f"/api/workspaces/{workspace_id}")
    assert detail_after_delete.status_code == 200
    assert detail_after_delete.json()["briefs"] == []


def test_workspace_state_and_paper_note_persist():
    created_workspace = client.post("/api/workspaces/", json={"title": "State test"})
    assert created_workspace.status_code == 201
    workspace_id = created_workspace.json()["id"]

    state = client.put(
        f"/api/workspaces/{workspace_id}/state/selection",
        json={"value": {"papers": [{"source": "arxiv", "external_id": "1"}]}},
    )
    assert state.status_code == 200
    assert state.json()["value"]["papers"][0]["external_id"] == "1"

    note = client.put(
        f"/api/workspaces/{workspace_id}/paper-notes/arxiv/1",
        json={"note": "Important baseline."},
    )
    assert note.status_code == 200

    detail = client.get(f"/api/workspaces/{workspace_id}")
    payload = detail.json()
    assert payload["state"][0]["state_key"] == "selection"
    assert payload["paper_notes"][0]["note"] == "Important baseline."
