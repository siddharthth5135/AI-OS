import sys

import httpx
import pytest

BASE_URL = "http://127.0.0.1:8000/api/v1"

# Skip this test in standard offline runs if the live container API is not running
try:
    httpx.get("http://127.0.0.1:8000/health", timeout=1.0)
except Exception:
    pytestmark = pytest.mark.skip(reason="Live local server not running on port 8000")


def test_flow():
    # 1. Signup a user
    signup_url = f"{BASE_URL}/auth/signup"
    signup_data = {
        "username": "testuser_persist",
        "email": "testuser_persist@example.com",
        "password": "Password123",
    }

    print("Sending signup request...")
    try:
        res = httpx.post(signup_url, json=signup_data, timeout=30.0)
        print(f"Signup response status: {res.status_code}")
        print(f"Signup response body: {res.text}")
        if res.status_code not in (
            201,
            200,
            400,
            409,
        ):  # 400/409 if user already exists
            print("Signup failed")
            sys.exit(1)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    # 2. Login
    login_url = f"{BASE_URL}/auth/login"
    login_data = {"email": "testuser_persist@example.com", "password": "Password123"}
    print("Sending login request...")
    res = httpx.post(login_url, json=login_data, timeout=30.0)
    print(f"Login response status: {res.status_code}")
    if res.status_code != 200:
        print("Login failed")
        sys.exit(1)

    token_info = res.json()["data"]
    access_token = token_info["access_token"]
    print(f"Access token retrieved: {access_token[:15]}...")

    headers = {"Authorization": f"Bearer {access_token}"}

    # 3. Check existing documents
    docs_url = f"{BASE_URL}/documents/"
    res = httpx.get(docs_url, headers=headers, timeout=30.0)
    print(f"Initial list documents status: {res.status_code}")
    initial_docs = res.json()["data"]
    print(f"Initial document count: {len(initial_docs)}")

    # 4. Upload a document if not already uploaded
    if len(initial_docs) == 0:
        upload_url = f"{BASE_URL}/documents/upload"
        files = {
            "file": ("test_doc.txt", b"Hello, this is a persistence test document!")
        }
        print("Uploading document...")
        res = httpx.post(upload_url, headers=headers, files=files, timeout=30.0)
        print(f"Upload response status: {res.status_code}")
        print(f"Upload response body: {res.text}")
        if res.status_code != 201:
            print("Upload failed")
            sys.exit(1)

        # Verify it was added
        res = httpx.get(docs_url, headers=headers, timeout=30.0)
        current_docs = res.json()["data"]
        print(f"Document list after upload: {len(current_docs)} documents")
        if len(current_docs) != 1:
            print("Document was not successfully added to the list")
            sys.exit(1)
        print("Upload verified successfully!")
    else:
        print("Document already exists. Proceed to verify persistence.")


if __name__ == "__main__":
    test_flow()
