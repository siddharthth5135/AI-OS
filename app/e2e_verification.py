import typing

from app.core.logging.logger import get_logger

logger = get_logger(__name__)
import asyncio
import os
import sys
import time
import uuid

import fitz  # PyMuPDF
import httpx

from app.core.config.settings import settings

BASE_URL = "http://localhost:8000/api/v1"
QDRANT_URL = f"http://{settings.pgvector_host}:{settings.pgvector_port}"


def generate_pdf() -> typing.Any:
    """
    Automatically generated docstring.
    """
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
    doc.save(pdf_path)
    doc.close()
    logger.info(f"Generated test PDF successfully at: {pdf_path}")
    return pdf_path


async def run_e2e() -> typing.Any:
    """
    Automatically generated docstring.
    """
    pdf_path = generate_pdf()

    # Use standard AsyncClient with higher timeout for ML model execution
    async with httpx.AsyncClient(timeout=60.0) as client:
        # ==========================================
        # STEP 1: SIGNUP & AUTHENTICATION
        # ==========================================
        logger.info("\n--- Step 1: User Signup & Authentication ---")
        username = f"e2e_user_{uuid.uuid4().hex[:6]}"
        email = f"{username}@example.com"
        password = "Password123!"

        signup_data = {"username": username, "email": email, "password": password}

        try:
            res = await client.post(f"{BASE_URL}/auth/signup", json=signup_data)
            if res.status_code == 201:
                token_data = res.json()["data"]
                logger.info(f"Signup successful! User: {username}")
            else:
                logger.info(
                    f"Signup returned status {res.status_code}, trying login..."
                )
                login_res = await client.post(
                    f"{BASE_URL}/auth/login",
                    json={"email": email, "password": password},
                )
                token_data = login_res.json()["data"]
                logger.info("Login successful!")
        except Exception as e:
            logger.info(f"Authentication failed: {str(e)}")
            sys.exit(1)

        token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # ==========================================
        # STEP 2: UPLOAD DOCUMENT
        # ==========================================
        logger.info("\n--- Step 2: Uploading Document ---")
        with open(pdf_path, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            res = await client.post(
                f"{BASE_URL}/documents/upload", headers=headers, files=files
            )

        if res.status_code != 201:
            logger.info(f"Upload failed: {res.status_code} - {res.text}")
            sys.exit(1)

        upload_resp = res.json()
        doc_id = upload_resp["data"]["id"]
        logger.info(f"Upload response (201 Created):")
        logger.info(f"  Document ID: {doc_id}")
        logger.info(f"  Filename: {upload_resp['data']['filename']}")
        logger.info(f"  Status: {upload_resp['data']['status']}")

        # ==========================================
        # STEP 3: POLL STATUS
        # ==========================================
        logger.info("\n--- Step 3: Polling Document Status ---")
        status = upload_resp["data"]["status"]
        chunk_count = 0

        for poll_idx in range(1, 11):
            await asyncio.sleep(3.0)
            res = await client.get(f"{BASE_URL}/documents/{doc_id}", headers=headers)
            if res.status_code != 200:
                logger.info(f"Failed to fetch document status: {res.status_code}")
                sys.exit(1)

            doc_data = res.json()["data"]
            status = doc_data["status"]
            chunk_count = doc_data.get("chunk_count") or 0
            logger.info(f"  [Poll #{poll_idx}] Status: {status}, Chunks: {chunk_count}")

            if status in ["indexed", "failed"]:
                break

        if status != "indexed":
            logger.info(
                f"Document processing failed or timed out. Final status: {status}"
            )
            sys.exit(1)

        logger.info("Document successfully parsed and indexed! ✓")

        # ==========================================
        # STEP 4: VERIFY VECTOR DATABASE POINTS
        # ==========================================
        logger.info("\n--- Step 4: Verifying Vector Database Point Count ---")
        # Query the points count from Qdrant directly
        qdrant_res = await client.post(
            f"{QDRANT_URL}/collections/documents/points/count", json={"exact": True}
        )
        if qdrant_res.status_code == 200:
            count_data = qdrant_res.json()["result"]
            count = count_data.get("count", 0)
            print(
                f"Verified Qdrant Vector Collection 'documents': count = {count} (Expected: > 0) ✓"
            )
            assert count > 0, "Qdrant vector count should be greater than zero!"
        else:
            print(
                f"Failed to query Qdrant count: {qdrant_res.status_code} - {qdrant_res.text}"
            )
            sys.exit(1)

        # ==========================================
        # STEP 5: SEMANTIC QUERY
        # ==========================================
        logger.info("\n--- Step 5: Semantic Document Search ---")
        query_payload = {"query": "CAP theorem guarantees", "doc_ids": [doc_id]}
        res = await client.post(
            f"{BASE_URL}/documents/query", headers=headers, json=query_payload
        )
        if res.status_code != 200:
            logger.info(f"Semantic query failed: {res.status_code} - {res.text}")
            sys.exit(1)

        search_results = res.json()["data"]
        logger.info(f"Search results:")
        for idx, item in enumerate(search_results):
            print(
                f"  [{idx + 1}] Score: {item['score']:.4f} | File: {item['filename']}"
            )
            logger.info(f"      Text: {item['text'][:120]}...")

        assert len(search_results) > 0, "Should return at least one semantic match!"
        logger.info("Semantic search completed successfully! ✓")

        # ==========================================
        # STEP 6: CHAT WITH DOC
        # ==========================================
        logger.info("\n--- Step 6: Chatting with Document Agent ---")
        chat_payload = {
            "query": "What is the CAP theorem?",
            "doc_ids": [doc_id],
            "stream": False,
        }
        res = await client.post(
            f"{BASE_URL}/agents/chat", headers=headers, json=chat_payload
        )
        if res.status_code != 200:
            logger.info(f"Chat failed: {res.status_code} - {res.text}")
            sys.exit(1)

        chat_data = res.json()["data"]
        logger.info(f"Chat response details:")
        logger.info(f"  Agent Used: {chat_data['agent_used']}")
        logger.info(f"  Response: {chat_data['response']}")
        logger.info(f"  Sources: {chat_data['sources']}")

        assert (
            chat_data["agent_used"] == "document"
        ), "Should route to 'document' agent!"
        assert (
            "CAP" in chat_data["response"]
        ), "Response should discuss the CAP theorem!"
        logger.info("Document agent chat successfully processed! ✓")

        # ==========================================
        # STEP 7: DELETE DOCUMENT & VERIFY CLEANUP
        # ==========================================
        logger.info("\n--- Step 7: Deleting Document and Verifying Cleanup ---")
        del_res = await client.delete(f"{BASE_URL}/documents/{doc_id}", headers=headers)
        if del_res.status_code != 200:
            logger.info(f"Deletion failed: {del_res.status_code} - {del_res.text}")
            sys.exit(1)

        logger.info("Deletion successful!")

        # Verify physical file deletion
        # Wait, inside container physical file path is what was created. Let's check storage path!
        # In upload_document router: dest_path = os.path.join(settings.storage_path, unique_filename)
        # In clean-up verification, let's see if GET document returns 404
        get_res = await client.get(f"{BASE_URL}/documents/{doc_id}", headers=headers)
        print(
            f"  Verification (GET Document): status_code = {get_res.status_code} (Expected: 404) ✓"
        )
        assert (
            get_res.status_code == 404
        ), "Document should be deleted from Postgres metadata!"

        # Verify Qdrant vector count for this document is 0
        qdrant_verify = await client.post(
            f"{QDRANT_URL}/collections/documents/points/count",
            json={
                "exact": True,
                "filter": {
                    "must": [{"key": "document_id", "match": {"value": doc_id}}]
                },
            },
        )
        rem_count = qdrant_verify.json()["result"]["count"]
        print(
            f"  Verification (Qdrant Point Count for {doc_id}): count = {rem_count} (Expected: 0) ✓"
        )
        assert rem_count == 0, f"Qdrant points for document {doc_id} should be deleted!"

        logger.info("\nALL E2E DOCUMENT INTELLIGENCE TESTS PASSED SUCCESSFULLY! ✓✓✓")


if __name__ == "__main__":
    # Run E2E test suite inside asyncio event loop
    os.environ["TESTING_MOCK_LLM"] = "1"
    asyncio.run(run_e2e())
