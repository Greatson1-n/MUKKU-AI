import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

from pydantic import field_validator

def sanitize_ollama_host(raw_host: str) -> str:
    if not raw_host:
        return "http://127.0.0.1:11434"
    host = str(raw_host).strip()
    if not host.startswith("http://") and not host.startswith("https://"):
        host = f"http://{host}"
    return host.replace("://0.0.0.0", "://127.0.0.1").rstrip("/")

class Settings(BaseSettings):
    APP_NAME: str = "MUKKU.AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # LLM Provider Configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")  # "ollama" or "groq"
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    HUGGINGFACE_API_TOKEN: str = os.getenv("HUGGINGFACE_API_TOKEN", "")

    # Ollama Configuration
    OLLAMA_HOST: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-minilm")
    VISION_MODEL: str = os.getenv("VISION_MODEL", "moondream")

    @field_validator("OLLAMA_HOST", mode="before")
    @classmethod
    def check_ollama_host(cls, v):
        return sanitize_ollama_host(v)

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{DATA_DIR / 'mukku.db'}"
    )

    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "mukku_ai_super_secret_local_key_2026")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_DAYS: int = 30

    # Paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    UPLOAD_DIR: Path = UPLOAD_DIR

    # Limits
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: set = {".pdf", ".docx", ".txt", ".md", ".csv", ".json"}
    MAX_CONTEXT_TOKENS: int = 3000
    RECENT_MESSAGES_COUNT: int = 6

    # System Defaults
    DEFAULT_SYSTEM_PROMPT: str = (
        "You are a helpful local AI assistant running through Ollama and Qwen2.5 3B Instruct.\n"
        "You should:\n"
        "- Answer clearly\n"
        "- Be concise when the question is simple\n"
        "- Explain difficult concepts step-by-step\n"
        "- Admit uncertainty\n"
        "- Never fabricate information intentionally\n"
        "- Use information supplied by tools when available\n"
        "- Follow the user's instructions\n"
        "- Maintain conversation context\n"
        "- Ask for clarification only when necessary\n"
        "- Format answers using Markdown\n"
        "- Use code blocks for programming code\n"
        "- Avoid unnecessary repetition"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
