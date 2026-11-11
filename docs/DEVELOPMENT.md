# WebRAG Development Guide

This guide provides step-by-step instructions for configuring, building, testing, and debugging WebRAG on a local workstation.

---

## 1. Prerequisites

Ensure the following tools are installed:

* **Linux / macOS / Windows (WSL2)**
* **Python**: Version `3.10` or higher (verified on Python `3.14`)
* **Node.js**: Version `18.0.0` or higher (Node `20+` recommended)
* **npm**: Version `9.0.0` or higher
* **Google Chrome**: Version `114` or higher (required for Chrome Side Panel API support)
* **Groq Cloud API Key**: Free or developer key from [console.groq.com](https://console.groq.com/)

---

## 2. Repository Structure

```
webRAG/
├── backend/                  # FastAPI server & RAG pipeline
│   ├── app/                  # Application modules
│   ├── tests/                # Automated pytest suite
│   ├── requirements.txt      # Python dependencies
│   ├── run.py                # Standalone startup runner
│   ├── .env.example          # Environment configuration template
│   └── .env                  # Local secret configuration (git-ignored)
├── extension/                # Chrome Extension (Manifest V3)
│   ├── public/               # Static assets & manifest.json
│   ├── src/                  # React sidepanel & content scripts
│   ├── package.json          # npm dependencies & build scripts
│   └── vite.config.ts        # Vite build configuration
├── docs/                     # Architectural & technical documentation
├── data/                     # Local SQLite & ChromaDB storage (git-ignored)
├── .gitignore                # Source control exclusions
└── README.md                 # Project landing page
```

---

## 3. Backend Setup

### A. Virtual Environment Setup

From the repository root:

```bash
# Navigate to the backend directory
cd backend

# Create a Python virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate
```

> [!TIP]
> On Arch Linux, Debian, or Ubuntu systems where system-wide packages are managed by package managers, using a local virtual environment avoids `externally-managed-environment` errors.

### B. Dependency Installation

Install backend dependencies using `pip`:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Verify key dependencies:
```bash
python3 -c "import fastapi, chromadb, langchain_groq, tiktoken, sentence_transformers; print('Backend dependencies loaded successfully.')"
```

### C. Environment Configuration

Copy the example configuration to `.env`:

```bash
cp .env.example .env
```

Edit `backend/.env` and supply your Groq API key:

```env
# WebRAG Environment Configuration
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=openai/gpt-oss-120b
GROQ_FALLBACK_MODEL=openai/gpt-oss-20b
MODEL_CONTEXT_WINDOW=131072
SAFETY_MARGIN_TOKENS=4096
EXPECTED_COMPLETION_TOKENS=4096
SUMMARIZATION_BATCH_TOKEN_LIMIT=6000
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
CHROMA_PERSIST_DIR=./data/chroma
SQLITE_DB_PATH=./data/webrag.db
HOST=127.0.0.1
PORT=8000
```

> [!IMPORTANT]
> The backend dynamically checks `backend/.env` on disk. Updating your API key does not require restarting the server.

### D. Starting the Backend Server

Start the server using either the startup runner or Uvicorn directly:

```bash
# Option 1: Using run.py
PYTHONPATH=backend python3 backend/run.py

# Option 2: Using Uvicorn with hot reload
PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify service readiness:
```bash
curl http://127.0.0.1:8000/api/v1/health
```

Expected response:
```json
{"status":"healthy","version":"1.0.0","vector_store":"ready","embeddings":"BAAI/bge-small-en-v1.5","groq_configured":true,"model":"openai/gpt-oss-120b","fallback_model":"openai/gpt-oss-20b"}
```

---

## 4. Frontend & Chrome Extension Setup

### A. Install npm Dependencies

From the repository root:

```bash
cd extension
npm install
```

### B. Build Extension Bundle

Build the production extension bundle:

```bash
npm run build
```

This compiles TypeScript, packages Tailwind CSS styles, copies manifest assets, and outputs the final extension to `extension/dist/`.

Verify that `extension/dist/manifest.json` and `extension/dist/sidepanel.html` exist.

---

## 5. Loading the Extension in Google Chrome

1. Open Google Chrome and navigate to:
   ```text
   chrome://extensions/
   ```
2. Enable the **Developer mode** toggle in the top-right corner.
3. Click the **Load unpacked** button in the top-left toolbar.
4. In the file picker, select the `extension/dist` directory inside this repository.
5. Confirm that **WebRAG** appears in your installed extensions list.
6. Open any public documentation webpage (e.g. `https://fastapi.tiangolo.com/`).
7. Click the **WebRAG** extension icon or Chrome Side Panel button to launch the assistant.

---

## 6. Running Automated Tests

WebRAG includes an automated test suite with 34 unit and integration tests.

Run all tests from the repository root:

```bash
PYTHONPATH=backend ./backend/venv/bin/pytest backend/tests -v
```

### Test Coverage Highlights

* **`test_api.py`**: Health endpoint and synchronous page ingest/query workflows.
* **`test_audit_verification.py`**: Groq key sanitization, missing key handling, multi-page crawling, hash replacement, and long-page handling.
* **`test_chunker.py`**: Recursive chunking and metadata preservation.
* **`test_context_and_summarization.py`**: Summarization detection, pronoun resolution, and multi-turn workflows.
* **`test_crawler.py`**: SSRF protection, private IP blocking, and internal link extraction.
* **`test_extractor.py`**: Readability extraction, HTML cleaning, and SHA-256 hash determinism.
* **`test_model_fallback_and_token_budget.py`**: Model configuration, fallback on 500, HTTP 429 backoff, `tiktoken` budget calculation, dynamic batching, and recent-message chronological ordering.
* **`test_pipeline.py`**: Deduplication and ChromaDB scope isolation.

---

## 7. Development Workflow & Hot Reloading

* **Backend Changes**: When running with `--reload`, Uvicorn automatically reloads application code when files in `backend/app/` are modified.
* **Extension Changes**: When modifying files in `extension/src/`, re-run `npm run build` and click the **Reload (circular arrow)** button on `chrome://extensions/` to update the extension.
