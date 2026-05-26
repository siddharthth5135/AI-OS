import asyncio
import uuid

import fitz  # PyMuPDF
import pytest
from httpx import AsyncClient

from app.main import app


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Configures the testing environment variables."""
    monkeypatch.setenv("TESTING_MOCK_LLM", "1")


@pytest.mark.asyncio
async def test_full_user_journey():
    """
    Executes the full user journey integration test:
    1. Sign up new user
    2. Log in
    3. Generate test PDF and upload it
    4. Poll until the document is successfully parsed and indexed in the background
    5. Chat about the document (queries the Document Agent)
    6. Save a long-term factual preference memory
    7. Chat referencing preferences (forces Python generation)
    8. Retrieve chat logs/history
    9. Check health endpoint status
    10. Delete document and confirm cleanup
    11. Log out user
    """
    uid = uuid.uuid4().hex[:6]
    username = f"int_user_{uid}"
    email = f"int_user_{uid}@example.com"
    password = "Password123!"

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 1. Sign up
        signup_payload = {"username": username, "email": email, "password": password}
        res = await ac.post("/api/v1/auth/signup", json=signup_payload)
        assert res.status_code == 201, f"Signup failed: {res.text}"
        data = res.json()["data"]
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Login
        login_payload = {"email": email, "password": password}
        res = await ac.post("/api/v1/auth/login", json=login_payload)
        assert res.status_code == 200, f"Login failed: {res.text}"
        assert "access_token" in res.json()["data"]

        # 3. Create test PDF document and Upload
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(
            (50, 50),
            "Consistency, Availability, and Partition Tolerance in CAP theorem.",
        )
        pdf_bytes = doc.write()
        doc.close()

        files = {"file": ("test_doc.pdf", pdf_bytes, "application/pdf")}
        res = await ac.post("/api/v1/documents/upload", headers=headers, files=files)
        assert res.status_code == 201, f"Upload failed: {res.text}"
        doc_id = res.json()["data"]["id"]
        assert doc_id is not None

        # 4. Poll until the document status becomes "indexed"
        for _ in range(10):
            await asyncio.sleep(0.5)
            res = await ac.get(f"/api/v1/documents/{doc_id}", headers=headers)
            assert res.status_code == 200
            if res.json()["data"]["status"] == "indexed":
                break
        else:
            pytest.fail("Document parsing timed out or failed to reach indexed status")

        # 5. Chat about the document
        chat_payload = {
            "query": "What is the CAP theorem?",
            "session_id": f"sess_{uid}",
            "doc_ids": [doc_id],
        }
        res = await ac.post("/api/v1/agents/chat", headers=headers, json=chat_payload)
        assert res.status_code == 200, f"Chat failed: {res.text}"
        chat_data = res.json()["data"]
        assert chat_data["agent_used"] == "document"
        assert "CAP" in chat_data["response"]

        # 6. Store a memory preference
        mem_payload = {
            "content": "User prefers python development preference",
            "memory_type": "preference",
            "importance": 0.8,
        }
        res = await ac.post("/api/v1/memory/store", headers=headers, json=mem_payload)
        assert res.status_code == 201, f"Memory store failed: {res.text}"
        assert "id" in res.json()["data"]

        # 7. Chat referencing the memory
        chat_payload2 = {
            "query": "Show me code based on my programming preferences",
            "session_id": f"sess_{uid}",
            "doc_ids": [],
        }
        res = await ac.post("/api/v1/agents/chat", headers=headers, json=chat_payload2)
        assert res.status_code == 200, f"Chat referencing memory failed: {res.text}"
        chat_data2 = res.json()["data"]
        assert "python" in chat_data2["response"].lower()

        # 8. Check chat history log
        res = await ac.get(
            f"/api/v1/memory/history?session_id=sess_{uid}", headers=headers
        )
        assert res.status_code == 200
        history_list = res.json()["data"]
        assert len(history_list) >= 2

        # 9. Check health endpoint status (allow degraded 207 or healthy 200 depending on external systems)
        res = await ac.get("/health")
        assert res.status_code in (200, 207)

        # 10. Clean up (delete document and verify deletion)
        res = await ac.delete(f"/api/v1/documents/{doc_id}", headers=headers)
        assert res.status_code == 200

        res = await ac.get(f"/api/v1/documents/{doc_id}", headers=headers)
        assert res.status_code == 404

        # 11. Logout user session
        res = await ac.post("/api/v1/auth/logout", headers=headers)
        assert res.status_code == 200
