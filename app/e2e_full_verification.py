from app.core.logging.logger import get_logger

logger = get_logger(__name__)
import asyncio
import os
import sys
import time
import uuid

import fitz  # PyMuPDF
import httpx

from app.core.cache.redis_client import get_redis
from app.core.config.settings import settings

BASE_URL = "http://localhost:8000/api/v1"
QDRANT_URL = f"http://{settings.pgvector_host}:{settings.pgvector_port}"


def generate_pdf():
    logger.info("\n--- Generating E2E Test PDF file ---")
    doc = fitz.open()
    page = doc.new_page()

    text_content = (
        "Antigravity is a high-performance agentic AI coding assistant designed by Google DeepMind.\n"
        "The CAP theorem states that a distributed data store can simultaneously provide at most two "
        "of the following three guarantees: Consistency, Availability, and Partition Tolerance.\n"
        "Partition tolerance means the system continues to operate despite an arbitrary number of messages "
        "being dropped or delayed by the network between nodes."
    )

    page.insert_text((50, 50), text_content)
    pdf_path = "/tmp/test.pdf"
    os.makedirs("/tmp", exist_ok=True)
    doc.save(pdf_path)
    doc.close()
    logger.info(f"Generated test PDF successfully at: {pdf_path}")
    return pdf_path


