# WebRAG API Reference

The WebRAG backend exposes a RESTful API over HTTP on `http://127.0.0.1:8000`. Cross-Origin Resource Sharing (CORS) is enabled to permit requests from the Chrome Extension (`chrome-extension://*`) and local development clients.

---

## Base URL

```text
http://127.0.0.1:8000/api/v1
```

---

## 1. Health & Status

### `GET /health`

Returns service health, embedding model specifications, active vector store status, and LLM configuration.

#### Request
```bash
curl -X GET http://127.0.0.1:8000/api/v1/health
```

#### Response (`200 OK`)
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "vector_store": "ready",
  "embeddings": "BAAI/bge-small-en-v1.5",
  "groq_configured": true,
  "model": "openai/gpt-oss-120b",
  "fallback_model": "openai/gpt-oss-20b"
}
```

---

## 2. Page Ingestion

### `POST /ingest/page`

Synchronously cleans, splits, embeds, and stores content from a single webpage. Content may be provided directly (via the extension's DOM extraction) or fetched on the server by URL.

#### Request Schema (`PageIngestRequest`)

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `url` | `string` | **Yes** | Target webpage URL |
| `title` | `string` | No | Page title (extracted by content script or `<title>`) |
| `text` | `string` | No | Pre-extracted clean text from browser DOM |
| `html` | `string` | No | Raw HTML for backend Readability parsing |
| `scope_id` | `string` | No | Target scope identifier. Auto-generated if omitted. |

#### Example Request
```bash
curl -X POST http://127.0.0.1:8000/api/v1/ingest/page \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://fastapi.tiangolo.com/tutorial/",
    "title": "Tutorial - User Guide - FastAPI",
    "text": "FastAPI is a modern, fast web framework for building APIs with Python...",
    "scope_id": "scope_page_fastapi_guide"
  }'
```

#### Response (`200 OK` - `PageIngestResponse`)
```json
{
  "scope_id": "scope_page_fastapi_guide",
  "page_title": "Tutorial - User Guide - FastAPI",
  "source_url": "https://fastapi.tiangolo.com/tutorial/",
  "chunks_indexed": 12,
  "already_indexed": false,
  "status": "completed",
  "message": "Successfully indexed 12 chunks."
}
```

#### Error Responses
* `400 Bad Request`: Unsafe URL rejected (private IP/SSRF) or HTTP fetch failure.
* `500 Internal Server Error`: Vector store indexing or database write failure.

---

## 3. Website Ingestion

### `POST /ingest/site`

Initiates an asynchronous, bounded background crawl of an entire website starting from a seed URL.

#### Request Schema (`SiteIngestRequest`)

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `url` | `string` | **Yes** | — | Base seed URL to begin crawling |
| `max_pages` | `integer` | No | `10` | Maximum pages to crawl and index |
| `max_depth` | `integer` | No | `2` | Maximum link depth from seed URL |
| `concurrency` | `integer` | No | `2` | Maximum concurrent HTTP GET requests |
| `scope_id` | `string` | No | Auto | Custom scope ID. Auto-generated if omitted. |

#### Example Request
```bash
curl -X POST http://127.0.0.1:8000/api/v1/ingest/site \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://docs.pytest.org/en/stable/",
    "max_pages": 15,
    "max_depth": 2,
    "concurrency": 2
  }'
```

#### Response (`200 OK` - `SiteIngestResponse`)
```json
{
  "job_id": "job_c9a1d48e01f2",
  "scope_id": "scope_site_docs_pytest_org",
  "status": "pending",
  "message": "Website crawl job initiated for https://docs.pytest.org/en/stable/"
}
```

---

### `GET /ingest/status/{job_id}`

Polls the active progress and metrics of a website crawl job.

#### Example Request
```bash
curl -X GET http://127.0.0.1:8000/api/v1/ingest/status/job_c9a1d48e01f2
```

#### Response (`200 OK` - `CrawlStatusResponse`)
```json
{
  "job_id": "job_c9a1d48e01f2",
  "scope_id": "scope_site_docs_pytest_org",
  "status": "running",
  "pages_crawled": 8,
  "pages_indexed": 7,
  "total_chunks": 54,
  "pages_failed": 1,
  "current_url": "https://docs.pytest.org/en/stable/getting-started.html",
  "error": null
}
```

#### Error Responses
* `404 Not Found`: Job ID does not exist in SQLite database.

---

## 4. Grounded Chat & Question Answering

### `POST /chat`

Submits a natural-language question against an indexed scope. Supports both factual Q&A and whole-document/website summarization.

#### Request Schema (`ChatRequest`)

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `scope_id` | `string` | **Yes** | — | Scope identifier containing indexed corpus |
| `question` | `string` | **Yes** | — | User's question or command (e.g. "Summarize") |
| `top_k` | `integer` | No | `5` | Relevant chunks to retrieve ($1 \le \text{top\_k} \le 20$) |

#### Example Request
```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "scope_id": "scope_page_fastapi_guide",
    "question": "What is the recommended way to declare query parameters?",
    "top_k": 5
  }'
```

#### Response (`200 OK` - `ChatResponse`)
```json
{
  "answer": "To declare query parameters in FastAPI, you define function parameters that are not part of the path parameters. You can set default values or use `None` to make them optional.",
  "citations": [
    {
      "source_url": "https://fastapi.tiangolo.com/tutorial/query-params/",
      "page_title": "Query Parameters - FastAPI",
      "chunk_index": 2,
      "content_excerpt": "When you declare other function parameters that are not part of the path parameters, they are automatically interpreted as 'query' parameters...",
      "relevance_score": 0.892
    }
  ],
  "scope_id": "scope_page_fastapi_guide",
  "context_found": true
}
```

---

## 5. Scope Management

### `GET /scopes/{scope_id}`

Retrieves complete metadata for an active scope, including all indexed pages, chunk counts, and content hashes.

#### Example Request
```bash
curl -X GET http://127.0.0.1:8000/api/v1/scopes/scope_page_fastapi_guide
```

#### Response (`200 OK` - `ScopeDetailsResponse`)
```json
{
  "scope_id": "scope_page_fastapi_guide",
  "type": "page",
  "base_url": "https://fastapi.tiangolo.com/tutorial/",
  "page_count": 1,
  "chunk_count": 12,
  "created_at": "2026-11-11T14:30:00.000000+00:00",
  "pages": [
    {
      "url": "https://fastapi.tiangolo.com/tutorial/",
      "title": "Tutorial - User Guide - FastAPI",
      "chunk_count": 12,
      "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "indexed_at": "2026-11-11T14:30:00.000000+00:00"
    }
  ]
}
```

---

### `DELETE /scopes/{scope_id}`

Permanently purges all vector embeddings from ChromaDB, all metadata and crawl jobs from SQLite, and all chat history for the specified scope.

#### Example Request
```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/scopes/scope_page_fastapi_guide
```

#### Response (`200 OK` - `DeleteScopeResponse`)
```json
{
  "deleted": true,
  "scope_id": "scope_page_fastapi_guide"
}
```
