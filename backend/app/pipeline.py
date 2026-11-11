import hashlib
import logging
from typing import Optional, List, Tuple, Dict, Any
from urllib.parse import urlparse

from app.database import (
    upsert_scope,
    get_document_hash,
    record_document,
    save_chat_message,
    get_chat_history,
)
from app.extractor import process_page_to_document
from app.chunker import split_document
from app.vectorstore import (
    add_documents_to_store,
    delete_documents_by_url,
    similarity_search_scope,
    get_all_chunks_by_scope,
)
from app.llm import generate_grounded_answer, rewrite_query_with_context
from app.summarizer import is_summarization_query, summarize_scope_content
from app.schemas import Citation

logger = logging.getLogger(__name__)

def generate_default_scope_id(url: str, scope_type: str) -> str:
    parsed = urlparse(url)
    if scope_type == "site":
        origin = f"{parsed.scheme}://{parsed.netloc}"
        hash_part = hashlib.md5(origin.encode()).hexdigest()[:8]
        return f"site_{parsed.netloc}_{hash_part}"
    else:
        hash_part = hashlib.md5(url.encode()).hexdigest()[:8]
        clean_path = parsed.path.strip("/").replace("/", "_")[:20] or "home"
        return f"page_{parsed.netloc}_{clean_path}_{hash_part}"

def ingest_document(
    url: str,
    title: Optional[str] = None,
    text: Optional[str] = None,
    html: Optional[str] = None,
    scope_id: Optional[str] = None,
    scope_type: str = "page",
) -> Tuple[str, str, int, bool]:
    # Determine scope
    final_scope_id = scope_id or generate_default_scope_id(url, scope_type)

    # Register scope in database
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    upsert_scope(final_scope_id, scope_type, base_url)

    # 1. Normalize content & compute hash
    document = process_page_to_document(
        url=url,
        title=title,
        text=text,
        html=html,
        scope_id=final_scope_id
    )

    content_hash = document.metadata["content_hash"]
    page_title = document.metadata["page_title"]

    # 2. Check if document has already been indexed with unchanged content
    existing_hash = get_document_hash(final_scope_id, url)
    if existing_hash and existing_hash == content_hash:
        logger.info(f"Skipping re-embedding for unchanged document: {url} (scope {final_scope_id})")
        return final_scope_id, page_title, 0, True

    # 3. If modified, remove outdated chunks from vector store first
    if existing_hash:
        delete_documents_by_url(final_scope_id, url)

    # 4. Handle empty document
    if document.metadata.get("raw_text_len", 0) == 0:
        logger.warning(f"No readable text extracted from document: {url}")
        record_document(final_scope_id, url, page_title, content_hash, 0)
        return final_scope_id, page_title, 0, False

    # 5. Split document into chunks
    chunks = split_document(document, final_scope_id)
    if not chunks:
        logger.warning(f"No chunks extracted from document: {url}")
        record_document(final_scope_id, url, page_title, content_hash, 0)
        return final_scope_id, page_title, 0, False

    # 5. Embed and store in ChromaDB
    add_documents_to_store(chunks)

    # 6. Record metadata in SQLite
    record_document(final_scope_id, url, page_title, content_hash, len(chunks))
    logger.info(f"Successfully indexed {url} with {len(chunks)} chunks in scope {final_scope_id}")

    return final_scope_id, page_title, len(chunks), False

def query_rag(
    scope_id: str,
    question: str,
    top_k: int = 5
) -> Tuple[str, List[Citation], bool]:
    # 1. Whole-Document / Website Summarization Intent Handling
    if is_summarization_query(question):
        logger.info(f"Summarization intent detected for scope {scope_id}: '{question}'")
        all_docs = get_all_chunks_by_scope(scope_id)
        if not all_docs:
            return "I cannot answer this question based on the indexed content, as no content was found in the active scope.", [], False

        summary_answer, citations = summarize_scope_content(scope_id, all_docs)
        save_chat_message(scope_id, "user", question, None)
        save_chat_message(scope_id, "assistant", summary_answer, [c.model_dump() for c in citations])
        return summary_answer, citations, True

    # 2. Conversational Context & Query Rewriting for Follow-Up Questions
    chat_history = get_chat_history(scope_id, limit=6)
    search_query = rewrite_query_with_context(question, chat_history)

    # 3. Retrieve top_k relevant chunks filtered strictly by scope_id
    retrieved_items = similarity_search_scope(
        query=search_query,
        scope_id=scope_id,
        k=top_k
    )

    citations: List[Citation] = []
    chunk_dicts_for_llm = []

    for doc, score in retrieved_items:
        excerpt = doc.page_content.strip()
        if len(excerpt) > 400:
            excerpt = excerpt[:400] + "..."

        citation = Citation(
            source_url=doc.metadata.get("source_url", ""),
            page_title=doc.metadata.get("page_title", "Untitled Document"),
            chunk_index=doc.metadata.get("chunk_index", 0),
            content_excerpt=excerpt,
            relevance_score=round(score, 3) if score is not None else None,
        )
        citations.append(citation)

        chunk_dicts_for_llm.append({
            "source_url": citation.source_url,
            "page_title": citation.page_title,
            "content_excerpt": doc.page_content,
        })

    context_found = len(citations) > 0

    # 4. Generate grounded answer with conversation history passed to LLM
    answer = generate_grounded_answer(question, chunk_dicts_for_llm, chat_history=chat_history)

    # 5. Save to active conversation history in SQLite
    save_chat_message(scope_id, "user", question, None)
    save_chat_message(scope_id, "assistant", answer, [c.model_dump() for c in citations])

    return answer, citations, context_found
