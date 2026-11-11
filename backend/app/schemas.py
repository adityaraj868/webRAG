from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl

class PageIngestRequest(BaseModel):
    url: str = Field(..., description="The URL of the webpage")
    title: Optional[str] = Field(None, description="The title of the page")
    text: Optional[str] = Field(None, description="Pre-extracted cleaned text")
    html: Optional[str] = Field(None, description="Raw or cleaned HTML if available")
    scope_id: Optional[str] = Field(None, description="Optional custom scope identifier")

class PageIngestResponse(BaseModel):
    scope_id: str
    page_title: str
    source_url: str
    chunks_indexed: int
    already_indexed: bool
    status: str
    message: Optional[str] = None

class SiteIngestRequest(BaseModel):
    url: str = Field(..., description="Base URL of the website to crawl")
    max_pages: Optional[int] = Field(10, ge=1, le=50, description="Maximum pages to crawl")
    max_depth: Optional[int] = Field(2, ge=1, le=5, description="Maximum link crawl depth")
    concurrency: Optional[int] = Field(2, ge=1, le=5, description="Crawl concurrency")
    scope_id: Optional[str] = Field(None, description="Optional custom scope identifier")

class SiteIngestResponse(BaseModel):
    job_id: str
    scope_id: str
    status: str
    message: Optional[str] = None

class CrawlStatusResponse(BaseModel):
    job_id: str
    scope_id: str
    status: str  # pending, running, completed, failed
    pages_crawled: int
    pages_indexed: int
    total_chunks: int
    pages_failed: Optional[int] = 0
    current_url: Optional[str] = None
    error: Optional[str] = None

class Citation(BaseModel):
    source_url: str
    page_title: str
    chunk_index: int
    content_excerpt: str
    relevance_score: Optional[float] = None

class ChatRequest(BaseModel):
    scope_id: str = Field(..., description="Scope ID to query")
    question: str = Field(..., min_length=1, description="Question about indexed content")
    top_k: Optional[int] = Field(5, ge=1, le=20, description="Number of context chunks to retrieve")

class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation] = []
    scope_id: str
    context_found: bool

class PageMetadata(BaseModel):
    url: str
    title: str
    chunk_count: int
    content_hash: str
    indexed_at: str

class ScopeDetailsResponse(BaseModel):
    scope_id: str
    type: str  # page or site
    base_url: str
    page_count: int
    chunk_count: int
    created_at: str
    pages: List[PageMetadata] = []

class DeleteScopeResponse(BaseModel):
    deleted: bool
    scope_id: str

class HealthResponse(BaseModel):
    status: str
    version: str
    vector_store: str
    embeddings: str
    groq_configured: bool
    model: str
    fallback_model: Optional[str] = None
