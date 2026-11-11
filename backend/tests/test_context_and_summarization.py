import pytest
from app.database import init_db, delete_scope_metadata, get_chat_history
from app.vectorstore import delete_documents_by_scope, get_all_chunks_by_scope
from app.pipeline import ingest_document, query_rag
from app.summarizer import is_summarization_query
from app.llm import rewrite_query_with_context

@pytest.fixture(autouse=True)
def setup_teardown():
    init_db()
    yield
    delete_documents_by_scope("test_wiki_scope")
    delete_scope_metadata("test_wiki_scope")
    delete_documents_by_scope("test_isolated_scope")
    delete_scope_metadata("test_isolated_scope")

def test_summarization_query_detection():
    # True positives
    assert is_summarization_query("summarize") is True
    assert is_summarization_query("Summarize this page") is True
    assert is_summarization_query("Give me an overview") is True
    assert is_summarization_query("What is this page about?") is True
    assert is_summarization_query("Can you summarize this article?") is True
    assert is_summarization_query("tl;dr") is True

    # False positives (specific queries should NOT be treated as whole-document summarization)
    assert is_summarization_query("When was he born?") is False
    assert is_summarization_query("What were the major military battles?") is False
    assert is_summarization_query("Explain his rise to power in 1933") is False

def test_query_rewriter_resolves_pronouns():
    history = [
        {"role": "user", "content": "Tell me about Nikola Tesla."},
        {"role": "assistant", "content": "Nikola Tesla was a Serbian-American inventor, electrical engineer, and futurist best known for his contributions to the design of the alternating current (AC) electricity supply system."}
    ]

    # Test pronoun 'his' / 'he'
    rewritten1 = rewrite_query_with_context("What were his main inventions?", history)
    assert "Tesla" in rewritten1 or "Nikola" in rewritten1

    # Test ordinal reference
    rewritten2 = rewrite_query_with_context("Tell me more about him.", history)
    assert "Tesla" in rewritten2 or "Nikola" in rewritten2

def test_wikipedia_summarization_and_conversation_workflow():
    scope_id = "test_wiki_scope"
    url = "https://en.wikipedia.org/wiki/Nikola_Tesla"
    title = "Nikola Tesla - Wikipedia"

    # Construct multi-chunk biography article
    sections = [
        "Nikola Tesla was a Serbian-American inventor, electrical engineer, mechanical engineer, and futurist. He was born on 10 July 1856 in Smiljan in the Austrian Empire.",
        "Early years: Tesla studied engineering and physics in the 1870s without receiving a degree, and gained practical experience in the early 1880s working in telephony and at Continental Edison in the new electric power industry.",
        "Emigration to the United States: In 1884 Tesla emigrated to the United States, where he became a naturalized citizen. He worked for a short time at the Edison Machine Works in New York City before striking out on his own.",
        "Alternating Current and the Induction Motor: With the help of partners to finance and market his ideas, Tesla set up laboratories and companies in New York to develop a range of electrical and mechanical devices. His alternating current (AC) induction motor and related polyphase AC patents, licensed by Westinghouse Electric in 1888, earned him a considerable amount of money and became the cornerstone of the polyphase system which that company eventually marketed.",
        "Wireless Power and Colorado Springs: Attempting to develop inventions he could patent and market, Tesla conducted a range of experiments with mechanical oscillators and generators, electrical discharge tubes, and early X-ray imaging. He also built a wireless-controlled boat, one of the first ever exhibited. In 1899, Tesla moved to Colorado Springs, where he conducted high-frequency, high-voltage experiments.",
        "Wardenclyffe Tower project: In 1900, Tesla attempted to build an intercontinental wireless communication and power transmitter, the Wardenclyffe Tower, but ran out of funding before he could complete it.",
        "Later years and Death: After Wardenclyffe, Tesla experimented with a series of inventions in the 1910s and 1920s with varying degrees of success. Having spent most of his money, Tesla lived in a series of New York hotels, leaving behind unpaid bills. He died in room 3327 of the Hotel New Yorker on 7 January 1943 at the age of 86.",
    ]
    full_text = "\n\n".join(sections)

    s_id, t, chunk_count, _ = ingest_document(
        url=url,
        title=title,
        text=full_text,
        scope_id=scope_id,
        scope_type="page"
    )
    assert chunk_count >= 1

    # 1. Test "summarize"
    summary_ans, summary_cits, found_summary = query_rag(scope_id, "summarize")
    assert found_summary is True
    assert "Tesla" in summary_ans
    assert len(summary_cits) > 0
    # Verifies the system produces a meaningful overview rather than refusing
    assert "cannot answer" not in summary_ans.lower()
    assert "insufficient information" not in summary_ans.lower()

    # 2. Specific factual question about a later section (Wardenclyffe)
    fact_ans, fact_cits, found_fact = query_rag(scope_id, "What happened to the Wardenclyffe Tower project?")
    assert found_fact is True
    assert "funding" in fact_ans.lower() or "uncompleted" in fact_ans.lower() or "wireless" in fact_ans.lower()

    # 3. Follow-up question using pronoun "he" / "his"
    followup_ans, followup_cits, found_followup = query_rag(scope_id, "Where did he die?")
    assert found_followup is True
    assert "New Yorker" in followup_ans or "Hotel" in followup_ans or "January 1943" in followup_ans

    # 4. Conversation history in SQLite
    chat_hist = get_chat_history(scope_id)
    # 3 questions + 3 answers = 6 messages
    assert len(chat_hist) == 6
    assert chat_hist[0]["role"] == "user"
    assert chat_hist[0]["content"] == "summarize"

    # 5. Switch to another scope and verify that previous scope info is NOT leaked
    isolated_scope = "test_isolated_scope"
    ingest_document(
        url="https://plants.org/botany",
        title="Botany Basics",
        text="Photosynthesis is the process used by plants to convert light energy into chemical energy.",
        scope_id=isolated_scope,
        scope_type="page"
    )

    iso_ans, iso_cits, _ = query_rag(isolated_scope, "Where did he die?")
    # The isolated scope has NO Tesla context and NO Tesla chat history
    assert "Tesla" not in iso_ans
    assert "New Yorker" not in iso_ans

    # 6. Unrelated question should still refuse to hallucinate
    unrelated_ans, _, _ = query_rag(scope_id, "What is the average speed of a migrating swallow in miles per hour?")
    assert "cannot answer" in unrelated_ans.lower() or "insufficient" in unrelated_ans.lower()