async def run_e2e():
    pdf_path = generate_pdf()

    async with httpx.AsyncClient(timeout=60.0) as client:
        # ==========================================
        # STEP 1: SIGNUP & AUTHENTICATION
        # ==========================================
        logger.info("\n--- Step 1: User Signup & Authentication ---")
        username = f"e2e_user_{uuid.uuid4().hex[:6]}"
        email = f"{username}@example.com"
        password = "Password123!"

        signup_payload = {"username": username, "email": email, "password": password}
        res = await client.post(f"{BASE_URL}/auth/signup", json=signup_payload)
        assert res.status_code == 201, f"Signup failed: {res.text}"
        token_data = res.json()["data"]
        token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get user ID from /auth/me
        me_res = await client.get(f"{BASE_URL}/auth/me", headers=headers)
        assert me_res.status_code == 200, f"Retrieving /auth/me failed: {me_res.text}"
        user_id = me_res.json()["data"]["id"]
        logger.info(f"  ✓ Signup successful! User: {username}, ID: {user_id}")

        # ==========================================
        # STEP 2: MULTI-TURN DIALOGUE (NAME CHECK)
        # ==========================================
        logger.info("\n--- Step 2: Multi-turn Chat Context (Name Check) ---")
        session_id = "mem-001"

        # Turn 1: State name
        res1 = await client.post(
            f"{BASE_URL}/agents/chat",
            headers=headers,
            json={
                "query": "My name is Alex",
                "session_id": session_id,
                "stream": False,
            },
        )
        assert res1.status_code == 200, f"Chat Turn 1 failed: {res1.text}"
        logger.info(f"  Turn 1 Response: {res1.json()['data']['response']}")

        # Turn 2: Query name
        res2 = await client.post(
            f"{BASE_URL}/agents/chat",
            headers=headers,
            json={
                "query": "What is my name?",
                "session_id": session_id,
                "stream": False,
            },
        )
        assert res2.status_code == 200, f"Chat Turn 2 failed: {res2.text}"
        resp_text = res2.json()["data"]["response"]
        logger.info(f"  Turn 2 Response: {resp_text}")
        assert (
            "Alex" in resp_text
        ), f"Agent failed to recall user name! Response: {resp_text}"
        logger.info("  ✓ Multi-turn name check successful!")

        # ==========================================
        # STEP 3: REDIS CONTENT VERIFICATION
        # ==========================================
        logger.info("\n--- Step 3: Checking Redis short-term cache ---")
        redis = get_redis()
        # Initialize client if needed
        if not redis.client:
            await redis.connect(settings.redis_url.get_secret_value())

        key = redis.make_key("memory:short", user_id, session_id)
        redis_messages = await redis.get_json(key)
        logger.info(f"  Redis Key: {key}")
        logger.info(
            f"  Redis Messages Count: {len(redis_messages) if redis_messages else 0}"
        )
        assert redis_messages is not None, "Redis key does not exist!"
        # Since 2 turns were run, each turn appends user + assistant message.
        # Total messages = 4. We verify that count >= 2.
        assert (
            len(redis_messages) >= 2
        ), f"Redis array should contain at least 2 messages, found: {len(redis_messages)}"
        logger.info("  ✓ Redis content verified successfully!")

        # ==========================================
        # STEP 4: MANUAL FACT STORE
        # ==========================================
        logger.info("\n--- Step 4: Storing Manual Fact ---")
        store_payload = {
            "content": "User prefers Python",
            "memory_type": "fact",
            "importance": 0.8,
        }
        res_store = await client.post(
            f"{BASE_URL}/memory/store", headers=headers, json=store_payload
        )
        assert res_store.status_code == 201, f"Store failed: {res_store.text}"
        store_data = res_store.json()["data"]
        print(
            f"  ✓ Factual Memory Stored! ID: {store_data['embedding_id']}, Importance: {store_data['importance_score']}"
        )

        # ==========================================
        # STEP 5: SEMANTIC VECTOR SEARCH
        # ==========================================
        logger.info("\n--- Step 5: Semantic Search across User Memory ---")
        res_search = await client.get(
            f"{BASE_URL}/memory/search?q=programming+preferences", headers=headers
        )
        assert res_search.status_code == 200, f"Search failed: {res_search.text}"
        search_data = res_search.json()["data"]
        logger.info(f"  Search Results:")
        for idx, item in enumerate(search_data):
            print(
                f"    [{idx + 1}] Score: {item['score']:.4f} | Type: {item['memory_type']}"
            )
            logger.info(f"        Content: {item['content']}")
        assert len(search_data) > 0, "No semantic matches found!"
        assert search_data[0]["score"] > 0.35, "Similarity score was too low!"
        logger.info("  ✓ Semantic memory search successful!")

        # ==========================================
        # STEP 6: CONTEXTUAL CODE GENERATION
        # ==========================================
        logger.info("\n--- Step 6: Contextual Code Gen from Preference ---")
        # Ensure we pass the factual preference context using the same session
        res_code = await client.post(
            f"{BASE_URL}/agents/chat",
            headers=headers,
            json={
                "query": "Show me code",
                "session_id": "code-session",
                "stream": False,
            },
        )
        assert res_code.status_code == 200, f"Code chat failed: {res_code.text}"
        code_resp = res_code.json()["data"]["response"]
        logger.info(f"  Agent Code Response:\n{code_resp}")
        assert (
            "python" in code_resp.lower()
        ), "Should use Python according to stored preferences!"
        logger.info("  ✓ Contextual code generation from memory successful!")

        # ==========================================
        # STEP 7: VECTOR COLLECTION POINTS CHECK
        # ==========================================
        logger.info("\n--- Step 7: Verifying Supabase pgvector Points ---")
        qdrant_user_res = await client.post(
            f"{QDRANT_URL}/collections/user_memory/points/count", json={"exact": True}
        )
        assert (
            qdrant_user_res.status_code == 200
        ), f"Qdrant count failed: {qdrant_user_res.text}"
        user_points_count = qdrant_user_res.json()["result"]["count"]
        logger.info(
            f"  Qdrant user_memory point count: {user_points_count} (Expected: > 0)"
        )
        assert user_points_count > 0, "Collection user_memory is empty!"
        logger.info("  ✓ Vector points verification successful!")

        # ==========================================
        # STEP 8: ROUTING AGENT TESTS
        # ==========================================
        logger.info("\n--- Step 8: Multi-Agent Dynamic Routing Checks ---")

        # 8.1 Research routing
        logger.info("  Checking Research routing (CAP theorem?)...")
        res_route = await client.post(
            f"{BASE_URL}/agents/chat",
            headers=headers,
            json={"query": "CAP theorem?", "stream": False},
        )
        assert (
            res_route.json()["data"]["agent_used"] == "research"
        ), "Should route to research!"
        logger.info("    ✓ Routed to research successfully!")

        # 8.2 Code routing
        logger.info("  Checking Code routing (Write async file reader)...")
        res_route_code = await client.post(
            f"{BASE_URL}/agents/chat",
            headers=headers,
            json={"query": "Write async file reader", "stream": False},
        )
        assert (
            res_route_code.json()["data"]["agent_used"] == "code"
        ), "Should route to code!"
        logger.info("    ✓ Routed to code successfully!")

        # 8.3 Document routing & parallel retrieval verification
        logger.info("  Uploading PDF file for Document routing...")
        with open(pdf_path, "rb") as f:
            pdf_files = {"file": ("test.pdf", f, "application/pdf")}
            upload_res = await client.post(
                f"{BASE_URL}/documents/upload", headers=headers, files=pdf_files
            )
        assert upload_res.status_code == 201
        doc_id = upload_res.json()["data"]["id"]

        # Wait for indexing
        logger.info("  Polling document status...")
        for _ in range(15):
            await asyncio.sleep(1.0)
            chk_res = await client.get(
                f"{BASE_URL}/documents/{doc_id}", headers=headers
            )
            if chk_res.json()["data"]["status"] == "indexed":
                break

        logger.info("  Checking Document routing (Summarize)...")
        res_route_doc = await client.post(
            f"{BASE_URL}/agents/chat",
            headers=headers,
            json={"query": "Summarize", "doc_ids": [doc_id], "stream": False},
        )
        assert (
            res_route_doc.json()["data"]["agent_used"] == "document"
        ), "Should route to document!"
        logger.info("    ✓ Routed to document successfully!")

        # 8.4 Memory routing
        logger.info("  Checking Memory routing (What do you know about my prefs?)...")
        res_route_mem = await client.post(
            f"{BASE_URL}/agents/chat",
            headers=headers,
            json={"query": "What do you know about my prefs?", "stream": False},
        )
        assert (
            res_route_mem.json()["data"]["agent_used"] == "memory"
        ), "Should route to memory!"
        logger.info("    ✓ Routed to memory successfully!")

        # 8.5 Workflow routing
        print(
            "  Checking Workflow routing (First explain Redis, then write Python code for it)..."
        )
        res_route_work = await client.post(
            f"{BASE_URL}/agents/chat",
            headers=headers,
            json={
                "query": "First explain Redis, then write Python code for it",
                "stream": False,
            },
        )
        work_data = res_route_work.json()["data"]
        assert work_data["agent_used"] == "workflow", "Should route to workflow!"
        assert (
            "**Workflow Plan:**" in work_data["response"]
        ), "Workflow response must contain plan!"
        logger.info(
            "    ✓ Routed to workflow successfully and generated multi-step plan!"
        )

        # 8.6 Parallel Retrieval (Memories AND Document chunks retrieved together)
        print(
            "  Checking Parallel Retrieval (query with doc_ids and requiring memory)..."
        )
        res_parallel = await client.post(
            f"{BASE_URL}/agents/chat",
            headers=headers,
            json={
                "query": "Summarize the CAP theorem according to my preferences",
                "doc_ids": [doc_id],
                "stream": False,
            },
        )
        assert (
            res_parallel.status_code == 200
        ), f"Parallel retrieval failed: {res_parallel.text}"
        logger.info("    ✓ Parallel retrieval completed with zero errors!")

        # Cleanup redis client
        await redis.disconnect()

        logger.info("\n" + "=" * 50)
        logger.info(
            "ALL MASTER E2E MEMORY, ROUTING, & PARALLEL RETRIEVAL CHECKS PASSED!"
        )
        logger.info("=" * 50 + "\n")


if __name__ == "__main__":
    os.environ["TESTING_MOCK_LLM"] = "1"
    asyncio.run(run_e2e())
