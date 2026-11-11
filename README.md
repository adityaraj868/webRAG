# WebRAG — Browser-Native Knowledge Assistant

WebRAG is a browser-native website knowledge assistant built with Retrieval-Augmented Generation (RAG). It converts webpages and websites into searchable knowledge bases using a Chrome Extension side panel powered by a FastAPI backend.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│              Chrome Extension (Manifest V3)            │
│  ┌───────────────────────┐  ┌───────────────────────┐  │
│  │ Content Script        │  │ Side Panel UI (React) │  │
│  │ (DOM & Text Clean)    │  │ Tailwind, Lucide      │  │
│  └───────────┬───────────┘  └───────────┬───────────┘  │
└──────────────┼──────────────────────────┼──────────────┘
               │ JSON                     │ REST
               ▼                          ▼
┌────────────────────────────────────────────────────────┐
│                   FastAPI Backend                      │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Unified Ingestion & RAG Pipeline (pipeline.py)   │  │
│  │ 1. Normalize & Hash Content (extractor.py)       │  │
│  │ 2. RecursiveCharacterTextSplitter (chunker.py)   │  │
│  │ 3. BAAI/bge-small-en-v1.5 Embeddings             │  │
│  │ 4. Persistent ChromaDB Vector Store              │  │
│  │ 5. Strict Scope Isolation Filter                 │  │
│  │ 6. Grounded Groq Generation & Citations (llm.py) │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌───────────────────────┐  ┌───────────────────────┐  │
│  │ Bounded Site Crawler  │  │ SQLite Metadata       │  │
│  │ (robots, sitemap,     │  │ (Scopes, documents,   │  │
│  │  SSRF protection)     │  │  chat history)        │  │
│  └───────────────────────┘  └───────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

---

## Key Features

1. **Active Webpage Indexing**: Injects a clean content script into the active browser tab, strips clutter (scripts, navigation, footers, ads), extracts metadata and headings, and passes content to the backend.
2. **Bounded Website Crawling**: Crawls same-origin pages using sitemap.xml and internal links, respecting robots.txt and configurable concurrency/depth/page limits with SSRF validation.
3. **Unified Ingestion & RAG Pipeline**: Both page and website ingestion pass through the exact same processing pipeline.
4. **Smart Deduplication**: Computes SHA-256 hashes of normalized content to avoid re-embedding unchanged documents.
5. **Strict Scope Isolation**: Every document chunk is tagged with `scope_id`. ChromaDB retrieval filters strictly by `scope_id`, preventing cross-scope data contamination.
6. **Grounded Question Answering**: Retrieves top-5 relevant chunks, formats context, and generates answers strictly grounded in retrieved evidence using Groq (`llama-3.3-70b-versatile`).
7. **Clickable Source Citations**: Each answer includes expandable citations with chunk indices, similarity scores, and clickable links to open the original source in a new browser tab.
8. **Conversation History**: Stored in SQLite (never polluting the vector store).

---

## Technology Stack

- **Frontend**: React 19, TypeScript, Tailwind CSS, Lucide icons, Vite.
- **Browser API**: Chrome Manifest V3, Side Panel API, Content Scripts, ActiveTab.
- **Backend API**: Python 3.14 / FastAPI, Uvicorn, Pydantic v2.
- **RAG & Orchestration**: LangChain (`langchain-core`, `langchain-text-splitters`, `langchain-chroma`, `langchain-huggingface`, `langchain-groq`).
- **Embeddings**: `BAAI/bge-small-en-v1.5` (HuggingFace Sentence Transformers).
- **Vector Database**: ChromaDB (persistent local storage).
- **LLM**: Groq API (`llama-3.3-70b-versatile`).
- **Metadata Storage**: SQLite3.
- **Extraction**: Mozilla Readability (`readability-lxml`), BeautifulSoup4.

---

## Quickstart Guide

### 1. Backend Setup

```bash
# Navigate to the backend directory
cd backend

# Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure your Groq API key in .env
cp .env.example .env
# Edit .env and set your GROQ_API_KEY:
# GROQ_API_KEY=gsk_...
```

### 2. Start the Backend Server

```bash
# Run using the startup runner
PYTHONPATH=backend python3 backend/run.py

# Or directly with uvicorn
PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify backend health:
```bash
curl http://127.0.0.1:8000/api/v1/health
```

### 3. Build the Chrome Extension

```bash
# Navigate to the extension directory
cd extension

# Install npm dependencies
npm install

# Build extension for Chrome
npm run build
```

This compiles TypeScript, packages Tailwind styles, and outputs the production extension to `extension/dist/`.

### 4. Load Extension in Google Chrome

1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** toggle in the top-right corner.
3. Click **Load unpacked**.
4. Select the `extension/dist` folder from this repository.
5. Click on the **WebRAG** extension icon in your Chrome toolbar or press the side panel icon. The WebRAG side panel will open ready for use.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Service health status, model, and vector store readiness |
| `POST` | `/api/v1/ingest/page` | Index a single webpage (from DOM or direct URL) |
| `POST` | `/api/v1/ingest/site` | Asynchronously crawl and index a website |
| `GET` | `/api/v1/ingest/status/{job_id}` | Check website crawler job progress |
| `POST` | `/api/v1/chat` | Ask grounded natural-language questions within a scope |
| `GET` | `/api/v1/scopes/{scope_id}` | Retrieve scope metadata, indexed pages, and chunk counts |
| `DELETE` | `/api/v1/scopes/{scope_id}` | Clear all vectors and metadata for a scope |

---

## Automated Tests

Run the full automated test suite:

```bash
PYTHONPATH=backend ./venv/bin/pytest backend/tests -v
```

Test coverage includes:
- Content extraction, HTML cleaning, and SHA-256 hash calculation.
- LangChain recursive chunking and metadata preservation.
- Crawler link extraction and SSRF private IP validation.
- Content-hash deduplication (skips re-embedding unchanged documents).
- Multi-scope isolation in ChromaDB.
- Live FastAPI endpoint operations.
