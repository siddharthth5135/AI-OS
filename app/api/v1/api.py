from fastapi import APIRouter

from app.api.routes import agents, auth, documents, llm, memory

api_router = APIRouter()

# Include routes
api_router.include_router(auth.router)
api_router.include_router(llm.router)
api_router.include_router(agents.router)
api_router.include_router(documents.router)
api_router.include_router(memory.router)
