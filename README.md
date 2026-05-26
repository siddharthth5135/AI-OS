# AI OS — Multi-Agent AI Operating System

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL Vector](https://img.shields.io/badge/PostgreSQL-pgvector-blue?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Redis-7-red?logo=redis&logoColor=white)](https://redis.io/)
[![Supabase](https://img.shields.io/badge/Supabase-Vector-green?logo=supabase&logoColor=white)](https://supabase.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![CI Status](https://img.shields.io/badge/CI-Passing-brightgreen?logo=github-actions&logoColor=white)](https://github.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AI OS is a production-grade, highly scalable multi-agent AI operating system and backend infrastructure. Engineered from the ground up to support autonomous agents, it provides real-time task classification, contextual short/long-term memory synchronization, and document intelligence pipelines. It is designed to act as an enterprise-ready AI orchestration layer that handles complex multi-step workflows while keeping API response times to a minimum.

🔗 **Live Deployment Portfolio Link**: [https://ai-os-api.onrender.com](https://ai-os-api.onrender.com)  
📂 **Standalone Visual Flowcharts**: [diagrams/architecture.md](file:///d:/AI%20OS/diagrams/architecture.md)

---

## 🎯 Overview

AI OS serves as a comprehensive demonstration of modern async systems engineering, showcasing how multiple state-of-the-art AI agents can pair-program, research, and act in concert under a unified gateway. Rather than serving as a basic wrapper around LLM endpoints, AI OS operates as a full-fledged agent controller that manages:
1. **Dynamic Task Routing**: Automatically classifies queries (Research, Code, Document QA, Workflow, Memory) using an optimized combination of direct heuristic scoring and LLM fallback routing.
2. **Context-Aware Semantic Memory**: Dynamically injects Redis-cached short-term conversation logs and long-term PostgreSQL vector-embedded facts into agent contexts before calling the LLM.
3. **Async Document Parsing**: Pyro-processes heavy document uploads (PDF, TXT, MD) using PyMuPDF and SentenceTransformer embeddings, offloading tasks to background Celery workers so the gateway remains unblocked.
4. **Real-time Event Streaming**: Broadcasts task-routing lifecycle events and token streaming directly to clients via WebSockets and Server-Sent Events (SSE).

---

## 🏗️ Architecture

```
                       ┌───────────────────────────────┐
                       │     Client (HTTP / WS / SSE)  │
                       └───────────────┬───────────────┘
                                       │
                        API Route / WS │ (Uvicorn / FastAPI Gateway)
                                       ▼
                       ┌───────────────────────────────┐
                       │        FastAPI Gateway        │◄───────┐
                       │    (Auth, Route Security)     │        │
                       └───────────────┬───────────────┘        │
                                       │                        │ Task Stats /
                                       ▼                        │ Health Checks
                       ┌───────────────────────────────┐        │
                       │    Intelligent Orchestrator   ├────────┘
                       └───────┬───────────────┬───────┘
                               │               │
        Retrieve Context (10ms)│               │ Dispatch Heavy Parse (Async)
                               ▼               ▼
                ┌──────────────┴───────┐┌──────┴───────────────┐
                │ Redis Session Cache  ││     Celery Workers   │
                │ (Short-Term Memory)  ││ (Document Parsing)   │
                └──────────────────────┘└──────┬───────────────┘
                                               │
                                               │ Generate Embeddings & Index
                                               ▼
                ┌──────────────────────────────┴───────┐
                │        PostgreSQL + pgvector         │
                │   (Relational DB & Long-Term Vector) │
                └──────────────────────────────────────┘
```

### 🛠️ Technology Stack Matrix

| Category | Technology | Version | Purpose in Architecture |
| :--- | :--- | :--- | :--- |
| **Backend Core** | FastAPI | 0.111.0 | Asynchronous API gateway, routing, and WS controller |
| **Web Server** | Uvicorn | 0.29.0 | High-performance ASGI web server interface |
| **Relational DB** | PostgreSQL | 16 | Relational store for users, chats, and background tasks |
| **Vector Database**| pgvector | 0.5.1 | Vector similarity search engine for long-term memory & docs |
| **Caching / Store**| Redis | 7.x | Redis client for short-term chat logs and celery broker |
| **Task Queue** | Celery | 5.3.6 | Distributed task manager for background processing |
| **Async ORM** | SQLAlchemy | 2.0.30 | Async transactional database mapper |
| **Migrations** | Alembic | 1.13.1 | Database schema evolution and tracking |
| **Validation** | Pydantic | 2.7.1 | Strict request/response validation and serialization |
| **Local Models** | SentenceTransformers| 2.7.0 | CPU-offloaded offline embedding generation |
| **Cognitive LLM** | Google Gemini API | 1.5-Flash| Primary reasoning engine for agent executors |
| **Containers** | Docker / Compose | 20.10+ | Production replication and orchestration containerization |

---

## 🗂️ Project Structure

```
ai-os/
├── .github/
│   └── workflows/
│       └── ci.yml            # CI workflow running linter and unit tests on PRs
├── app/
│   ├── main.py               # Application startup entry point
│   ├── api/
│   │   ├── dependencies/     # Database and auth injectables
│   │   ├── routes/           # REST endpoints (auth, agents, documents, memory, etc.)
│   │   └── websocket/        # Real-time WebSocket connection handlers
│   ├── core/
│   │   ├── cache/            # Redis client wrappers
│   │   ├── config/           # Pydantic Settings configuration
│   │   ├── logging/          # Structlog configuration
│   │   ├── middleware/       # Structured request logging middleware
│   │   └── security/         # Password hashing and JWT helpers
│   ├── db/
│   │   ├── database.py       # Engine creation and session mapping
│   │   ├── models/           # Declarative base database tables (Chat, Task, Document, User)
│   │   └── session/          # Dependency local session wrappers
│   ├── services/
│   │   ├── documents/        # Document extraction and chunking business logic
│   │   ├── embeddings/       # Embedding translation service
│   │   ├── llm/              # Google Gemini client and prompting templates
│   │   ├── memory/           # Memory score_importance and retrieval logic
│   │   └── orchestration/    # AgentOrchestrator and task classifier
│   └── workers/
│       ├── celery_app.py     # Celery worker application configuration
│       ├── cleanup_worker.py # Periodic file and database cleanup tasks
│       ├── document_worker.py# Background document chunking and indexing tasks
│       └── embedding_worker.py# Background assistant response long-term embedding tasks
├── diagrams/                 # Standalone Mermaid system design flowcharts
├── docs/
│   ├── DEPLOYMENT.md         # Production deployment and configuration guide
│   └── PERFORMANCE.md        # Latency baselines and performance optimizations
├── tests/                    # Fully mock-contained test suites
│   ├── conftest.py           # Pytest configurations, DB overrides, and worker mocks
│   ├── test_integration.py   # E2E test running user-journey API operations
│   ├── test_memory_features.py# Unit tests for scoring and short-term memory
│   └── test_persistence.py   # Live integration test against container instance
├── Dockerfile                # Production multi-stage Docker build config
├── docker-compose.yml        # Development services layout (FastAPI + DB + Redis + Worker)
├── render.yaml               # Render Blueprint deployment definition
└── requirements.txt          # Pinned production dependencies
```

---

## ⚡ Quick Start

### 1. Configure the Environment
Ensure Python 3.12+ is installed. Clone the repository and copy the environment template:
```bash
git clone https://github.com/yourusername/ai-os.git
cd ai-os
cp .env.example .env
```
Edit `.env` and fill in the required keys, especially `GEMINI_API_KEY`, `DATABASE_URL`, and `REDIS_URL`.

### 2. Local Setup
```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate      # On Windows
# source venv/bin/activate # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run database migrations
alembic upgrade head

# Start the FastAPI application locally
uvicorn app.main:app --reload
```
The application will be available at:
* **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **API Redoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

### 3. Docker Compose Development
To run the full stack locally with hot reloading (FastAPI, Postgres, Redis, Celery worker) in one command:
```bash
docker compose up -d --build
```
This automatically sets up all dependencies and mounts the codebase for active development.

---

## 📚 API Reference

AI OS exposes 20+ distinct REST endpoints and a WebSocket streaming channel.

### Authentication Endpoints
* **`POST /api/v1/auth/signup`**: Creates a new user account.
* **`POST /api/v1/auth/login`**: Authenticates user and returns JWT tokens.
* **`POST /api/v1/auth/refresh`**: Exchanges a refresh token for a new access token.
* **`GET /api/v1/auth/me`**: Returns the current authenticated user details.
* **`POST /api/v1/auth/logout`**: Invalidates the current user session.

### Agent Orchestration Endpoints
* **`POST /api/v1/agents/chat`**: Routes a chat query to the designated agent (Research, Code, Document, Memory, Workflow) with support for context injection and SSE streaming.
* **`POST /api/v1/agents/code`**: Directly routes the query to the Code Agent, passing programming languages and source snippets.
* **`GET /api/v1/agents/task/{task_id}`**: Retrieves metadata and execution status for a background orchestrated task.

### Document Intelligence Endpoints
* **`POST /api/v1/documents/upload`**: Uploads and registers a new document (PDF, TXT, MD), dispatching it to background Celery workers.
* **`GET /api/v1/documents/`**: Lists all documents owned by the active user.
* **`GET /api/v1/documents/{document_id}`**: Retrieves status, metadata, and error details of a specific document.
* **`DELETE /api/v1/documents/{document_id}`**: Deletes the document record and removes all associated vectors from the vector store.
* **`POST /api/v1/documents/query`**: Directly executes a semantic similarity search against indexed document chunks.

### Memory Endpoints
* **`GET /api/v1/memory/history`**: Retrieves recent conversational message logs for the user, filtered optionally by `session_id`.
* **`POST /api/v1/memory/store`**: Manually generates and registers a new factual memory entry in PostgreSQL + pgvector.
* **`GET /api/v1/memory/search`**: Runs similarity queries against the user's registered long-term facts.
* **`DELETE /api/v1/memory/{memory_id}`**: Removes a specific memory entry.
* **`POST /api/v1/memory/consolidate`**: Manually triggers consolidation of short-term logs into long-term memories.

### System & Observability Endpoints
* **`GET /health`**: Returns composite health status checking database, Redis, and overall system connectivity.
* **`GET /metrics`**: Serves Prometheus-compatible performance metrics (token counts, request latency, Celery task status).
* **`GET /api/v1/admin/stats`**: Admin dashboard endpoint summarizing total registered users, documents, memories, active WebSockets, and token consumption.

---

### 🔌 WebSocket Client Code Snippet

Use this JavaScript snippet to open a bi-directional streaming connection to the AI OS WebSocket server:

```javascript
const token = "YOUR_JWT_ACCESS_TOKEN";
const wsUrl = `ws://localhost:8000/ws/chat?token=${token}`;
const socket = new WebSocket(wsUrl);

socket.onopen = (event) => {
    console.log("[Connected] WebSocket handshake complete.");
    
    // Send a streaming request message
    const requestPayload = {
        query: "Explain the CAP Theorem and show Python code referencing it.",
        session_id: "demo-session-123",
        doc_ids: []
    };
    socket.send(JSON.stringify(requestPayload));
};

socket.onmessage = (event) => {
    const response = JSON.parse(event.data);
    
    if (response.type === "task_update") {
        console.log(`[Status Update]: ${response.data.status}`);
    } else if (response.type === "token") {
        process.stdout.write(response.data.text); // Stream token chunks in real-time
    } else if (response.type === "task_completed") {
        console.log(`\n[Completed] Latency: ${response.data.latency_ms}ms`);
        socket.close();
    } else if (response.type === "error") {
        console.error(`[Error]: ${response.data.message}`);
    }
};

socket.onclose = () => console.log("[Disconnected] WebSocket closed.");
```

---

## 📊 Observability & Performance

* **Prometheus Metrics**: Exposes metrics on `/metrics` to track API request latency (`TASK_LATENCY`), total requests (`TASKS_TOTAL`), and daily token consumption (`LLM_TOKENS`).
* **Structured Logging**: Configured with `structlog` to emit JSON-formatted logs to standard output, making it fully compatible with cloud log aggregators (Datadog, Grafana Loki, Render log stream).
* **Performance Baselines**: Latency and pipeline statistics are extensively analyzed and documented. See [docs/PERFORMANCE.md](file:///d:/AI%20OS/docs/PERFORMANCE.md) for full benchmarks.

---

## 🧪 Testing

The repository contains unit and integration test suites running offline against a local SQLite database with fully mocked LLM response generators.

```bash
# Run the complete test suite
.\venv\Scripts\pytest tests/ -v --asyncio-mode=auto
```

Expected output:
```
tests/test_integration.py::test_full_user_journey PASSED
tests/test_memory_features.py::test_score_importance PASSED
tests/test_memory_features.py::test_short_term_memory PASSED
```

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Make changes and format them: `.\venv\Scripts\black app/ tests/ && .\venv\Scripts\isort app/ tests/`
4. Verify all tests pass: `.\venv\Scripts\pytest tests/ -v --asyncio-mode=auto`
5. Propose your changes via a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
