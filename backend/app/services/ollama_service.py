import json
import logging
import math
import re
from typing import AsyncGenerator, Dict, Any, List, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

def _generate_fallback_embedding(text: str, dim: int = 384) -> List[float]:
    """Generates a normalized deterministic feature vector when offline/cloud without embedding API."""
    vec = [0.0] * dim
    words = re.findall(r'\w+', text.lower())
    if not words:
        return vec
    for word in words:
        # Simple polynomial rolling hash
        h = 0
        for char in word:
            h = (h * 31 + ord(char)) % dim
        vec[h] += 1.0
    # Normalize vector for cosine similarity
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec

class OllamaService:
    def __init__(self):
        raw = getattr(settings, "OLLAMA_HOST", "http://127.0.0.1:11434")
        if not raw.startswith("http://") and not raw.startswith("https://"):
            raw = f"http://{raw}"
        self.base_url = raw.replace("://0.0.0.0", "://127.0.0.1").rstrip("/")
        self.default_model = settings.OLLAMA_MODEL
        self.embed_model = settings.EMBEDDING_MODEL
        self.vision_model = settings.VISION_MODEL
        self.groq_base_url = "https://api.groq.com/openai/v1"

    @property
    def is_groq(self) -> bool:
        return settings.LLM_PROVIDER.lower() == "groq" and bool(settings.GROQ_API_KEY)

    async def check_health(self) -> Dict[str, Any]:
        """Check if AI service (Ollama or Groq) is running and ready."""
        if self.is_groq:
            return await self._check_groq_health()
        return await self._check_ollama_health()

    async def _check_groq_health(self) -> Dict[str, Any]:
        status = {
            "is_online": False,
            "ollama_host": "Groq Cloud (LPU)",
            "configured_model": settings.GROQ_MODEL,
            "model_installed": False,
            "embedding_model": "all-minilm (cloud vector)",
            "embedding_model_installed": True,
            "vision_model": "llama-3.2-11b-vision-preview",
            "vision_model_installed": True,
            "available_models": [],
            "error": None
        }
        try:
            headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(f"{self.groq_base_url}/models", headers=headers)
                if res.status_code == 200:
                    status["is_online"] = True
                    status["model_installed"] = True
                    data = res.json().get("data", [])
                    status["available_models"] = [
                        {"name": m.get("id"), "size": 0, "modified_at": ""}
                        for m in data
                    ]
                else:
                    status["error"] = f"Groq API returned HTTP {res.status_code}. Please check GROQ_API_KEY."
        except Exception as e:
            status["error"] = f"Unable to reach Groq Cloud: {str(e)}"
        return status

    async def _check_ollama_health(self) -> Dict[str, Any]:
        status = {
            "is_online": False,
            "ollama_host": self.base_url,
            "configured_model": self.default_model,
            "model_installed": False,
            "embedding_model": self.embed_model,
            "embedding_model_installed": False,
            "vision_model": self.vision_model,
            "vision_model_installed": False,
            "available_models": [],
            "error": None
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    status["is_online"] = True
                    models_data = res.json().get("models", [])
                    status["available_models"] = [
                        {
                            "name": m.get("name"),
                            "size": m.get("size"),
                            "modified_at": m.get("modified_at")
                        }
                        for m in models_data
                    ]
                    model_names = [m.get("name", "").lower() for m in models_data]

                    # Match base model
                    target_model = self.default_model.lower()
                    status["model_installed"] = any(
                        target_model in name or name.startswith(target_model.split(":")[0])
                        for name in model_names
                    )

                    # Match embedding model
                    target_embed = self.embed_model.lower()
                    status["embedding_model_installed"] = any(
                        target_embed in name for name in model_names
                    )

                    # Match vision model
                    target_vision = self.vision_model.lower()
                    status["vision_model_installed"] = any(
                        target_vision in name for name in model_names
                    )
                else:
                    status["error"] = f"Ollama returned HTTP {res.status_code}"
        except Exception as e:
            status["error"] = f"Unable to connect to Ollama at {self.base_url}: {str(e)}"
        return status

    async def list_models(self) -> List[Dict[str, Any]]:
        if self.is_groq:
            try:
                headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
                async with httpx.AsyncClient(timeout=8.0) as client:
                    res = await client.get(f"{self.groq_base_url}/models", headers=headers)
                    if res.status_code == 200:
                        return [{"name": m.get("id")} for m in res.json().get("data", [])]
            except Exception as e:
                logger.error(f"Error fetching Groq models: {e}")
            return []

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    return res.json().get("models", [])
        except Exception as e:
            logger.error(f"Error fetching Ollama models: {e}")
        return []

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        format_type: Optional[str] = None,
        images: Optional[List[str]] = None
    ) -> str:
        """Single non-streaming generate call to Ollama or Groq."""
        if self.is_groq:
            return await self._generate_groq(prompt, model, system, options, format_type)
        return await self._generate_ollama(prompt, model, system, options, format_type, images)

    def _sanitize_groq_model(self, model: Optional[str]) -> str:
        """Ensures the model name sent to Groq is a valid active cloud model."""
        target = model or settings.GROQ_MODEL
        if not target or ":" in target or target in [settings.OLLAMA_MODEL, "qwen2.5:3b", "qwen-2.5-32b"]:
            return "llama-3.3-70b-versatile"
        return target

    async def _generate_groq(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        format_type: Optional[str] = None
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        selected_model = self._sanitize_groq_model(model)
        payload: Dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "temperature": options.get("temperature", 0.7) if options else 0.7,
        }
        if format_type == "json":
            payload["response_format"] = {"type": "json_object"}

        try:
            headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(f"{self.groq_base_url}/chat/completions", json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                elif res.status_code == 404 and selected_model != "llama-3.3-70b-versatile":
                    # Fallback to standard Groq model if configured model not found
                    payload["model"] = "llama-3.3-70b-versatile"
                    res2 = await client.post(f"{self.groq_base_url}/chat/completions", json=payload, headers=headers)
                    if res2.status_code == 200:
                        return res2.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()

                error_msg = f"HTTP {res.status_code}"
                try:
                    error_msg = res.json().get("error", {}).get("message", error_msg)
                except Exception:
                    pass
                logger.error(f"Groq generate error: {error_msg}")
                return f"Error: Groq returned {error_msg}"
        except Exception as e:
            logger.error(f"Groq generate exception: {e}")
            return f"Error connecting to cloud AI service: {str(e)}"

    async def _generate_ollama(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        format_type: Optional[str] = None,
        images: Optional[List[str]] = None
    ) -> str:
        selected_model = model or self.default_model
        payload = {
            "model": selected_model,
            "prompt": prompt,
            "stream": False
        }
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options
        if format_type:
            payload["format"] = format_type
        if images:
            payload["images"] = images

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                res = await client.post(f"{self.base_url}/api/generate", json=payload)
                if res.status_code == 200:
                    return res.json().get("response", "").strip()
                else:
                    logger.error(f"Ollama generate error HTTP {res.status_code}: {res.text}")
                    return f"Error: Ollama HTTP {res.status_code}"
        except Exception as e:
            logger.error(f"Generate exception: {e}")
            return f"Unable to connect to local AI model. Please ensure Ollama is running. ({str(e)})"

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream chat tokens from Ollama or Groq."""
        if self.is_groq:
            async for token in self._chat_stream_groq(messages, model, options):
                yield token
        else:
            async for token in self._chat_stream_ollama(messages, model, options):
                yield token

    async def _chat_stream_groq(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        selected_model = self._sanitize_groq_model(model)
        temperature = options.get("temperature", 0.7) if options else 0.7
        top_p = options.get("top_p", 0.9) if options else 0.9
        max_tokens = options.get("num_predict", 2048) if options else 2048

        payload = {
            "model": selected_model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens
        }

        try:
            headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.groq_base_url}/chat/completions",
                    json=payload,
                    headers=headers
                ) as stream_resp:
                    if stream_resp.status_code != 200:
                        error_text = await stream_resp.aread()
                        detail = f"status {stream_resp.status_code}"
                        try:
                            err_json = json.loads(error_text.decode('utf-8', errors='ignore'))
                            detail = err_json.get("error", {}).get("message", detail)
                        except Exception:
                            pass

                        # If model is decommissioned or not found, automatically fallback to llama-3.3-70b-versatile
                        if selected_model != "llama-3.3-70b-versatile" and any(k in detail.lower() for k in ["decommissioned", "not found", "does not exist", "404"]):
                            logger.warning(f"Groq model {selected_model} issue ({detail}). Retrying with llama-3.3-70b-versatile.")
                            payload["model"] = "llama-3.3-70b-versatile"
                            async with client.stream(
                                "POST",
                                f"{self.groq_base_url}/chat/completions",
                                json=payload,
                                headers=headers
                            ) as fb_resp:
                                if fb_resp.status_code == 200:
                                    async for line in fb_resp.aiter_lines():
                                        if not line or not line.startswith("data: "):
                                            continue
                                        raw_data = line[6:].strip()
                                        if raw_data == "[DONE]":
                                            break
                                        try:
                                            chunk = json.loads(raw_data)
                                            choices = chunk.get("choices", [])
                                            if choices:
                                                content = choices[0].get("delta", {}).get("content", "")
                                                if content:
                                                    yield content
                                        except Exception:
                                            pass
                                    return

                        logger.error(f"Groq stream error: {detail}")
                        yield f"Error: Groq returned {detail}"
                        return

                    async for line in stream_resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        raw_data = line[6:].strip()
                        if raw_data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(raw_data)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
        except httpx.ConnectError:
            yield "Unable to connect to Groq cloud. Please check your internet connection."
        except httpx.TimeoutException:
            yield "\n[Generation timed out. Groq took too long to respond.]"
        except Exception as e:
            logger.error(f"Groq chat stream error: {e}")
            yield f"\n[Groq connection error: {str(e)}]"

    async def _chat_stream_ollama(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        selected_model = model or self.default_model
        payload = {
            "model": selected_model,
            "messages": messages,
            "stream": True
        }
        if options:
            payload["options"] = options

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                    if response.status_code != 200:
                        yield f"Error: Ollama returned status {response.status_code}"
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            msg = chunk.get("message", {})
                            content = msg.get("content", "")
                            if content:
                                yield content
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        except httpx.ConnectError:
            yield "Unable to connect to the local AI model. Please make sure Ollama is running."
        except httpx.TimeoutException:
            yield "\n[Generation timed out. The local model took too long to respond.]"
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield f"\n[Model connection error: {str(e)}]"

    async def embed(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Compute vector embeddings for a list of text strings."""
        if self.is_groq:
            # If Hugging Face token is provided, use HF Serverless feature extraction
            if settings.HUGGINGFACE_API_TOKEN:
                try:
                    headers = {"Authorization": f"Bearer {settings.HUGGINGFACE_API_TOKEN}"}
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        res = await client.post(
                            "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2",
                            json={"inputs": texts, "options": {"wait_for_model": True}},
                            headers=headers
                        )
                        if res.status_code == 200:
                            return res.json()
                except Exception as e:
                    logger.warning(f"HF embedding failed, falling back to local vector: {e}")
            # Robust deterministic vector representation for cloud deployment
            return [_generate_fallback_embedding(t) for t in texts]

        selected_model = model or self.embed_model
        embeddings: List[List[float]] = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            for text in texts:
                try:
                    payload = {"model": selected_model, "prompt": text}
                    res = await client.post(f"{self.base_url}/api/embeddings", json=payload)
                    if res.status_code == 200:
                        emb = res.json().get("embedding", [])
                        embeddings.append(emb)
                    else:
                        payload2 = {"model": selected_model, "input": text}
                        res2 = await client.post(f"{self.base_url}/api/embed", json=payload2)
                        if res2.status_code == 200:
                            emb2 = res2.json().get("embeddings", [[]])[0]
                            embeddings.append(emb2)
                        else:
                            embeddings.append(_generate_fallback_embedding(text))
                except Exception as e:
                    logger.error(f"Embedding error for text snippet: {e}")
                    embeddings.append(_generate_fallback_embedding(text))
        return embeddings

ollama_service = OllamaService()
