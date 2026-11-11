import os
import time
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import pytest
from langchain_core.documents import Document

from app.config import get_groq_api_key, GROQ_MODEL, ALLOW_LOCALHOST
from app.llm import get_groq_llm, generate_grounded_answer, sanitize_error
from app.extractor import process_page_to_document, extract_from_html
from app.pipeline import ingest_document, query_rag
from app.vectorstore import get_vectorstore, delete_documents_by_scope, similarity_search_scope
from app.database import init_db, delete_scope_metadata, get_scope_documents, get_chat_history
from app.crawler import run_website_crawl, validate_url_safety

# ---------------------------------------------------------------------------
# Section 2: Groq Integration Verification
# ---------------------------------------------------------------------------

def test_groq_key_sanitization():
    leaked_str = "Error: Invalid key gsk_abc123xyz456SECRET in request url"
    sanitized = sanitize_error(leaked_str)
    assert "gsk_abc123xyz456SECRET" not in sanitized
    assert "gsk_***" in sanitized

def test_groq_missing_key_behavior(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    with pytest.raises(ValueError) as exc:
        get_groq_llm()
    assert "GROQ_API_KEY is not set" in str(exc.value)

    # Calling generate_grounded_answer with missing key returns helpful notice and context
    sample_context = [{
        "source_url": "https://example.com",
        "page_title": "Example",
        "content_excerpt": "Sample content about WebRAG."
    }]
    ans = generate_grounded_answer("What is WebRAG?", sample_context)
    assert "Groq API key is not configured" in ans

# ---------------------------------------------------------------------------
# Section 3: Grounded RAG Functionality & Citations
# ---------------------------------------------------------------------------

def test_rag_retrieval_and_source_citations():
    init_db()
    scope_id = "test_audit_rag_scope"
    delete_documents_by_scope(scope_id)
    delete_scope_metadata(scope_id)

    # Ingest document with specific technical facts
    doc_url = "https://webrag.dev/docs/spec"
    doc_title = "WebRAG Technical Specification"
    doc_text = (
        "WebRAG utilizes the BAAI/bge-small-en-v1.5 embedding model for vector generation. "
        "The recursive text splitter divides content into 1000-character chunks with a 200-character overlap. "
        "ChromaDB is employed as the persistent vector database with scope_id filtering."
    )

    s_id, title, count, _ = ingest_document(
        url=doc_url,
        title=doc_title,
        text=doc_text,
        scope_id=scope_id
    )
    assert count > 0

    # 1. Ask question with answer explicitly present
    q_present = "What chunk size and overlap does the recursive text splitter use?"
    answer, citations, context_found = query_rag(scope_id, q_present, top_k=3)

    assert context_found is True
    assert len(citations) > 0
    # Citation points to the correct source URL and page title
    assert citations[0].source_url == doc_url
    assert citations[0].page_title == doc_title
    assert "1000-character" in citations[0].content_excerpt
    assert "200-character" in citations[0].content_excerpt

    # 2. Ask question with answer completely absent from the indexed content
    q_absent = "What is the capital city of France?"
    retrieved_for_absent = similarity_search_scope(q_absent, scope_id, k=3)
    # The prompt explicitly mandates refusal when facts are not in context
    empty_ans = generate_grounded_answer(q_absent, [])
    assert "no relevant context was found" in empty_ans

    # 3. Clean up
    delete_documents_by_scope(scope_id)
    delete_scope_metadata(scope_id)

# ---------------------------------------------------------------------------
# Section 4: Multi-Page Website Crawling & Cross-Page Retrieval
# ---------------------------------------------------------------------------

class MockWebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/robots.txt":
            content = "User-agent: *\nDisallow: /admin\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(content.encode())
        elif self.path == "/sitemap.xml":
            content = """<?xml version="1.0" encoding="UTF-8"?>
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <url><loc>http://127.0.0.1:{port}/page1.html</loc></url>
            </urlset>
            """.format(port=self.server.server_port)
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(content.encode())
        elif self.path == "/page1.html":
            content = """<html><body>
                <h1>Page One: Overview</h1>
                <p>Welcome to the multi-page mock website. Page one discusses introductory concepts.</p>
                <a href="/page2.html">Go to Page Two</a>
                <a href="/page1.html">Duplicate Link to Page One</a>
                <a href="https://external-example.com/unrelated">External Link</a>
                <a href="/missing-404.html">Broken Page</a>
            </body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(content.encode())
        elif self.path == "/page2.html":
            content = """<html><body>
                <h1>Page Two: Architecture</h1>
                <p>Page two details the distributed architecture and caching mechanisms.</p>
                <a href="/page3.html">Go to Page Three</a>
            </body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(content.encode())
        elif self.path == "/page3.html":
            content = """<html><body>
                <h1>Page Three: Chunking Deep Dive</h1>
                <p>Page three explains recursive boundary splitting and tokenization.</p>
            </body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(content.encode())
        elif self.path == "/admin":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>Admin Page</body></html>")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logging noise in tests

def test_multipage_crawling_and_cross_page_retrieval(monkeypatch):
    import asyncio
    monkeypatch.setenv("ALLOW_LOCALHOST", "true")

    async def _run():
        init_db()

        # Find free port and spin up HTTP server
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()

        server = HTTPServer(('127.0.0.1', port), MockWebHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        base_url = f"http://127.0.0.1:{port}/page1.html"
        scope_id = f"test_crawl_scope_{port}"
        job_id = f"test_job_{port}"

        delete_documents_by_scope(scope_id)
        delete_scope_metadata(scope_id)

        async def on_page_extracted(url: str, html: str, target_scope: str):
            _, _, count, _ = ingest_document(url=url, html=html, scope_id=target_scope, scope_type="site")
            return count

        # Run crawl with limit of 10 pages, depth 3
        await run_website_crawl(
            job_id=job_id,
            scope_id=scope_id,
            base_url=base_url,
            max_pages=10,
            max_depth=3,
            concurrency=2,
            on_page_extracted=on_page_extracted
        )

        # Verify multiple documents entered the shared ingestion pipeline
        docs = get_scope_documents(scope_id)
        urls_indexed = [d["url"] for d in docs]

        assert len(docs) >= 3
        assert any("/page1.html" in u for u in urls_indexed)
        assert any("/page2.html" in u for u in urls_indexed)
        assert any("/page3.html" in u for u in urls_indexed)
        # External link was NOT crawled
        assert not any("external-example.com" in u for u in urls_indexed)

        # Verify cross-page retrieval
        # Query for Page 2 content
        _, cit_p2, found_p2 = query_rag(scope_id, "Tell me about distributed architecture and caching", top_k=2)
        assert found_p2
        assert any("/page2.html" in c.source_url for c in cit_p2)

        # Query for Page 3 content
        _, cit_p3, found_p3 = query_rag(scope_id, "What does page three explain about tokenization?", top_k=2)
        assert found_p3
        assert any("/page3.html" in c.source_url for c in cit_p3)

        server.shutdown()
        delete_documents_by_scope(scope_id)
        delete_scope_metadata(scope_id)

    asyncio.run(_run())

# ---------------------------------------------------------------------------
# Section 6: Data Integrity & Scope Isolation
# ---------------------------------------------------------------------------

def test_modified_content_replaces_old_chunks():
    init_db()
    scope_id = "test_replace_scope"
    url = "https://example.com/live-doc"

    delete_documents_by_scope(scope_id)
    delete_scope_metadata(scope_id)

    # Index Version 1
    v1_text = "Version 1: The primary database is PostgreSQL."
    ingest_document(url=url, title="DB Doc", text=v1_text, scope_id=scope_id)
    results_v1 = similarity_search_scope("PostgreSQL", scope_id, k=5)
    assert len(results_v1) == 1
    assert "PostgreSQL" in results_v1[0][0].page_content

    # Index Version 2 (modified text)
    v2_text = "Version 2: The primary database has migrated entirely to SQLite and ChromaDB."
    ingest_document(url=url, title="DB Doc", text=v2_text, scope_id=scope_id)

    # Verify old PostgreSQL chunk was replaced and no longer exists
    results_v2_old = similarity_search_scope("PostgreSQL", scope_id, k=5)
    assert not any("Version 1" in doc.page_content for doc, _ in results_v2_old)

    results_v2_new = similarity_search_scope("SQLite and ChromaDB", scope_id, k=5)
    assert any("Version 2" in doc.page_content for doc, _ in results_v2_new)

    delete_documents_by_scope(scope_id)
    delete_scope_metadata(scope_id)

def test_conversation_history_persistence():
    init_db()
    scope_id = "test_history_scope"
    delete_documents_by_scope(scope_id)
    delete_scope_metadata(scope_id)

    ingest_document(url="https://example.com/info", title="Info", text="WebRAG conversation persistence test.", scope_id=scope_id)

    query_rag(scope_id, "What is this test?", top_k=1)
    query_rag(scope_id, "What else is covered?", top_k=1)

    history = get_chat_history(scope_id)
    # 2 questions + 2 assistant answers = 4 messages
    assert len(history) == 4
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "What is this test?"
    assert history[1]["role"] == "assistant"

    delete_documents_by_scope(scope_id)
    delete_scope_metadata(scope_id)

# ---------------------------------------------------------------------------
# Section 7: Failure & Boundary Cases
# ---------------------------------------------------------------------------

def test_empty_webpage_handling():
    init_db()
    scope_id = "test_empty_scope"
    empty_html = "<html><head><title>Empty Page</title></head><body>   \n\n  </body></html>"
    s_id, title, count, already = ingest_document(
        url="https://example.com/empty",
        title="Empty Page",
        html=empty_html,
        scope_id=scope_id
    )
    # Empty page should not crash and should produce 0 chunks
    assert count == 0

def test_very_long_webpage_handling():
    init_db()
    scope_id = "test_long_scope"
    delete_documents_by_scope(scope_id)
    delete_scope_metadata(scope_id)

    # 50,000 character page
    long_text = ("WebRAG robust scalability test. Paragraph about retrieval-augmented generation. ") * 700
    s_id, title, count, _ = ingest_document(
        url="https://example.com/long",
        title="Long Document",
        text=long_text,
        scope_id=scope_id
    )
    assert count > 40  # Successfully chunked into 40+ chunks
    docs = get_scope_documents(scope_id)
    assert docs[0]["chunk_count"] == count

    delete_documents_by_scope(scope_id)
    delete_scope_metadata(scope_id)
