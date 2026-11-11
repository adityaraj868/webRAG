import pytest
from app.pipeline import ingest_document, query_rag
from app.vectorstore import get_vectorstore, delete_documents_by_scope
from app.database import init_db, delete_scope_metadata

@pytest.fixture(autouse=True)
def setup_teardown():
    init_db()
    yield
    delete_documents_by_scope("test_scope_a")
    delete_documents_by_scope("test_scope_b")
    delete_scope_metadata("test_scope_a")
    delete_scope_metadata("test_scope_b")

def test_ingest_and_hash_deduplication():
    scope_id = "test_scope_a"
    url = "https://test.example.com/page1"
    content = "WebRAG is a browser-native retrieval-augmented generation assistant."

    # First ingest
    s_id, title, count1, already1 = ingest_document(
        url=url,
        title="Page 1",
        text=content,
        scope_id=scope_id,
        scope_type="page"
    )
    assert s_id == scope_id
    assert count1 > 0
    assert not already1

    # Second ingest with same content should skip re-embedding
    s_id, title, count2, already2 = ingest_document(
        url=url,
        title="Page 1",
        text=content,
        scope_id=scope_id,
        scope_type="page"
    )
    assert already2
    assert count2 == 0

def test_scope_isolation():
    scope_a = "test_scope_a"
    scope_b = "test_scope_b"

    # Index Apple info into scope A
    ingest_document(
        url="https://apples.org/info",
        title="Apples Info",
        text="Apples are delicious red or green fruits rich in antioxidants.",
        scope_id=scope_a
    )

    # Index Quantum Computing into scope B
    ingest_document(
        url="https://quantum.org/info",
        title="Quantum Info",
        text="Quantum computers leverage qubits and superposition to process information.",
        scope_id=scope_b
    )

    # Query scope A for quantum - should find 0 context
    _, citations_a, context_found_a = query_rag(scope_a, "Tell me about qubits and superposition")
    for cit in citations_a:
        assert "quantum.org" not in cit.source_url

    # Query scope B for quantum - should retrieve Quantum Info
    _, citations_b, context_found_b = query_rag(scope_b, "Tell me about qubits")
    assert context_found_b
    assert any("quantum.org" in cit.source_url for cit in citations_b)
