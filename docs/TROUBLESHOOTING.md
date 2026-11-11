# WebRAG Troubleshooting Guide

This guide covers common errors, edge cases, and recovery procedures across the WebRAG stack.

---

## 1. Environment & Dependency Issues

### Error: `bash: .venv/bin/activate: No such file or directory`
**Cause**: The Python virtual environment has not been created yet.
**Solution**:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

---

### Error: `error: externally-managed-environment`
**Cause**: On modern Linux distributions (Arch Linux, Debian 12+, Ubuntu 23+), system Python restricts global `pip install` commands.
**Solution**: Never install dependencies globally with `sudo pip`. Always activate a virtual environment first:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### Error: `bash: uvicorn: command not found`
**Cause**: Uvicorn is installed inside the virtual environment, but the virtual environment is not active in your current shell session.
**Solution**:
```bash
source backend/venv/bin/activate
# Or invoke directly via the venv path
PYTHONPATH=backend ./backend/venv/bin/uvicorn app.main:app --reload
```

---

## 2. Server Startup & Network Failures

### Error: `ModuleNotFoundError: No module named 'app'`
**Cause**: Python cannot locate the `app` package because the current working directory is not in `PYTHONPATH`.
**Solution**: Prefix commands with `PYTHONPATH=backend`:
```bash
PYTHONPATH=backend python3 backend/run.py
```

---

### Error: `[Errno 98] Address already in use` (Port 8000)
**Cause**: Another process or an orphaned Uvicorn worker is occupying port 8000.
**Solution**:
```bash
# Identify process using port 8000
lsof -i :8000
# Terminate the process (replace PID with actual PID)
kill -9 <PID>
```
Alternatively, configure a custom port in `backend/.env`:
```env
PORT=8001
```

---

## 3. Groq API & LLM Issues

### Error: `⚠️ Groq API key is not configured` / `GROQ_API_KEY is not set`
**Cause**: `GROQ_API_KEY` is missing or still set to the default placeholder `your_groq_api_key_here`.
**Solution**:
1. Open `backend/.env`.
2. Ensure `GROQ_API_KEY` is set to a valid key starting with `gsk_`:
   ```env
   GROQ_API_KEY=gsk_abc123...
   ```
3. The backend reloads `.env` dynamically; restarting the server is not necessary.

---

### Error: `Groq HTTP 429 Rate Limit for model 'openai/gpt-oss-120b'`
**Cause**: Free/developer tier Groq accounts enforce a strict Tokens-Per-Minute (TPM) limit (typically 6,000 to 8,000 TPM). When summarizing long documents (e.g. 200+ chunks), multiple sequential batches will hit this quota.
**Behavior**:
* WebRAG's resilient engine automatically catches HTTP 429 errors, reads the `Retry-After` response header, and sleeps until the token bucket resets.
* It does **not** fail over to the secondary model, preventing quota waste.
**Solution**:
* Allow the backoff timer to complete automatically.
* To reduce prompt size per batch, lower the batch token limit in `backend/.env`:
  ```env
  SUMMARIZATION_BATCH_TOKEN_LIMIT=4000
  ```

---

### Error: `The model does not exist or you do not have access to it (404)`
**Cause**: The configured primary model was deprecated or removed by Groq.
**Behavior**: WebRAG automatically switches to the configured fallback model (`openai/gpt-oss-20b`) and logs the failover.
**Solution**: Update `GROQ_MODEL` in `backend/.env` to an active model listed at `https://console.groq.com/docs/models`.

---

## 4. Chrome Extension & Side Panel Issues

### Error: Side panel shows `Failed to fetch` or `Cannot connect to backend`
**Cause**: The FastAPI server is not running or is listening on a different host/port.
**Solution**:
1. Verify the backend is active:
   ```bash
   curl http://127.0.0.1:8000/api/v1/health
   ```
2. If `curl` fails, start the server (`PYTHONPATH=backend python3 backend/run.py`).
3. Ensure no local firewall or VPN blocks localhost loopback connections.

---

### Error: Extension assets fail to load (`net::ERR_FILE_NOT_FOUND`)
**Cause**: Absolute paths in Vite bundle (`/assets/...`) fail to resolve in Chrome extension schemes (`chrome-extension://...`).
**Solution**: WebRAG's `extension/vite.config.ts` includes `base: './'`. Rebuild the bundle to generate relative asset paths:
```bash
cd extension
npm run build
```
Then navigate to `chrome://extensions/` and click **Reload**.

---

### Error: `Uncaught (in promise) Error: Could not establish connection. Receiving end does not exist.`
**Cause**: The active browser tab is a restricted Chrome page (`chrome://`, `chrome-extension://`, Chrome Web Store) where content scripts cannot execute.
**Solution**: Navigate to a standard webpage (`https://...` or `http://...`) and re-open the side panel.

---

## 5. RAG Retrieval & Ingestion Issues

### Symptom: `I cannot answer this question based on the indexed content...`
**Causes & Solutions**:
1. **Empty / Irrelevant Chunks**: Check that the active scope contains indexed pages. Select the scope in the side panel to view indexed page titles and chunk counts.
2. **Pronoun follow-ups without context**: If asking *"Who was he?"* on a fresh session with no prior conversation turns, the rewriter has no context. State the subject explicitly in the first question (e.g. *"Who was Nikola Tesla?"*).
3. **Information genuinely absent**: WebRAG strictly follows its grounding guardrails and refuses to fabricate facts that are not present in the indexed excerpts.

---

### Symptom: Single Page Ingestion yields 0 chunks
**Cause**: The target webpage relies heavily on client-side JavaScript (e.g. React/Vue SPA) that renders blank HTML on direct HTTP GET requests.
**Solution**: Open the page in your browser and use the **Current Page** indexing button. The content script will extract the fully hydrated DOM from the active tab.

---

### Symptom: ChromaDB Permission or Lock Errors
**Cause**: File permission mismatch or an unclean shutdown holding SQLite file locks in `./data/chroma`.
**Solution**:
```bash
# Ensure current user owns data directory
chown -R $USER:$USER data/
# If vector store is corrupted during testing, reset:
rm -rf data/chroma data/webrag.db
```
The backend will automatically recreate empty databases on next launch.
