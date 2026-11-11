import re
import time
import random
import logging
from typing import List, Dict, Any, Tuple, Optional
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_groq import ChatGroq

from app.config import (
    get_groq_api_key,
    get_groq_model,
    get_groq_fallback_model,
    GROQ_MODEL,
    GROQ_FALLBACK_MODEL,
    GROQ_MAX_RETRIES,
    GROQ_RETRY_BASE_DELAY,
    GROQ_MAX_RETRY_DELAY,
    MODEL_CONTEXT_WINDOW,
)
from app.token_budget import (
    count_tokens,
    count_message_tokens,
    get_max_input_budget,
    fit_context_within_budget,
    validate_prompt_tokens,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are WebRAG, a precise and factual AI assistant. Your job is to answer questions strictly and exclusively based on the provided website excerpts below.

CRITICAL INSTRUCTIONS:
1. Grounding: Answer ONLY using facts directly mentioned in the CONTEXT. Do not use outside knowledge or extrapolate beyond the text.
2. Insufficient Information: If the provided context does not contain enough facts to answer the question, state clearly and concisely: "I cannot answer this question based on the indexed content, as the context does not provide sufficient information on this topic."
3. Accuracy: Never fabricate facts, statistics, or source references.
4. Neutral tone: Be direct, clear, and informative. Use markdown formatting where appropriate (bullet points, bold text)."""

def sanitize_error(error_msg: str) -> str:
    """Redact any Groq API key patterns to prevent credential leakage in logs or responses."""
    return re.sub(r'gsk_[a-zA-Z0-9_\-]+', 'gsk_***', str(error_msg))

def get_groq_llm(model: Optional[str] = None) -> ChatGroq:
    """
    Instantiate ChatGroq with selected or configured model.
    max_retries is set to 0 so invoke_llm_with_resilience handles retry-after,
    exponential backoff, and model fallback deterministically.
    """
    key = get_groq_api_key()
    if not key:
        raise ValueError("GROQ_API_KEY is not set in environment or .env file.")
    selected_model = model or get_groq_model()
    return ChatGroq(
        model=selected_model,
        api_key=key,
        temperature=0.1,
        max_retries=0,
        request_timeout=30.0,
    )

def is_rate_limit_error(exc: Exception) -> bool:
    """Detect HTTP 429 rate limit or TPM/RPM errors."""
    if not exc:
        return False
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    resp = getattr(exc, "response", None)
    if resp and getattr(resp, "status_code", None) == 429:
        return True
    exc_type = type(exc).__name__
    if "RateLimit" in exc_type:
        return True
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "tokens per minute" in msg or "tpm" in msg

def is_auth_error(exc: Exception) -> bool:
    """Detect HTTP 401 unauthorized or invalid credentials."""
    if not exc:
        return False
    status = getattr(exc, "status_code", None)
    if status == 401:
        return True
    resp = getattr(exc, "response", None)
    if resp and getattr(resp, "status_code", None) == 401:
        return True
    exc_type = type(exc).__name__
    if "Authentication" in exc_type:
        return True
    msg = str(exc).lower()
    return "401" in msg or "invalid api key" in msg or "unauthorized" in msg

def get_retry_after(exc: Exception) -> Optional[float]:
    """Extract retry-after delay from response headers or error message."""
    resp = getattr(exc, "response", None)
    if resp and hasattr(resp, "headers"):
        retry_hdr = resp.headers.get("retry-after")
        if retry_hdr:
            try:
                return float(retry_hdr)
            except (ValueError, TypeError):
                pass
    m = re.search(r'try again in ([0-9.]+)\s*s', str(exc), re.I)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None

def invoke_llm_with_resilience(
    messages: List[BaseMessage],
    primary_model: Optional[str] = None,
    fallback_model: Optional[str] = None,
    max_429_retries: int = GROQ_MAX_RETRIES,
    base_delay: float = GROQ_RETRY_BASE_DELAY,
    max_delay: float = GROQ_MAX_RETRY_DELAY,
) -> str:
    """
    Executes an LLM call with tokenizer-budget validation, HTTP 429 exponential backoff,
    and automatic fallback to secondary model on model/API failures.
    
    Rules:
    1. HTTP 429 is retried with backoff on the SAME model (never switches to fallback for 429).
    2. Fallback model is activated ONLY for appropriate model/API failures (500s, 404, model not found, etc.).
    3. Never exposes credentials in logs.
    """
    key = get_groq_api_key()
    if not key:
        raise ValueError("GROQ_API_KEY is not set in environment or .env file.")

    primary = primary_model or get_groq_model()
    fallback = fallback_model or get_groq_fallback_model()

    # Validate token budget before dispatching
    validate_prompt_tokens(messages)

    def _call_model(model_name: str) -> Tuple[Optional[str], Optional[Exception]]:
        llm = get_groq_llm(model=model_name)
        for attempt in range(max_429_retries + 1):
            try:
                res = llm.invoke(messages)
                return res.content.strip(), None
            except Exception as e:
                if is_rate_limit_error(e) and attempt < max_429_retries:
                    retry_after = get_retry_after(e)
                    backoff = min(max_delay, base_delay * (2 ** attempt) + random.uniform(0.1, 0.4))
                    sleep_time = retry_after if retry_after is not None else backoff
                    logger.warning(
                        f"Groq HTTP 429 Rate Limit for model '{model_name}'. Backing off {sleep_time:.2f}s "
                        f"(attempt {attempt+1}/{max_429_retries})."
                    )
                    time.sleep(sleep_time)
                    continue
                return None, e
        return None, RuntimeError(f"Max retries exceeded for model {model_name}")

    # 1. Attempt with primary model
    content, primary_err = _call_model(primary)
    if content is not None:
        return content

    # If failure was a 429 Rate Limit, DO NOT switch to fallback model
    if is_rate_limit_error(primary_err):
        safe_msg = sanitize_error(str(primary_err))
        logger.error(f"Rate limit exceeded on primary model '{primary}' after {max_429_retries} retries: {safe_msg}")
        raise primary_err

    # If failure was an Authentication Error, DO NOT switch to fallback model
    if is_auth_error(primary_err):
        safe_msg = sanitize_error(str(primary_err))
        logger.error(f"Authentication error on primary model '{primary}': {safe_msg}")
        raise primary_err

    # 2. For genuine model / API failures (404, 500, 502, 503, model decommissioned/unavailable), activate fallback model
    safe_primary_err = sanitize_error(str(primary_err))
    logger.warning(
        f"Primary model '{primary}' encountered API failure: {safe_primary_err}. "
        f"Activating fallback model '{fallback}'."
    )

    fallback_content, fallback_err = _call_model(fallback)
    if fallback_content is not None:
        return fallback_content

    # Both models failed
    safe_fallback_err = sanitize_error(str(fallback_err))
    logger.error(f"Fallback model '{fallback}' also failed: {safe_fallback_err}")
    raise fallback_err

def rewrite_query_with_context(
    question: str,
    chat_history: List[Dict[str, Any]]
) -> str:
    """Rewrite ambiguous follow-up questions using recent chat context."""
    if not chat_history:
        return question

    pronoun_or_vague = re.search(
        r'\b(he|she|it|its|they|them|his|her|this|that|these|those|second|first|third|more|next|why|who|what happened|tell me more|elaborate)\b',
        question,
        re.I
    )
    is_short_followup = len(question.strip().split()) <= 6

    if not pronoun_or_vague and not is_short_followup:
        return question

    prompt = f"""Given the following conversation history between User and Assistant, rewrite the User's latest question into a clear, standalone search query that contains all necessary names, subjects, and context.
DO NOT answer the question. Only return the standalone rewritten search query. If the question is already clear and standalone, return it unchanged.

Conversation History:
"""
    for msg in chat_history[-4:]:
        role = "User" if msg.get("role") == "user" else "Assistant"
        content = msg.get("content", "")
        if len(content) > 300:
            content = content[:300] + "..."
        prompt += f"{role}: {content}\n"

    prompt += f"\nLatest User Question: {question}\n\nStandalone Search Query:"

    try:
        messages = [
            SystemMessage(content="You rewrite follow-up questions into standalone search queries based on chat context."),
            HumanMessage(content=prompt)
        ]
        rewritten = invoke_llm_with_resilience(messages)
        rewritten = rewritten.strip().strip('"').strip("'")
        if rewritten and len(rewritten) > 2 and len(rewritten) < 200:
            logger.info(f"Contextual Query Rewriting: '{question}' -> '{rewritten}'")
            return rewritten
    except Exception as e:
        safe_err = sanitize_error(str(e))
        logger.warning(f"Query rewrite skipped due to error: {safe_err}")

    return question

def generate_grounded_answer(
    question: str,
    context_chunks: List[Dict[str, Any]],
    chat_history: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Generates an answer strictly grounded in retrieved context chunks,
    enforcing tokenizer-aware budget across context, history, and questions.
    """
    if not context_chunks:
        return "I cannot answer this question based on the indexed content, as no relevant context was found in the active scope."

    key = get_groq_api_key()
    if not key:
        return (
            "⚠️ Groq API key is not configured. Please set `GROQ_API_KEY` in your environment or `backend/.env` file.\n\n"
            "Retrieved relevant chunks from indexed content are shown below."
        )

    # 1. Enforce tokenizer-aware prompt budgeting
    budgeted_chunks, budgeted_history = fit_context_within_budget(
        system_prompt=SYSTEM_PROMPT,
        question=question,
        context_chunks=context_chunks,
        chat_history=chat_history,
    )

    # Assemble formatted context with source attribution
    context_sections = []
    for idx, c in enumerate(budgeted_chunks, 1):
        title = c.get("page_title", "Source")
        url = c.get("source_url", "")
        text = c.get("content_excerpt", "").strip()
        context_sections.append(f"--- [Source {idx}: {title} ({url})] ---\n{text}")

    full_context_str = "\n\n".join(context_sections)

    human_content = f"""CONTEXT:
{full_context_str}

QUESTION:
{question}

Provide an answer grounded strictly in the context above:"""

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    # Inject conversation context within budget
    if budgeted_history:
        for msg in budgeted_history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                if len(content) > 500:
                    content = content[:500] + "..."
                messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=human_content))

    try:
        return invoke_llm_with_resilience(messages)
    except Exception as e:
        safe_msg = sanitize_error(str(e))
        logger.error(f"Error calling Groq API: {safe_msg}")
        return f"Error generating answer from Groq API: {safe_msg}"
