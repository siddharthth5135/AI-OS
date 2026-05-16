# AI OS - Multi-Agent AI Operating System

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)

A production-grade Multi-Agent AI Operating System with LLM integration, vector storage, and intelligent agent orchestration.

## 🎯 Overview

AI OS is a comprehensive platform for building and deploying intelligent AI agents that can research, generate code, process documents, and orchestrate complex workflows. Built with modern async patterns, it provides a scalable foundation for multi-agent systems.

## ✨ Features

- **Modern FastAPI Application** with async/await patterns
- **Multi-Agent Architecture** supporting research, code, document, and workflow agents
- **LLM Integration** with Google Gemini
- **Vector Storage** for semantic search and embeddings
- **Background Task Processing** with Celery
- **Real-time Communication** via WebSockets
- **Production-Ready** with Docker, monitoring, and structured logging

## � Tech Stack

- **Framework**: FastAPI 0.111.0
- **Language**: Python 3.12+
- **Database**: PostgreSQL 16 (Supabase)
- **Cache**: Redis 7 (Upstash)
- **ORM**: SQLAlchemy 2.0.30 with AsyncIO
- **Validation**: Pydantic 2.7.1
- **AI/ML**: Google Gemini, sentence-transformers
- **Task Queue**: Celery 5.3.6
- **Containerization**: Docker & Docker Compose

## 📋 Prerequisites

- Python 3.12+
- pip
- Git 2.x+
- Docker Desktop (optional)

## ⚡ Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ai-os
```

### 2. Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 5. Run the Application

```bash
uvicorn app.main:app --reload
```

The application will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

## 🐳 Docker Deployment

```bash
docker compose up -d
```

This starts:
- FastAPI application (port 8000)
- PostgreSQL database (port 5432)
- Redis cache (port 6379)

## 📁 Project Structure

```
ai-os/
├── app/                    # Main application
│   ├── main.py            # FastAPI entry point
│   ├── api/               # API routes & WebSocket
│   ├── core/              # Config, security, logging
│   ├── db/                # Database models & migrations
│   ├── services/          # Business logic
│   ├── agents/            # AI agents
│   └── workers/           # Background tasks
├── tests/                 # Test suite
├── .env                   # Environment variables
├── requirements.txt       # Production dependencies
└── docker-compose.yml     # Service orchestration
```

## 🛠️ Available Commands

```bash
# Run application
uvicorn app.main:app --reload

# Run tests
pytest tests/ -v

# Format code
black app/ tests/
isort app/ tests/

# Docker commands
docker compose up -d       # Start services
docker compose down        # Stop services
docker compose logs -f     # View logs
```

## 📚 API Documentation

Once running, access the interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔐 Environment Variables

Key environment variables (see `.env` for full list):

- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `SUPABASE_URL` - Supabase API endpoint
- `SUPABASE_ANON_KEY` - Supabase anonymous key
- `SUPABASE_SERVICE_KEY` - Supabase service role key
- `GEMINI_API_KEY` - Google Gemini API key
- `JWT_SECRET_KEY` - JWT signing secret

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Format code: `black app/ tests/ && isort app/ tests/`
5. Run tests: `pytest tests/ -v`
6. Commit and push
7. Create a pull request

## � License

MIT License

Copyright (c) 2024 AI OS

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## 🆘 Support

For issues and questions:
- Create an issue in the repository
- Check API docs at `/docs`

---

**Built with ❤️ using FastAPI, Python 3.12, and modern async patterns**
