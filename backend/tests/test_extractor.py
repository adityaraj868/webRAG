import pytest
from app.extractor import (
    compute_content_hash,
    normalize_text,
    extract_from_html,
    process_page_to_document,
)

def test_compute_content_hash_deterministic():
    text1 = "Hello world   this is a test\n"
    text2 = "Hello world this is a test"
    assert compute_content_hash(text1) == compute_content_hash(text2)

def test_normalize_text():
    raw = "Line 1\n\n\n\nLine 2   with   extra  spaces\r\nLine 3"
    norm = normalize_text(raw)
    assert "\n\n\n" not in norm
    assert "Line 1\n\nLine 2 with extra spaces\nLine 3" == norm

def test_extract_from_html():
    html = """
    <!DOCTYPE html>
    <html>
      <head><title>WebRAG Knowledge Assistant</title></head>
      <body>
        <nav><a href="/home">Home</a></nav>
        <article>
          <h1>Overview of WebRAG</h1>
          <p>WebRAG is a browser-native retrieval-augmented generation engine.</p>
          <h2>Key Features</h2>
          <p>It supports both current page and entire website indexing.</p>
        </article>
        <footer>Copyright 2026</footer>
      </body>
    </html>
    """
    title, clean_text, headings = extract_from_html(html, "https://example.com/page")
    assert "WebRAG" in title
    assert "Overview of WebRAG" in headings
    assert "browser-native" in clean_text
    assert "Copyright 2026" not in clean_text  # Cleaned out footer

def test_process_page_to_document():
    doc = process_page_to_document(
        url="https://example.com/doc",
        title="Custom Title",
        text="Sample page text content.",
        scope_id="scope_123"
    )
    assert doc.metadata["scope_id"] == "scope_123"
    assert doc.metadata["source_url"] == "https://example.com/doc"
    assert doc.metadata["page_title"] == "Custom Title"
    assert "content_hash" in doc.metadata
    assert len(doc.metadata["content_hash"]) == 64
