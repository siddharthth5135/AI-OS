# AI OS Deployment Guide

This guide provides step-by-step instructions for deploying the Multi-Agent AI Operating System (AI OS) to Render or Railway.

---

## Prerequisites
Before starting, ensure you have the following ready:
- A GitHub repository containing the AI OS codebase pushed to the `main` branch.
- An account on [Render](https://render.com) or [Railway](https://railway.app).
- A Google Gemini API key from [Google AI Studio](https://aistudio.google.com).
- A Supabase Project configured with PGVector and a Storage bucket named `documents`.
- An Upstash Redis database (if not using Render/Railway hosted Redis).

---

## Render Deployment (Step by Step)

### 1. Connect GitHub Repository to Render
1. Log in to your Render Dashboard.
2. Click **New +** and select **Blueprint**.
3. Connect your GitHub repository. Render will automatically parse the `render.yaml` configuration file from the repository root.

### 2. Configure Environment Variables
In the Render dashboard, go to the environment settings for both the Web Service (`ai-os-api`) and Worker Service (`ai-os-celery`) to supply the required secret values:

| Variable | Required | Source / Description | Example |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key | `AIzaSyCYvZct...` |
| `JWT_SECRET_KEY` | Yes | 64-character hex string for signing JWT tokens | `3266d6ed5611930bd34145d7ad95...` |
| `DATABASE_URL` | Yes | Supabase database connection string (use `postgresql+asyncpg://` protocol) | `postgresql+asyncpg://postgres.ref:pass@host:5432/postgres` |
| `SUPABASE_URL` | Yes | Supabase Project API URL | `https://hjgoomssudhyeowyeukx.supabase.co` |
| `SUPABASE_ANON_KEY` | Yes | Supabase anon public key | `eyJhbGciOiJIUzI...` |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key (for storage operations) | `eyJhbGciOiJIUzI...` |
| `DEBUG` | No | Toggle debug mode (Set to `False` in production) | `False` |

*Note: `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` are automatically linked via Render's Redis service.*

### 3. Deploy and Verify
1. Render will trigger a build of the production Docker image.
2. Once the web service status shows **Live**, navigate to `https://your-app-url.onrender.com/health` to verify that all systems are healthy.

---

## Railway Deployment (Step by Step)

### 1. Initialize Project
1. Log in to your Railway Dashboard.
2. Click **New Project** → **Deploy from GitHub repo**.
3. Select your AI OS repository.

### 2. Provision Database and Redis Services
1. In the Railway project board, click **New** → **Database** → **Redis**.
2. Railway will provision a Redis instance and inject `REDIS_URL` automatically.

### 3. Add Environment Variables
Add the environment variables listed in the Render section to the Railway service settings.

---

## Post-Deployment Verification

### 1. Verify Health Endpoint
Send a `GET` request to `/health`:
```bash
curl -f https://your-deployed-api.com/health
```
**Expected Response (200 OK):**
```json
{
  "status": "healthy",
  "services": {
    "postgres": { "ok": true, "latency_ms": 45 },
    "redis": { "ok": true, "latency_ms": 12 },
    "pgvector": { "ok": true },
    "gemini": { "ok": true }
  },
  "version": "0.1.0"
}
```

### 2. Create User Session
Send a `POST` request to `/api/v1/auth/signup`:
```bash
curl -X POST https://your-deployed-api.com/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"username":"prod_user","email":"user@example.com","password":"Password123"}'
```
**Expected Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhb...",
    "refresh_token": "eyJhb...",
    "token_type": "bearer"
  },
  "message": "User registered successfully"
}
```

### 3. Verify Agent Chat
Send a chat prompt to the agent orchestrator:
```bash
curl -X POST https://your-deployed-api.com/api/v1/agents/chat \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello AI OS!"}'
```

---

## Rollback Procedure
If a deployment fails or introduces a regression:
1. In the Render / Railway Dashboard, select the service.
2. Navigate to **Deployments** (Render) or **Activity** (Railway).
3. Find the last stable deployment.
4. Click the options menu and select **Rollback** or **Redeploy** to this version.
