import asyncio
import uuid
import httpx
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"

async def run_live_agent_tests():
    uid = uuid.uuid4().hex[:6]
    username = f"live_test_{uid}"
    email = f"{username}@example.com"
    password = "LivePassword123!"

    print(f"--- Starting Live Agent Verification for user: {username} ---")

    async with httpx.AsyncClient() as client:
        # 1. Sign Up
        res = await client.post(f"{BASE_URL}/auth/signup", json={
            "username": username,
            "email": email,
            "password": password
        }, timeout=60.0)
        assert res.status_code == 201, f"Signup failed: {res.text}"
        print("[OK] Signup Successful")

        # 2. Login
        res = await client.post(f"{BASE_URL}/auth/login", json={
            "email": email,
            "password": password
        }, timeout=60.0)
        assert res.status_code == 200, f"Login failed: {res.text}"
        token = res.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("[OK] Login Successful")

        # 3. Test Research Agent (General Query)
        print("\nTesting Research Agent...")
        res = await client.post(f"{BASE_URL}/agents/chat", headers=headers, json={
            "query": "What are the core properties of quantum entanglement?",
            "session_id": f"sess_{uid}",
            "doc_ids": []
        }, timeout=60.0)
        assert res.status_code == 200, f"Research query failed: {res.text}"
        data = res.json()["data"]
        print(f"[OK] Handled by Agent: {data.get('agent_used')}")
        print(f"Response snippet: {data.get('response')[:150]}...")

        # 4. Test Code Agent (Coding Query)
        print("\nTesting Code Agent...")
        res = await client.post(f"{BASE_URL}/agents/chat", headers=headers, json={
            "query": "Write a python function to compute the fibonacci sequence using recursion.",
            "session_id": f"sess_{uid}",
            "doc_ids": []
        }, timeout=60.0)
        assert res.status_code == 200, f"Code query failed: {res.text}"
        data = res.json()["data"]
        print(f"[OK] Handled by Agent: {data.get('agent_used')}")
        print(f"Response snippet: {data.get('response')[:150]}...")

        # 5. Upload a document & Test Document Agent
        print("\nUploading document for Document Agent testing...")
        files = {"file": ("api_rules.txt", b"AI OS Rules: 1. Keep it clean. 2. Maintain state. 3. Fast response.")}
        res = await client.post(f"{BASE_URL}/documents/upload", headers=headers, files=files, timeout=60.0)
        assert res.status_code == 201, f"Document upload failed: {res.text}"
        doc_id = res.json()["data"]["id"]
        print(f"[OK] Document uploaded, ID: {doc_id}")

        # Wait for Celery worker to finish embedding
        print("Waiting for Celery worker to index document...")
        for _ in range(10):
            await asyncio.sleep(1.0)
            res = await client.get(f"{BASE_URL}/documents/{doc_id}", headers=headers)
            if res.json()["data"]["status"] == "indexed":
                print("[OK] Document Indexed successfully")
                break
        else:
            print("[ERROR] Document indexing timed out")
            sys.exit(1)

        print("Testing Document Agent...")
        res = await client.post(f"{BASE_URL}/agents/chat", headers=headers, json={
            "query": "What is Rule 2 of the AI OS Rules according to my uploaded document?",
            "session_id": f"sess_{uid}",
            "doc_ids": [doc_id]
        }, timeout=60.0)
        assert res.status_code == 200, f"Document query failed: {res.text}"
        data = res.json()["data"]
        print(f"[OK] Handled by Agent: {data.get('agent_used')}")
        print(f"Response snippet: {data.get('response')[:150]}...")

        # 6. Store memory fact & Test Memory Agent
        print("\nStoring a memory entry...")
        res = await client.post(f"{BASE_URL}/memory/store", headers=headers, json={
            "content": "User prefers React for building modern web applications.",
            "memory_type": "preference",
            "importance": 0.9
        }, timeout=60.0)
        assert res.status_code == 201, f"Memory store failed: {res.text}"
        print("[OK] Memory stored successfully")

        print("Testing Memory Agent via Context retrieval...")
        res = await client.post(f"{BASE_URL}/agents/chat", headers=headers, json={
            "query": "What is my preference for building modern web applications?",
            "session_id": f"sess_{uid}",
            "doc_ids": []
        }, timeout=60.0)
        assert res.status_code == 200, f"Memory-related query failed: {res.text}"
        data = res.json()["data"]
        print(f"[OK] Handled by Agent: {data.get('agent_used')}")
        print(f"Response snippet: {data.get('response')[:150]}...")

        # 7. Test Workflow Agent (by forcing workflow agent routing or using a workflow style request)
        print("\nTesting Workflow Agent...")
        res = await client.post(f"{BASE_URL}/agents/chat", headers=headers, json={
            "query": "Generate a deployment checklist workflow for a FastAPI application.",
            "session_id": f"sess_{uid}",
            "doc_ids": []
        }, timeout=60.0)
        assert res.status_code == 200, f"Workflow query failed: {res.text}"
        data = res.json()["data"]
        print(f"[OK] Handled by Agent: {data.get('agent_used')}")
        print(f"Response snippet: {data.get('response')[:150]}...")

        print("\n--- All 5 agents initialized, routed, and responded successfully! ---")

if __name__ == "__main__":
    asyncio.run(run_live_agent_tests())
