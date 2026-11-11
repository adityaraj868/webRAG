import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def initialize():
    init_db()

def test_health_endpoint():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "vector_store" in data

def test_page_ingest_and_query_flow():
    scope_id = "test_api_scope_1"

    # Ingest page
    resp = client.post("/api/v1/ingest/page", json={
        "url": "https://fastapi.tiangolo.com/tutorial",
        "title": "FastAPI Tutorial",
        "text": "FastAPI is a modern, fast web framework for building APIs with Python based on standard type hints.",
        "scope_id": scope_id,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_id"] == scope_id
    assert data["chunks_indexed"] > 0

    # Query scope details
    resp = client.get(f"/api/v1/scopes/{scope_id}")
    assert resp.status_code == 200
    scope_data = resp.json()
    assert scope_data["page_count"] == 1
    assert scope_data["chunk_count"] > 0

    # Query chat endpoint
    resp = client.post("/api/v1/chat", json={
        "scope_id": scope_id,
        "question": "What is FastAPI?",
        "top_k": 3
    })
    assert resp.status_code == 200
    chat_data = resp.json()
    assert "answer" in chat_data
    assert len(chat_data["citations"]) > 0
    assert chat_data["citations"][0]["source_url"] == "https://fastapi.tiangolo.com/tutorial"

    # Delete scope
    del_resp = client.delete(f"/api/v1/scopes/{scope_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

    # Check 404 after deletion
    resp_after = client.get(f"/api/v1/scopes/{scope_id}")
    assert resp_after.status_code == 404
