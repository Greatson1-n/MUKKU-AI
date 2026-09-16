import logging
from typing import Optional, Dict, Any
import httpx
from app.core.config import settings
from app.services.ollama_service import ollama_service

logger = logging.getLogger(__name__)

class VisionService:
    def __init__(self):
        self.vision_model = settings.VISION_MODEL

    async def is_vision_available(self) -> bool:
        """Checks if a vision-capable model is installed in Ollama."""
        status = await ollama_service.check_health()
        return status.get("vision_model_installed", False)

    async def describe_image(self, base64_image: str, prompt: str = "Describe this image thoroughly and in detail, noting any text, objects, layout, and colors.") -> str:
        """
        Sends the image to the local vision model (e.g. moondream:latest)
        and extracts a detailed textual description to pass to Qwen2.5.
        """
        if not await self.is_vision_available():
            return (
                "Vision Model Offline: A vision-capable model (such as moondream or llava) is not available "
                "in your local Ollama instance. Please run `ollama pull moondream` to enable image understanding."
            )

        # Strip data URL prefix if present
        clean_b64 = base64_image
        if "," in base64_image:
            clean_b64 = base64_image.split(",", 1)[1]

        try:
            description = await ollama_service.generate(
                prompt=prompt,
                model=self.vision_model,
                images=[clean_b64]
            )
            return description
        except Exception as e:
            logger.error(f"Vision model error: {e}")
            return f"Error analyzing image with vision model: {str(e)}"

vision_service = VisionService()
