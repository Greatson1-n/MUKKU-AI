import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import Base, engine
from app.api import auth, chat, conversations, documents, memory, ollama, settings as app_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("mukku.ai")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} startup complete.")
    yield
    logger.info("Shutting down application...")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Local AI Chatbot Assistant powered by Ollama + Qwen2.5 3B Instruct",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global error handler to prevent stack traces leaking to normal users
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "An unexpected error occurred. Please try again or check AI service status."}
    )

# Health endpoint
@app.get("/api/health")
def health_check():
    is_groq = settings.LLM_PROVIDER.lower() == "groq"
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "provider": settings.LLM_PROVIDER,
        "ollama_host": "Groq Cloud" if is_groq else settings.OLLAMA_HOST,
        "default_model": settings.GROQ_MODEL if is_groq else settings.OLLAMA_MODEL
    }

# Register Routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(documents.router)
app.include_router(memory.router)
app.include_router(ollama.router)
app.include_router(app_settings.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
