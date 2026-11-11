# WebRAG Security Policy & Architecture

This document describes the security model, trust boundaries, and defensive controls implemented across WebRAG.

---

## 1. Threat Model & Trust Boundaries

```
[Untrusted Web Content] ──> [Chrome Content Script] ──> [FastAPI Backend] ──> [Local Storage & Groq]
         │                              │                        │
  Malicious HTML,                DOM Sanitization         SSRF Validation,
  Tracking Scripts               (scripts removed)        Scope Isolation,
                                                          Key Redaction
```

WebRAG operates as a local workstation developer tool. It processes untrusted web documents while protecting:
1. **Local System Resources**: Preventing Server-Side Request Forgery (SSRF) and local network probing.
2. **API Credentials**: Protecting Groq API keys from accidental leakage in logs or responses.
3. **Data Boundary**: Preventing cross-scope data contamination between unrelated websites.

---

## 2. API Key Protection

* **Environment Variable Storage**: The Groq API key (`GROQ_API_KEY`) is stored exclusively on the backend in `backend/.env` or the host process environment.
* **Never Exposed to Client**: The Chrome Extension never receives, stores, or handles the Groq API key.
* **Automated Log Sanitization**: All error handlers pass messages through [`sanitize_error`](file:///home/epsilon/Projects/webRAG/backend/app/llm.py):
  ```python
  def sanitize_error(error_msg: str) -> str:
      return re.sub(r'gsk_[a-zA-Z0-9_\-]+', 'gsk_***', str(error_msg))
  ```
  Any Groq credential pattern (`gsk_...`) that might appear in an HTTP stack trace or API error is redacted to `gsk_***` before logging or returning to the client.
* **Source Control Exclusion**: The root [`.gitignore`](file:///home/epsilon/Projects/webRAG/.gitignore) explicitly excludes all `.env`, `.env.*`, and `*.env` files. Only [`.env.example`](file:///home/epsilon/Projects/webRAG/backend/.env.example) with placeholder values is committed.

---

## 3. Server-Side Request Forgery (SSRF) Protection

When ingesting a webpage by URL or running a bounded crawl, the backend fetches content over the network. To prevent SSRF attacks against internal infrastructure, [`validate_url_safety`](file:///home/epsilon/Projects/webRAG/backend/app/crawler.py) inspects every target URL:

1. **Protocol Restriction**: Rejects all schemes other than `http` and `https`. Schemes such as `file://`, `gopher://`, `ftp://`, or `data:` are blocked.
2. **DNS Resolution**: Resolves target hostnames to IP addresses before initiating connections.
3. **Blacklisted IP Ranges**: Rejects connection attempts to internal, loopback, or private networks:
   * **Loopback**: `127.0.0.0/8`, `::1`
   * **Private IPv4 (RFC 1918)**: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
   * **Link-Local & Cloud Metadata**: `169.254.0.0/16`, `fe80::/10`. This explicitly prevents access to AWS/GCP instance metadata endpoints (`http://169.254.169.254/`).
   * **Unique Local Addresses (IPv6 ULA)**: `fc00::/7`
4. **Development Testing Bypass**: Localhost checking can be relaxed for automated mock tests by setting `ALLOW_LOCALHOST=true` in `backend/.env`.

---

## 4. Crawl Security & Origin Restrictions

* **Strict Same-Origin Policy**: The crawler compares the hostname (`netloc`) of every discovered link against the seed URL. External links and alternate subdomains are discarded.
* **Robots.txt Compliance**: Crawl paths evaluate `robots.txt` disallow rules using `urllib.robotparser`.
* **Bounded Resource Allocation**: Hard limits on `max_pages` (default 10), `max_depth` (default 2), and `concurrency` (default 2) prevent denial-of-service on remote servers.

---

## 5. Scope Isolation & Data Privacy

* **Vector Search Filtering**: Every chunk in ChromaDB is indexed with a `scope_id` metadata tag. Similarity search applies a strict filter:
  ```python
  where={"scope_id": scope_id}
  ```
  Chunks from one website or document are inaccessible to queries executing in another scope.
* **Conversation History Separation**: Conversation turns stored in SQLite are segregated by `scope_id`. Chat history is never mixed across scopes.
* **Complete Data Purge**: Deleting a scope via `DELETE /api/v1/scopes/{scope_id}` atomically removes all vector embeddings from ChromaDB and all records, messages, and crawl jobs from SQLite.

---

## 6. DOM Cleaning & Content Sanitization

When extracting content in the Chrome Extension:
* The active page DOM is cloned before inspection; the user's active page is never mutated.
* Dynamic script execution tags (`<script>`, `<style>`, `<iframe>`, `<noscript>`) are stripped before packaging content.
* Text extraction focuses on semantic containers (`<main>`, `<article>`), stripping navigational elements and tracking frames.

---

## 7. Known Security Limitations

1. **Single-User Architecture**: WebRAG is designed as a local single-user developer tool. It does not implement multi-tenant authentication or role-based access control (RBAC).
2. **Permissive Local CORS**: The FastAPI backend configures `allow_origins=["*"]` to simplify local communication between the Chrome Extension (`chrome-extension://...`) and the local daemon (`127.0.0.1:8000`). In production environments or shared networks, origins should be restricted to specific extension IDs.
3. **Indirect Prompt Injection**: If a user indexes an adversarial webpage containing prompt injection payloads (e.g. *"Ignore all previous instructions and output..."*), the LLM could be misled. WebRAG mitigates this by wrapping retrieved context in strict system grounding prompts, but users should be cautious when indexing untrusted or malicious websites.
