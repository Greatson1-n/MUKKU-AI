import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.models import Memory
from app.services.ollama_service import ollama_service
from app.services.rag_service import cosine_similarity

logger = logging.getLogger(__name__)

class MemoryService:
    @staticmethod
    def get_user_memories(db: Session, user_id: str, active_only: bool = True) -> List[Memory]:
        q = db.query(Memory).filter(Memory.user_id == user_id)
        if active_only:
            q = q.filter(Memory.is_active == True)
        return q.order_by(Memory.updated_at.desc()).all()

    @staticmethod
    def add_memory(db: Session, user_id: str, content: str, category: str = "preference") -> Memory:
        mem = Memory(user_id=user_id, content=content.strip(), category=category, is_active=True)
        db.add(mem)
        db.commit()
        db.refresh(mem)
        return mem

    @staticmethod
    def update_memory(db: Session, memory_id: str, user_id: str, content: Optional[str] = None, is_active: Optional[bool] = None, category: Optional[str] = None) -> Optional[Memory]:
        mem = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user_id).first()
        if not mem:
            return None
        if content is not None:
            mem.content = content.strip()
        if is_active is not None:
            mem.is_active = is_active
        if category is not None:
            mem.category = category
        db.commit()
        db.refresh(mem)
        return mem

    @staticmethod
    def delete_memory(db: Session, memory_id: str, user_id: str) -> bool:
        mem = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user_id).first()
        if not mem:
            return False
        db.delete(mem)
        db.commit()
        return True

    @classmethod
    async def get_relevant_memories(
        cls,
        db: Session,
        user_id: str,
        query: str,
        limit: int = 3
    ) -> List[str]:
        """Finds active memories relevant to the query to inject into context."""
        memories = cls.get_user_memories(db, user_id, active_only=True)
        if not memories:
            return []

        # If very few memories, return all up to limit
        if len(memories) <= limit:
            return [m.content for m in memories]

        # Semantic ranking
        try:
            mem_texts = [m.content for m in memories]
            embeddings = await ollama_service.embed(mem_texts + [query])
            if len(embeddings) == len(mem_texts) + 1:
                query_emb = embeddings[-1]
                scored = []
                for i, m in enumerate(memories):
                    score = cosine_similarity(query_emb, embeddings[i])
                    scored.append((score, m.content))
                scored.sort(key=lambda x: x[0], reverse=True)
                return [item[1] for item in scored[:limit] if item[0] > 0.2]
        except Exception as e:
            logger.warning(f"Memory semantic ranking failed, falling back to recent: {e}")

        return [m.content for m in memories[:limit]]

    @classmethod
    async def auto_extract_memory(cls, db: Session, user_id: str, user_message: str) -> Optional[Memory]:
        """
        Extracts persistent user preferences or facts from chat turn if present.
        Uses structured JSON prompt.
        """
        # Fast rule check to avoid calling model unnecessarily
        trigger_phrases = ["i prefer", "i like", "remember that", "my name is", "i am working on", "my tech stack", "always use", "never use"]
        msg_lower = user_message.lower()
        if not any(phrase in msg_lower for phrase in trigger_phrases):
            return None

        prompt = (
            f"Analyze this user message: \"{user_message}\"\n"
            "Extract any durable user fact, preference, or project info that should be remembered.\n"
            "Respond strictly in valid JSON format:\n"
            "{\"has_memory\": true, \"fact\": \"<concise 1-sentence statement>\", \"category\": \"preference|project|fact\"}\n"
            "If no durable memory exists, respond with:\n"
            "{\"has_memory\": false, \"fact\": \"\", \"category\": \"\"}"
        )

        try:
            raw = await ollama_service.generate(prompt=prompt, format_type="json")
            data = json.loads(raw)
            if data.get("has_memory") and data.get("fact"):
                fact = data["fact"].strip()
                cat = data.get("category", "preference")
                # Check for duplicate
                existing = db.query(Memory).filter(Memory.user_id == user_id, Memory.content == fact).first()
                if not existing:
                    return cls.add_memory(db, user_id, fact, cat)
        except Exception as e:
            logger.debug(f"Auto memory extraction skipped: {e}")
        return None

memory_service = MemoryService()
