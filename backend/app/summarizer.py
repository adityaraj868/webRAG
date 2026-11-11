import re
import time
import logging
from typing import List, Dict, Any, Tuple, Set
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.documents import Document

from app.llm import invoke_llm_with_resilience, sanitize_error
from app.config import (
    get_groq_api_key,
    SUMMARIZATION_BATCH_TOKEN_LIMIT,
    SUMMARIZATION_REDUCE_FAN_IN,
    SUMMARIZATION_RATE_DELAY,
)
from app.token_budget import count_tokens
from app.schemas import Citation

logger = logging.getLogger(__name__)

SUMMARIZATION_SYSTEM_PROMPT = """You are WebRAG, an expert analytical AI assistant.
Your task is to produce a high-quality, comprehensive, and well-structured summary of the provided text.

CRITICAL RULES:
1. Grounding: Include ONLY facts, figures, and developments mentioned in the provided text.
2. Structure: Format clearly with markdown sections (e.g. ## Executive Overview, ## Key Themes & Major Highlights, ## Key Takeaways & Significance).
3. Objective: Maintain neutral, factual, and informative prose.
4. Comprehensive: Cover the breadth of the document from beginning to end."""

def is_summarization_query(query: str) -> bool:
    """Detect if user query is asking for a whole-document or website summary."""
    q = query.strip().lower()
    q = re.sub(r'[\?!.,;:]', '', q).strip()

    direct_phrases = {
        'summarize',
        'summarize this',
        'summarize this page',
        'summarize page',
        'summarize website',
        'summarize the website',
        'summarize this website',
        'summarize the page',
        'give me a summary',
        'give me an overview',
        'overview',
        'summary',
        'tldr',
        'tl/dr',
        'tl;dr',
        'what is this page about',
        'what is this about',
        'what is this website about',
        'what is this document about',
        'give an overview of this page',
        'provide a summary',
        'brief overview',
    }
    if q in direct_phrases:
        return True

    patterns = [
        r'^(please\s+)?(can\s+you\s+)?(briefly\s+)?summarize(\s+(this|the)\s+(page|website|article|document|content))?$',
        r'^(give|provide)\s+(me\s+)?(a\s+)?(brief\s+)?(summary|overview)(\s+of\s+(this|the)\s+(page|website|article|document|content))?$',
        r'^what(\s+is|\'s)\s+(this|the)(\s+(page|website|article|document|content))?\s+about(\s+overall)?$',
    ]
    return any(re.match(p, q) for p in patterns)

def create_dynamic_token_batches(
    docs: List[Document],
    max_batch_tokens: int = SUMMARIZATION_BATCH_TOKEN_LIMIT
) -> List[List[Document]]:
    """
    Partitions documents into dynamically sized batches based on token counts.
    Ensures that every chunk is assigned to exactly one batch with no arbitrary ceiling on batch count.
    """
    if not docs:
        return []

    batches: List[List[Document]] = []
    current_batch: List[Document] = []
    current_tokens = 0

    for doc in docs:
        # Include framing overhead
        doc_tokens = count_tokens(doc.page_content) + 25

        if current_batch and (current_tokens + doc_tokens > max_batch_tokens):
            batches.append(current_batch)
            current_batch = [doc]
            current_tokens = doc_tokens
        else:
            current_batch.append(doc)
            current_tokens += doc_tokens

    if current_batch:
        batches.append(current_batch)

    return batches

