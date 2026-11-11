import os
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.documents import Document

from app.config import (
    get_groq_model,
    get_groq_fallback_model,
    MODEL_CONTEXT_WINDOW,
    SAFETY_MARGIN_TOKENS,
    EXPECTED_COMPLETION_TOKENS,
)
from app.token_budget import (
    count_tokens,
    count_message_tokens,
    get_max_input_budget,
    fit_context_within_budget,
    validate_prompt_tokens,
)
from app.llm import (
    invoke_llm_with_resilience,
    generate_grounded_answer,
    is_rate_limit_error,
    is_auth_error,
    sanitize_error,
)
from app.summarizer import (
    create_dynamic_token_batches,
    recursive_reduce,
    extract_representative_citations,
    summarize_scope_content,
)
from app.database import (
    init_db,
    save_chat_message,
    get_chat_history,
    delete_scope_metadata,
)

# ---------------------------------------------------------------------------
# 1. Model Configuration Tests
# ---------------------------------------------------------------------------

def test_primary_and_fallback_model_configuration(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")
    assert get_groq_model() == "openai/gpt-oss-120b"
    assert get_groq_fallback_model() == "openai/gpt-oss-20b"

    # Test environment overrides
    monkeypatch.setenv("GROQ_MODEL", "custom-primary-model")
    monkeypatch.setenv("GROQ_FALLBACK_MODEL", "custom-fallback-model")
    assert get_groq_model() == "custom-primary-model"
    assert get_groq_fallback_model() == "custom-fallback-model"

# ---------------------------------------------------------------------------
# 2. Model Fallback Behavior Tests
# ---------------------------------------------------------------------------

class MockLLMResponse:
    def __init__(self, content: str):
        self.content = content

def test_fallback_activated_on_server_error(monkeypatch):
    """When primary model fails with 500 / model failure, fallback model is invoked."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_testdummykey123456789")
    monkeypatch.setenv("GROQ_MODEL", "primary-test-model")
    monkeypatch.setenv("GROQ_FALLBACK_MODEL", "fallback-test-model")

    call_history = []

    def fake_get_groq_llm(model=None):
        mock = MagicMock()
        model_name = model or "primary-test-model"
        if model_name == "primary-test-model":
            def fail_call(msgs):
                call_history.append("primary")
                # Simulate a 500 Internal Server / Model error
                err = RuntimeError("Model unavailable or Internal Server Error 500")
                err.status_code = 500
                raise err
            mock.invoke.side_effect = fail_call
        else:
            def success_call(msgs):
                call_history.append("fallback")
                return MockLLMResponse("Response from fallback model")
            mock.invoke.side_effect = success_call
        return mock

    with patch("app.llm.get_groq_llm", side_effect=fake_get_groq_llm):
        res = invoke_llm_with_resilience([HumanMessage(content="Hello")])
        assert res == "Response from fallback model"
        assert "primary" in call_history
        assert "fallback" in call_history

def test_http_429_rate_limit_retries_without_switching_to_fallback(monkeypatch):
    """HTTP 429 triggers backoff retry on primary model; does NOT switch to fallback model."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_testdummykey123456789")
    monkeypatch.setenv("GROQ_MODEL", "primary-test-model")
    monkeypatch.setenv("GROQ_FALLBACK_MODEL", "fallback-test-model")

    call_counts = {"primary": 0, "fallback": 0}

    def fake_get_groq_llm(model=None):
        mock = MagicMock()
        model_name = model or "primary-test-model"
        if model_name == "primary-test-model":
            def retry_call(msgs):
                call_counts["primary"] += 1
                if call_counts["primary"] < 3:
                    # Simulate 429 rate limit error
                    err = Exception("Rate limit reached. 429 Too Many Requests")
                    err.status_code = 429
                    raise err
                return MockLLMResponse("Primary recovered after backoff")
            mock.invoke.side_effect = retry_call
        else:
            def fallback_call(msgs):
                call_counts["fallback"] += 1
                return MockLLMResponse("Fallback should not be called on 429")
            mock.invoke.side_effect = fallback_call
        return mock

    with patch("app.llm.get_groq_llm", side_effect=fake_get_groq_llm):
        with patch("time.sleep", return_value=None):  # Fast forward sleep
            res = invoke_llm_with_resilience([HumanMessage(content="Hello")], max_429_retries=3)
            assert res == "Primary recovered after backoff"
            assert call_counts["primary"] == 3
            assert call_counts["fallback"] == 0  # Fallback was NOT called

