import pytest
from langchain_core.documents import Document
from app.chunker import split_document

def test_split_document_metadata_preservation():
    doc = Document(
        page_content="WebRAG chunking test. " * 100,  # Long enough to split
        metadata={
            "source_url": "https://example.com/test",
            "page_title": "Chunker Test",
            "content_hash": "testhash12345",
        }
    )
    chunks = split_document(doc, "scope_abc")
    assert len(chunks) > 1
    for idx, c in enumerate(chunks):
        assert c.metadata["scope_id"] == "scope_abc"
        assert c.metadata["source_url"] == "https://example.com/test"
        assert c.metadata["page_title"] == "Chunker Test"
        assert c.metadata["content_hash"] == "testhash12345"
        assert c.metadata["chunk_index"] == idx
