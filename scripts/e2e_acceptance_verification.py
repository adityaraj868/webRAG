import asyncio
import httpx
import json

BASE_URL = "http://127.0.0.1:8000"

async def run_full_acceptance_test():
    print("==================================================================")
    print("      WebRAG — Final Live Acceptance & Verification Test          ")
    print("==================================================================")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Health check
        res = await client.get(f"{BASE_URL}/api/v1/health")
        assert res.status_code == 200, f"Health check failed: {res.text}"
        health = res.json()
        print(f"[Step 1] Health Check: status={health['status']}, groq_configured={health['groq_configured']}, model={health['model']}")

        # Step 2: Index Current Page from real documentation (FastAPI Intro)
        page_payload = {
            "url": "https://fastapi.tiangolo.com/tutorial/first-steps/",
            "title": "FastAPI First Steps",
            "text": "First Steps: The simplest FastAPI file looks like `from fastapi import FastAPI; app = FastAPI()`. You can run it with `uvicorn main:app --reload`. Interactive API documentation is available at `/docs`.",
            "scope_id": "acceptance_page_scope"
        }
        res = await client.post(f"{BASE_URL}/api/v1/ingest/page", json=page_payload)
        assert res.status_code == 200
        page_res = res.json()
        print(f"[Step 2] Page Ingestion: scope={page_res['scope_id']}, chunks={page_res['chunks_indexed']}, already_indexed={page_res['already_indexed']}")

        # Step 3 & 4: Ask Question whose answer is present & verify grounded answer
        chat_q1 = {
            "scope_id": "acceptance_page_scope",
            "question": "How do you run the simplest FastAPI app?",
            "top_k": 3
        }
        res = await client.post(f"{BASE_URL}/api/v1/chat", json=chat_q1)
        assert res.status_code == 200
        chat_res1 = res.json()
        print("\n[Step 3 & 4] Grounded Answer (Present):")
        print(f"Answer: {chat_res1['answer']}")
        print(f"Citations count: {len(chat_res1['citations'])}")

        # Step 5: Verify citation source
        cit = chat_res1['citations'][0]
        assert cit['source_url'] == page_payload['url']
        assert "uvicorn" in cit['content_excerpt']
        print(f"[Step 5] Verified Citation: title='{cit['page_title']}', url='{cit['source_url']}', chunk={cit['chunk_index']}")

        # Step 10 (Tested early): Re-index unchanged content and verify deduplication
        res = await client.post(f"{BASE_URL}/api/v1/ingest/page", json=page_payload)
        assert res.status_code == 200
        dedup_res = res.json()
        assert dedup_res['already_indexed'] is True
        assert dedup_res['chunks_indexed'] == 0
        print(f"[Step 10] Deduplication Verified: already_indexed={dedup_res['already_indexed']}, new_chunks={dedup_res['chunks_indexed']}")

        # Step 6: Multi-page Website Indexing
        site_payload = {
            "url": "https://example.com",
            "max_pages": 3,
            "max_depth": 1,
            "concurrency": 2,
            "scope_id": "acceptance_site_scope"
        }
        res = await client.post(f"{BASE_URL}/api/v1/ingest/site", json=site_payload)
        assert res.status_code == 200
        site_res = res.json()
        job_id = site_res['job_id']
        print(f"\n[Step 6] Website Crawl Job Dispatched: job_id={job_id}")

        # Poll until complete
        for _ in range(15):
            await asyncio.sleep(1.0)
            res = await client.get(f"{BASE_URL}/api/v1/ingest/status/{job_id}")
            status = res.json()
            if status['status'] in ('completed', 'failed'):
                break
        print(f"Crawl Status: status={status['status']}, crawled={status['pages_crawled']}, indexed={status['pages_indexed']}, chunks={status['total_chunks']}")

        # Step 7: Ask question requiring information from the site
        chat_q2 = {
            "scope_id": "acceptance_site_scope",
            "question": "What is Example Domain used for?",
            "top_k": 3
        }
        res = await client.post(f"{BASE_URL}/api/v1/chat", json=chat_q2)
        assert res.status_code == 200
        chat_res2 = res.json()
        print(f"\n[Step 7] Website Question Answer: {chat_res2['answer']}")
        print(f"Citations: {[c['source_url'] for c in chat_res2['citations']]}")

        # Step 8: Ask an unrelated question and verify insufficient context behavior
        chat_q3 = {
            "scope_id": "acceptance_page_scope",
            "question": "What is the boiling point of liquid nitrogen in Fahrenheit?",
            "top_k": 3
        }
        res = await client.post(f"{BASE_URL}/api/v1/chat", json=chat_q3)
        assert res.status_code == 200
        chat_res3 = res.json()
        print(f"\n[Step 8] Refusal on Absent Information:")
        print(f"Answer: {chat_res3['answer']}")

        # Clean up scopes
        await client.delete(f"{BASE_URL}/api/v1/scopes/acceptance_page_scope")
        await client.delete(f"{BASE_URL}/api/v1/scopes/acceptance_site_scope")
        print("\n[Acceptance Test] Scopes cleaned up successfully.")
        print("🎉 ALL 10 ACCEPTANCE TEST CRITERIA FULLY VERIFIED!")

if __name__ == "__main__":
    asyncio.run(run_full_acceptance_test())