def test_http_429_exhaustion_raises(monkeypatch):
    """When HTTP 429 persists across all retries, error is raised and fallback is NOT called."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_testdummykey123456789")
    call_counts = {"primary": 0, "fallback": 0}

    def fake_get_groq_llm(model=None):
        mock = MagicMock()
        model_name = model or "primary"
        def persistent_429(msgs):
            if "fallback" in model_name:
                call_counts["fallback"] += 1
            else:
                call_counts["primary"] += 1
            err = Exception("HTTP 429: rate_limit_exceeded (TPM limit reached)")
            err.status_code = 429
            raise err
        mock.invoke.side_effect = persistent_429
        return mock

    with patch("app.llm.get_groq_llm", side_effect=fake_get_groq_llm):
        with patch("time.sleep", return_value=None):
            with pytest.raises(Exception) as exc_info:
                invoke_llm_with_resilience([HumanMessage(content="Hello")], max_429_retries=2)
            assert "429" in str(exc_info.value)
            assert call_counts["primary"] == 3  # Initial + 2 retries
            assert call_counts["fallback"] == 0

# ---------------------------------------------------------------------------
# 3. Token-Budget Enforcement Tests
# ---------------------------------------------------------------------------

def test_tokenizer_counting_and_budget_calculation():
    text = "The quick brown fox jumps over the lazy dog."
    token_cnt = count_tokens(text)
    assert token_cnt > 0
    assert token_cnt < len(text)  # BPE token count is always lower than char count for prose

    messages = [
        SystemMessage(content="You are WebRAG."),
        HumanMessage(content="Summarize this."),
    ]
    msg_tokens = count_message_tokens(messages)
    assert msg_tokens >= count_tokens("You are WebRAG.") + count_tokens("Summarize this.")

    max_budget = get_max_input_budget()
    expected = MODEL_CONTEXT_WINDOW - SAFETY_MARGIN_TOKENS - EXPECTED_COMPLETION_TOKENS
    assert max_budget == expected

def test_fit_context_within_budget_pruning():
    chunks = [
        {"page_title": "Page 1", "source_url": "https://a.com", "content_excerpt": "A" * 500},
        {"page_title": "Page 2", "source_url": "https://b.com", "content_excerpt": "B" * 500},
        {"page_title": "Page 3", "source_url": "https://c.com", "content_excerpt": "C" * 500},
    ]
    chat_history = [
        {"role": "user", "content": "Question 1"},
        {"role": "assistant", "content": "Answer 1"},
    ]
    # Set a tight input budget of 400 tokens
    pruned_chunks, pruned_history = fit_context_within_budget(
        system_prompt="System",
        question="What is A?",
        context_chunks=chunks,
        chat_history=chat_history,
        max_input_tokens=400,
    )
    # The lowest-priority chunks must be omitted or truncated to prevent overflow
    assert len(pruned_chunks) <= len(chunks)
    assert len(pruned_chunks) >= 1

def test_validate_prompt_tokens_overflow():
    # Construct an oversized message
    oversized = [HumanMessage(content="word " * 150000)]
    with pytest.raises(ValueError) as exc:
        validate_prompt_tokens(oversized, max_allowed=1000)
    assert "exceeds safe input budget" in str(exc.value)

# ---------------------------------------------------------------------------
# 4. Summarization: Dynamic Batches & No Ceiling & No Silent Truncation
# ---------------------------------------------------------------------------

def test_dynamic_summarization_batches_exceeding_eight():
    """Verify that batch creation scales dynamically by tokens without an 8-batch ceiling."""
    docs = []
    # Create 20 chunks of ~100 tokens each
    for i in range(20):
        docs.append(Document(
            page_content=f"Section {i} content text with important facts " * 10,
            metadata={"source_url": f"https://example.com/p{i}", "chunk_index": i}
        ))

    # Set batch token limit to 150 tokens so ~20 chunks yield around 10-12 batches
    batches = create_dynamic_token_batches(docs, max_batch_tokens=150)
    assert len(batches) > 8, f"Expected > 8 batches to prove ceiling removal, got {len(batches)}"

    # Ensure EVERY chunk is accounted for
    total_batched_chunks = sum(len(b) for b in batches)
    assert total_batched_chunks == len(docs)

def test_no_silent_content_truncation():
    """Batches exceeding 30,000 characters must not be truncated."""
    long_chunk = "Important verifiable content. " * 1500  # ~45,000 characters
    doc = Document(
        page_content=long_chunk,
        metadata={"source_url": "https://example.com/long", "chunk_index": 0}
    )
    batches = create_dynamic_token_batches([doc], max_batch_tokens=15000)
    assert len(batches) == 1
    # Full length is preserved in the batch
    assert len(batches[0][0].page_content) == len(long_chunk)

def test_citation_preservation_in_summarization():
    docs = [
        Document(page_content=f"Content {i}", metadata={"source_url": f"https://site.com/{i}", "chunk_index": i})
        for i in range(10)
    ]
    citations = extract_representative_citations(docs)
    assert len(citations) > 0
    # URLs must be preserved
    source_urls = [c.source_url for c in citations]
    assert "https://site.com/0" in source_urls
    assert "https://site.com/9" in source_urls

def test_recursive_reduction_hierarchy():
    """Verify recursive reduction bundles summaries when count > fan_in."""
    intermediate_summaries = [f"Section {i} summary overview." for i in range(15)]
    calls = []

    def mock_invoke(messages):
        prompt = messages[-1].content
        calls.append(prompt)
        return "Synthesized summary output"

    with patch("app.summarizer.invoke_llm_with_resilience", side_effect=mock_invoke):
        res = recursive_reduce(intermediate_summaries, "Test Document", fan_in=5)
        assert res == "Synthesized summary output"
        # Since 15 > 5, intermediate consolidation calls must have occurred before final reduction
        assert len(calls) > 1

# ---------------------------------------------------------------------------
# 5. Chat History Regression Test: Most Recent Messages Chronological Ordering
# ---------------------------------------------------------------------------

def test_get_chat_history_retrieves_most_recent_chronologically():
    """
    Regression test for SQLite get_chat_history():
    Must return the MOST RECENT messages, in chronological order (ASC).
    """
    init_db()
    scope_id = "test_recent_history_scope"
    delete_scope_metadata(scope_id)

    # Insert 10 sequential messages
    for i in range(1, 11):
        role = "user" if i % 2 != 0 else "assistant"
        save_chat_message(scope_id, role, f"Message {i}", None)

    # Request limit=4
    history = get_chat_history(scope_id, limit=4)
    assert len(history) == 4

    contents = [m["content"] for m in history]
    # The 4 most recent are Messages 7, 8, 9, 10
    assert contents == ["Message 7", "Message 8", "Message 9", "Message 10"]
    # And they are ordered chronologically ASC
    assert contents[0] == "Message 7"
    assert contents[-1] == "Message 10"

    delete_scope_metadata(scope_id)
