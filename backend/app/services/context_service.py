import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Conversation, Message
from app.services.ollama_service import ollama_service
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)

# Approximate token estimator (1 token ~= 4 chars)
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

class ContextService:
    @staticmethod
    def get_system_instructions(
        custom_system_prompt: Optional[str] = None,
        language: str = "en",
        memories: Optional[List[str]] = None
    ) -> str:
        """Constructs a lean, targeted system prompt for Qwen2.5 3B."""
        base_prompt = custom_system_prompt or settings.DEFAULT_SYSTEM_PROMPT

        # Multilingual instruction
        lang_note = ""
        if language and language.lower() not in ["en", "english"]:
            lang_map = {
                "hi": "Hindi",
                "hindi": "Hindi",
                "mni": "Manipuri (Meitei Mayek / Meiteilon)",
                "manipuri": "Manipuri (Meitei Mayek / Meiteilon)",
                "es": "Spanish",
                "fr": "French",
                "de": "German",
                "bn": "Bengali"
            }
            lang_name = lang_map.get(language.lower(), language)
            lang_note = (
                f"\n\n[Language Requirement]: The user requested responses in {lang_name}.\n"
                "Respond in this requested language. IMPORTANT: Do NOT translate programming code, "
                "variable names, SQL, terminal commands, or syntax—keep code in standard programming syntax "
                "while providing all explanations and comments in the requested language."
            )

        # Memory injection
        mem_note = ""
        if memories:
            mem_note = (
                "\n\n[User Context & Preferences]:\n" +
                "\n".join(f"- {m}" for m in memories) +
                "\nFollow these preferences whenever relevant."
            )

        return f"{base_prompt}{lang_note}{mem_note}"

    @classmethod
    async def summarize_older_messages(cls, older_messages: List[Message], current_summary: str = "") -> str:
        """Uses Qwen2.5 to generate a 2-3 sentence rolling summary of older conversation history."""
        if not older_messages:
            return current_summary

        history_lines = []
        for m in older_messages:
            history_lines.append(f"{m.role.capitalize()}: {m.content[:300]}")
        history_text = "\n".join(history_lines)

        prompt = (
            "Summarize the key decisions, topics, and facts discussed in this prior conversation snippet in 2 to 3 concise sentences.\n"
            f"Prior Summary: {current_summary}\n\n"
            f"New Snippet:\n{history_text}\n\n"
            "Updated Concise Summary:"
        )

        try:
            summary = await ollama_service.generate(
                prompt=prompt,
                options={"temperature": 0.3, "num_predict": 120}
            )
            return summary.strip()
        except Exception as e:
            logger.error(f"Failed to generate conversation summary: {e}")
            return current_summary

    @classmethod
    async def build_context_messages(
        cls,
        db: Session,
        conversation: Conversation,
        current_user_content: str,
        system_prompt: Optional[str] = None,
        language: str = "en",
        memory_enabled: bool = True,
        tool_observation: Optional[str] = None,
        tool_citations: Optional[List[Dict[str, Any]]] = None,
        recent_window_size: int = 6
    ) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
        """
        Builds an optimized list of messages for Qwen2.5 3B.
        Pattern:
        [System instructions + relevant memories]
        + [Conversation summary (if exists)]
        + [Recent message window (last 4-6 messages)]
        + [Tool observation / RAG snippets (if executed)]
        + [Current user message]
        """
        # 1. Fetch relevant memories if enabled
        memories = []
        if memory_enabled:
            memories = await memory_service.get_relevant_memories(
                db, conversation.user_id, current_user_content, limit=3
            )

        # 2. Base system message
        system_content = cls.get_system_instructions(
            custom_system_prompt=system_prompt or conversation.system_prompt,
            language=language,
            memories=memories
        )

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]

        # 3. Retrieve past messages for this conversation
        all_past_messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.asc())
            .all()
        )

        # 4. Context summarization for older messages
        if len(all_past_messages) > recent_window_size:
            older = all_past_messages[:-recent_window_size]
            recent = all_past_messages[-recent_window_size:]

            # Check if we should update rolling summary
            if not conversation.summary or len(older) % 4 == 0:
                conversation.summary = await cls.summarize_older_messages(older, conversation.summary)
                db.commit()

            if conversation.summary:
                messages.append({
                    "role": "system",
                    "content": f"[Conversation History Summary]: {conversation.summary}"
                })
        else:
            recent = all_past_messages

        # 5. Append recent messages
        for msg in recent:
            messages.append({"role": msg.role, "content": msg.content})

        # 6. Current turn assembly (with tool observation if present)
        final_user_turn = current_user_content
        if tool_observation:
            final_user_turn = (
                f"[Tool / Verified External Data]:\n{tool_observation}\n\n"
                f"[User Query]:\n{current_user_content}\n\n"
                "Please synthesize the final response using the verified external data provided above when relevant. "
                "Clearly distinguish verified information from general reasoning."
            )

        messages.append({"role": "user", "content": final_user_turn})

        return messages, tool_citations or []

context_service = ContextService()
