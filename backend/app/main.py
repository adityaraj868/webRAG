import uuid
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import httpx

from app.config import (
    get_groq_api_key,
    get_groq_model,
    get_groq_fallback_model,
    GROQ_MODEL,
    GROQ_FALLBACK_MODEL,
    EMBEDDING_MODEL,
)
from app.database import (
    init_db,
    get_scope,
    get_scope_documents,
    delete_scope_metadata,
    create_crawl_job,
    get_crawl_job,
)
from app.schemas import (
    PageIngestRequest,
    PageIngestResponse,
    SiteIngestRequest,
    SiteIngestResponse,
    CrawlStatusResponse,
    ChatRequest,
    ChatResponse,
    ScopeDetailsResponse,
    DeleteScopeResponse,
    HealthResponse,
    PageMetadata,
)
from app.pipeline import ingest_document, query_rag, generate_default_scope_id
from app.vectorstore import delete_documents_by_scope, get_vectorstore
from app.crawler import run_website_crawl, validate_url_safety, USER_AGENT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("webrag")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing WebRAG backend...")
    init_db()
    try:
        # Pre-initialize vector store and embeddings
        get_vectorstore()
        logger.info("ChromaDB vector store initialized.")
    except Exception as e:
        logger.warning(f"Could not warm up vectorstore on startup: {e}")
    yield
    logger.info("WebRAG backend shutting down.")

app = FastAPI(
    title="WebRAG Backend",
    version="1.0.0",
    description="Backend API for WebRAG Chrome Extension",
    lifespan=lifespan,
)

# Enable CORS for Chrome Extension requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/v1/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        vector_store="ready",
        embeddings=EMBEDDING_MODEL,
        groq_configured=bool(get_groq_api_key()),
        model=get_groq_model(),
        fallback_model=get_groq_fallback_model(),
    )

@app.post("/api/v1/ingest/page", response_model=PageIngestResponse)
async def ingest_page_endpoint(req: PageIngestRequest):
    logger.info(f"Received page ingest request for: {req.url}")

    html_content = req.html
    text_content = req.text

    # If neither text nor html was provided, fetch the URL directly
    if not html_content and not text_content:
        is_safe, reason = validate_url_safety(req.url)
        if not is_safe:
            raise HTTPException(status_code=400, detail=f"Unsafe URL rejected: {reason}")
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                resp = await client.get(req.url, headers={"User-Agent": USER_AGENT})
                if resp.status_code != 200:
                    raise HTTPException(status_code=400, detail=f"Failed to fetch {req.url}: HTTP {resp.status_code}")
                html_content = resp.text
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch {req.url}: {str(e)}")

    try:
        scope_id, title, chunks_count, already_indexed = ingest_document(
            url=req.url,
            title=req.title,
            text=text_content,
            html=html_content,
            scope_id=req.scope_id,
            scope_type="page",
        )

        msg = "Content was already indexed and unchanged." if already_indexed else f"Successfully indexed {chunks_count} chunks."
        return PageIngestResponse(
            scope_id=scope_id,
            page_title=title,
            source_url=req.url,
            chunks_indexed=chunks_count,
            already_indexed=already_indexed,
            status="completed",
            message=msg,
        )
    except Exception as e:
        logger.error(f"Error ingesting page {req.url}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to ingest page: {str(e)}")

@app.post("/api/v1/ingest/site", response_model=SiteIngestResponse)
async def ingest_site_endpoint(req: SiteIngestRequest, background_tasks: BackgroundTasks):
    is_safe, reason = validate_url_safety(req.url)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"Unsafe URL rejected: {reason}")

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    scope_id = req.scope_id or generate_default_scope_id(req.url, "site")

    create_crawl_job(job_id=job_id, scope_id=scope_id)

    async def on_page_extracted_callback(page_url: str, page_html: str, target_scope_id: str) -> int:
        _, _, chunks_count, _ = ingest_document(
            url=page_url,
            html=page_html,
            scope_id=target_scope_id,
            scope_type="site",
        )
        return chunks_count

    # Run crawl in background task
    background_tasks.add_task(
        run_website_crawl,
        job_id=job_id,
        scope_id=scope_id,
        base_url=req.url,
        max_pages=req.max_pages or 10,
        max_depth=req.max_depth or 2,
        concurrency=req.concurrency or 2,
        on_page_extracted=on_page_extracted_callback,
    )

    return SiteIngestResponse(
        job_id=job_id,
        scope_id=scope_id,
        status="pending",
        message=f"Website crawl job initiated for {req.url}",
    )

@app.get("/api/v1/ingest/status/{job_id}", response_model=CrawlStatusResponse)
def get_ingest_status_endpoint(job_id: str):
    job = get_crawl_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Crawl job {job_id} not found")

    return CrawlStatusResponse(
        job_id=job["job_id"],
        scope_id=job["scope_id"],
        status=job["status"],
        pages_crawled=job["pages_crawled"],
        pages_indexed=job["pages_indexed"],
        total_chunks=job["total_chunks"],
        pages_failed=job.get("pages_failed", 0),
        current_url=job["current_url"],
        error=job["error"],
    )

@app.post("/api/v1/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    scope = get_scope(req.scope_id)
    if not scope:
        return ChatResponse(
            answer=f"Scope '{req.scope_id}' does not exist or has not indexed any content yet. Please index a page or website first.",
            citations=[],
            scope_id=req.scope_id,
            context_found=False,
        )

    try:
        answer, citations, context_found = query_rag(
            scope_id=req.scope_id,
            question=req.question,
            top_k=req.top_k or 5,
        )
        return ChatResponse(
            answer=answer,
            citations=citations,
            scope_id=req.scope_id,
            context_found=context_found,
        )
    except Exception as e:
        logger.error(f"Error in chat endpoint for scope {req.scope_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat query failed: {str(e)}")

@app.get("/api/v1/scopes/{scope_id}", response_model=ScopeDetailsResponse)
def get_scope_endpoint(scope_id: str):
    scope = get_scope(scope_id)
    if not scope:
        raise HTTPException(status_code=404, detail=f"Scope '{scope_id}' not found")

    docs = get_scope_documents(scope_id)
    total_chunks = sum(d["chunk_count"] for d in docs)

    page_metadata_list = [
        PageMetadata(
            url=d["url"],
            title=d["title"],
            chunk_count=d["chunk_count"],
            content_hash=d["content_hash"],
            indexed_at=d["indexed_at"]
        ) for d in docs
    ]

    return ScopeDetailsResponse(
        scope_id=scope["scope_id"],
        type=scope["type"],
        base_url=scope["base_url"],
        page_count=len(docs),
        chunk_count=total_chunks,
        created_at=scope["created_at"],
        pages=page_metadata_list,
    )

@app.delete("/api/v1/scopes/{scope_id}", response_model=DeleteScopeResponse)
def delete_scope_endpoint(scope_id: str):
    scope = get_scope(scope_id)
    if not scope:
        raise HTTPException(status_code=404, detail=f"Scope '{scope_id}' not found")

    # 1. Delete all vectors from ChromaDB
    delete_documents_by_scope(scope_id)

    # 2. Delete metadata and messages from SQLite
    delete_scope_metadata(scope_id)

    return DeleteScopeResponse(
        deleted=True,
        scope_id=scope_id,
    )
