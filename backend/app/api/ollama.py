from fastapi import APIRouter
from app.services.ollama_service import ollama_service
from app.schemas.schemas import OllamaStatusResponse

router = APIRouter(prefix="/api/ollama", tags=["Ollama Status"])

@router.get("/status", response_model=OllamaStatusResponse)
async def get_ollama_status():
    """Returns real-time status of Ollama connection and installed models."""
    health_data = await ollama_service.check_health()
    return OllamaStatusResponse(**health_data)

@router.get("/models")
async def get_models():
    """Returns list of models installed in Ollama."""
    models = await ollama_service.list_models()
    return {"models": models}