def generate_direct_summary(docs: List[Document], document_title: str) -> str:
    """Single-pass direct summary for documents that fit completely within one token batch."""
    combined_text = "\n\n".join([
        f"--- Section {idx+1} (Chunk {d.metadata.get('chunk_index', idx)}) ---\n{d.page_content}"
        for idx, d in enumerate(docs)
    ])
    prompt = f"""DOCUMENT TITLE: {document_title}

SOURCE TEXT:
{combined_text}

Provide a comprehensive, well-structured summary covering the entire document:"""
    return invoke_llm_with_resilience([
        SystemMessage(content=SUMMARIZATION_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ])

def recursive_reduce(
    summaries: List[str],
    document_title: str,
    fan_in: int = SUMMARIZATION_REDUCE_FAN_IN
) -> str:
    """
    Recursively reduces a collection of intermediate section summaries.
    If the number of summaries exceeds fan_in, bundles them in groups of fan_in
    and synthesizes each group before final consolidation.
    """
    if not summaries:
        return "No summary content could be synthesized."

    # Base case: fits within fan-in, perform final master reduction
    if len(summaries) <= fan_in:
        combined_sections = "\n\n".join(summaries)
        reduce_prompt = f"""DOCUMENT TITLE: {document_title}

SECTION SUMMARIES:
{combined_sections}

TASK:
Combine these section summaries into a single, cohesive, comprehensive, and well-organized final summary of "{document_title}".
Structure your response as follows:
- **Executive Overview**: A clear summary of what this document or website covers.
- **Key Themes & Major Highlights**: Detailed, thematic breakdown covering the full chronological or logical progression.
- **Key Takeaways & Significance**: Concluding assessment.

Ensure all facts are strictly grounded in the section summaries above:"""

        return invoke_llm_with_resilience([
            SystemMessage(content=SUMMARIZATION_SYSTEM_PROMPT),
            HumanMessage(content=reduce_prompt)
        ])

    # Recursive reduction step: bundle in groups of `fan_in`
    logger.info(
        f"Hierarchical Reduction: {len(summaries)} intermediate summaries exceed fan-in ({fan_in}). "
        f"Running recursive consolidation step."
    )
    consolidated_groups: List[str] = []
    for i in range(0, len(summaries), fan_in):
        group = summaries[i:i + fan_in]
        group_text = "\n\n".join(group)
        group_prompt = f"""DOCUMENT: {document_title} (Intermediate Digest Part {len(consolidated_groups)+1})

SECTION SUMMARIES:
{group_text}

TASK:
Synthesize these section summaries into a comprehensive intermediate digest, preserving all key facts, dates, names, events, and thematic developments:"""

        group_res = invoke_llm_with_resilience([
            SystemMessage(content="You synthesize section digests into a consolidated intermediate digest."),
            HumanMessage(content=group_prompt)
        ])
        consolidated_groups.append(f"### Intermediate Digest Part {len(consolidated_groups)+1}\n{group_res}")

        if SUMMARIZATION_RATE_DELAY > 0:
            time.sleep(SUMMARIZATION_RATE_DELAY)

    # Recurse on the consolidated digests
    return recursive_reduce(consolidated_groups, document_title, fan_in=fan_in)

def extract_representative_citations(docs: List[Document], max_citations: int = 10) -> List[Citation]:
    """Select representative source chunks spanning beginning, middle, and end, plus every unique page."""
    if not docs:
        return []

    indices = set()
    total = len(docs)
    indices.add(0)
    if total > 1:
        indices.add(total - 1)
    if total > 4:
        indices.add(total // 4)
        indices.add(total // 2)
        indices.add((3 * total) // 4)

    # Include first chunk of each unique URL (critical for multi-page sites)
    seen_urls = set()
    for idx, d in enumerate(docs):
        url = d.metadata.get("source_url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            indices.add(idx)

    sorted_indices = sorted(list(indices))
    if len(sorted_indices) > max_citations:
        # Sample proportionally ensuring start and end are always preserved
        step = (len(sorted_indices) - 1) / (max_citations - 1)
        sampled = [sorted_indices[round(i * step)] for i in range(max_citations)]
        sorted_indices = sorted(list(set(sampled)))

    citations: List[Citation] = []
    for idx in sorted_indices:
        d = docs[idx]
        excerpt = d.page_content.strip()
        if len(excerpt) > 400:
            excerpt = excerpt[:400] + "..."
        citations.append(
            Citation(
                source_url=d.metadata.get("source_url", ""),
                page_title=d.metadata.get("page_title", "Indexed Document"),
                chunk_index=d.metadata.get("chunk_index", idx),
                content_excerpt=excerpt,
                relevance_score=1.0,
            )
        )
    return citations

def summarize_scope_content(scope_id: str, docs: List[Document]) -> Tuple[str, List[Citation]]:
    """
    Summarizes all content in a scope using dynamic token-based batching and recursive reduction.
    Tracks all processed and failed chunk IDs. Guarantees no silent truncation.
    """
    if not docs:
        return (
            "I cannot answer this question based on the indexed content, as no content was found in the active scope.",
            []
        )

    key = get_groq_api_key()
    citations = extract_representative_citations(docs)

    if not key:
        return (
            "⚠️ Groq API key is not configured. Please set `GROQ_API_KEY` in your environment or `backend/.env` file.\n\n"
            f"Indexed document contains {len(docs)} chunks. Representative citations are shown below.",
            citations
        )

    # Determine document or site title
    doc_title = docs[0].metadata.get("page_title") or docs[0].metadata.get("source_url") or "Indexed Content"
    unique_urls = set(d.metadata.get("source_url") for d in docs if d.metadata.get("source_url"))
    if len(unique_urls) > 1:
        doc_title = f"Website ({len(unique_urls)} pages, {len(docs)} chunks)"

    # 1. Create dynamic token-based batches (no fixed batch ceiling)
    batches = create_dynamic_token_batches(docs, max_batch_tokens=SUMMARIZATION_BATCH_TOKEN_LIMIT)
    logger.info(
        f"Dynamic Summarization for '{doc_title}': {len(docs)} chunks partitioned into {len(batches)} "
        f"token batches (limit: {SUMMARIZATION_BATCH_TOKEN_LIMIT} tokens/batch)."
    )

    # Fast path: single batch
    if len(batches) == 1:
        try:
            summary = generate_direct_summary(batches[0], doc_title)
            return summary, citations
        except Exception as e:
            safe_msg = sanitize_error(str(e))
            logger.error(f"Error in direct summarization: {safe_msg}")
            return f"Error generating document summary: {safe_msg}", citations

    # 2. Map step: process each batch without silent truncation
    processed_chunk_ids: List[str] = []
    failed_chunk_ids: List[str] = []
    section_summaries: List[str] = []

    for b_idx, batch in enumerate(batches, 1):
        batch_ids = [
            f"{d.metadata.get('source_url', '')}#chunk-{d.metadata.get('chunk_index', i)}"
            for i, d in enumerate(batch)
        ]

        # Assemble complete text of all chunks in batch (never silently truncate)
        batch_text = "\n\n".join([
            f"--- [Chunk {d.metadata.get('chunk_index', i)} of {d.metadata.get('source_url', '')}] ---\n{d.page_content}"
            for i, d in enumerate(batch)
        ])

        b_prompt = f"""DOCUMENT: {doc_title} (Part {b_idx} of {len(batches)})

TEXT:
{batch_text}

Summarize the key facts, events, concepts, and arguments from this section in 3-5 concise, information-dense paragraphs or bullet points:"""

        try:
            b_resp = invoke_llm_with_resilience([
                SystemMessage(content="You extract key factual points from document sections for hierarchical summarization."),
                HumanMessage(content=b_prompt)
            ])
            section_summaries.append(f"### Part {b_idx} Highlights\n{b_resp.strip()}")
            processed_chunk_ids.extend(batch_ids)

            # Controlled concurrency delay to respect Groq TPM rate limits
            if SUMMARIZATION_RATE_DELAY > 0 and b_idx < len(batches):
                time.sleep(SUMMARIZATION_RATE_DELAY)

        except Exception as e:
            safe_err = sanitize_error(str(e))
            logger.error(f"Error in summarizer map step for batch {b_idx}: {safe_err}")
            failed_chunk_ids.extend(batch_ids)
            section_summaries.append(
                f"### Part {b_idx} Notice\n(Section highlights for {len(batch_ids)} chunks omitted due to API failure)"
            )

    logger.info(
        f"Map step completed: {len(processed_chunk_ids)} chunks processed successfully, "
        f"{len(failed_chunk_ids)} chunks failed out of {len(docs)} total chunks."
    )

    # 3. Recursive reduction step
    try:
        final_summary = recursive_reduce(section_summaries, doc_title, fan_in=SUMMARIZATION_REDUCE_FAN_IN)
        return final_summary, citations
    except Exception as e:
        safe_msg = sanitize_error(str(e))
        logger.error(f"Error during recursive reduction for scope {scope_id}: {safe_msg}")
        return f"Error synthesizing document summary: {safe_msg}", citations
