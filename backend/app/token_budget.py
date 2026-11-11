import logging
from typing import List, Dict, Any, Optional, Tuple
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
import tiktoken

from app.config import (
    MODEL_CONTEXT_WINDOW,
    SAFETY_MARGIN_TOKENS,
    EXPECTED_COMPLETION_TOKENS,
)

logger = logging.getLogger(__name__)

# Use cl100k_base (OpenAI / GPT BPE tokenizer)
try:
    _encoding = tiktoken.get_encoding("cl100k_base")
except Exception as e:
    logger.warning(f"Failed to load tiktoken cl100k_base encoding: {e}. Falling back to character heuristic.")
    _encoding = None

def count_tokens(text: str) -> int:
    """Accurately count tokens using BPE tokenizer with graceful fallback."""
    if not text:
        return 0
    if _encoding is not None:
        try:
            return len(_encoding.encode(text, disallowed_special=()))
        except Exception:
            pass
    # Fallback heuristic: ~4 characters per token
    return max(1, len(text) // 4)

def count_message_tokens(messages: List[BaseMessage]) -> int:
    """Calculate token count for a list of messages including format overhead."""
    # Base framing tokens (~3 tokens reply primer)
    total_tokens = 3
    for msg in messages:
        # Standard OpenAI message framing overhead: <|im_start|>{role}\n{content}<|im_end|>\n (~3 tokens)
        total_tokens += 3
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        total_tokens += count_tokens(content)
    return total_tokens

def get_max_input_budget(
    context_window: int = MODEL_CONTEXT_WINDOW,
    safety_margin: int = SAFETY_MARGIN_TOKENS,
    expected_completion: int = EXPECTED_COMPLETION_TOKENS
) -> int:
    """
    Calculate maximum safe input prompt tokens:
    Context Window - Safety Margin - Expected Output Tokens
    Default: 131,072 - 4,096 - 4,096 = 122,880 tokens.
    """
    budget = context_window - safety_margin - expected_completion
    return max(1000, budget)

def fit_context_within_budget(
    system_prompt: str,
    question: str,
    context_chunks: List[Dict[str, Any]],
    chat_history: Optional[List[Dict[str, Any]]] = None,
    max_input_tokens: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Enforces tokenizer-aware budget across:
    1. System instructions
    2. Current question
    3. Conversation history (recent messages prioritized within history allowance)
    4. Retrieved document chunks (ranked by relevance)
    
    Guarantees that the resulting prompt fits strictly within max_input_tokens.
    """
    if max_input_tokens is None:
        max_input_tokens = get_max_input_budget()

    fixed_tokens = count_tokens(system_prompt) + count_tokens(question) + 100  # Framing overhead
    available_tokens = max_input_tokens - fixed_tokens
    if available_tokens <= 0:
        logger.warning(f"Fixed prompt tokens ({fixed_tokens}) exceed maximum input budget ({max_input_tokens})")
        return [], []

    # 1. Budget conversation history (up to 2,000 tokens or 20% of available budget)
    history_budget = min(2000, max(500, available_tokens // 5))
    included_history: List[Dict[str, Any]] = []
    curr_hist_tokens = 0

    if chat_history:
        # Traverse history from newest to oldest
        for msg in reversed(chat_history):
            content = msg.get("content", "")
            m_tokens = count_tokens(content) + 6
            if curr_hist_tokens + m_tokens <= history_budget:
                included_history.insert(0, msg)
                curr_hist_tokens += m_tokens
            else:
                break

    # 2. Budget retrieved chunks with remaining available tokens
    chunk_budget = available_tokens - curr_hist_tokens
    included_chunks: List[Dict[str, Any]] = []
    curr_chunk_tokens = 0

    for chunk in context_chunks:
        title = chunk.get("page_title", "Source")
        url = chunk.get("source_url", "")
        text = chunk.get("content_excerpt", "").strip()
        formatted = f"--- [Source: {title} ({url})] ---\n{text}"
        c_tokens = count_tokens(formatted) + 10
        if curr_chunk_tokens + c_tokens <= chunk_budget:
            included_chunks.append(chunk)
            curr_chunk_tokens += c_tokens
        else:
            # Check if there is enough budget to safely include a truncated tail chunk
            remaining = chunk_budget - curr_chunk_tokens
            if remaining > 150:
                char_budget = remaining * 3
                new_chunk = dict(chunk)
                new_chunk["content_excerpt"] = text[:char_budget] + "\n[...truncated to fit token budget...]"
                included_chunks.append(new_chunk)
            break

    return included_chunks, included_history

def validate_prompt_tokens(messages: List[BaseMessage], max_allowed: Optional[int] = None) -> int:
    """Validate that message tokens stay strictly within configured budget."""
    total = count_message_tokens(messages)
    limit = max_allowed if max_allowed is not None else get_max_input_budget()
    if total > limit:
        raise ValueError(
            f"Prompt token count ({total}) exceeds safe input budget ({limit}) "
            f"for context window {MODEL_CONTEXT_WINDOW}."
        )
    return total
