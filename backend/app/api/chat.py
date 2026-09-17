import json
import uuid
import time
import logging
from typing import AsyncGenerator
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, SessionLocal
from app.api.auth import get_current_user
from app.models.models import User, Conversation, Message, Document
from app.schemas.schemas import ChatRequest, EditMessageRequest, RegenerateRequest
from app.services.ollama_service import ollama_service
from app.services.tool_service import tool_service
from app.services.context_service import context_service, estimate_tokens
from app.services.memory_service import memory_service
from app.services.vision_service import vision_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

def utcnow():
    return datetime.now(timezone.utc)

def generate_local_title(content: str) -> str:
    """Fast, deterministic zero-latency title generation from user prompt."""
    clean = content.strip().replace("\n", " ")
    prefixes = [
        "can you explain", "explain to me", "please explain", "explain how", "explain",
        "how does", "how do", "how can i", "how to", "what is the", "what is", "what are",
        "write a python", "write a code", "write a", "can you write", "help me write",
        "tell me about", "give me an overview of", "summarize", "help me with"
    ]
    lower = clean.lower()
    for p in prefixes:
        if lower.startswith(p):
            clean = clean[len(p):].strip(" ?:.,!-")
            break
    clean = clean.strip(" ?:.,!-\"'")
    words = clean.split()
    if not words:
        return "New Chat"
    title = " ".join(words[:6]).title()
    return title[:45].strip() or "New Chat"

async def sse_chat_generator(
    user_id: str,
    req: ChatRequest,
    existing_user_message: Message = None
) -> AsyncGenerator[str, None]:
    """Generates Server-Sent Events (SSE) stream for chat interactions with persistent crash-recovery."""
    db: Session = SessionLocal()
    assistant_msg = None
    full_response_chunks = []
    
    try:
        # 1. Get or create conversation
        conv = None
        is_new_conv = False
        if req.conversation_id:
            conv = db.query(Conversation).filter(
                Conversation.id == req.conversation_id,
                Conversation.user_id == user_id
            ).first()

        if not conv:
            is_new_conv = True
            default_model = settings.GROQ_MODEL if settings.LLM_PROVIDER.lower() == "groq" else settings.OLLAMA_MODEL
            conv_id = req.conversation_id if req.conversation_id else str(uuid.uuid4())
            conv = Conversation(
                id=conv_id,
                user_id=user_id,
                title="New Chat",
                model_name=req.model or default_model,
                system_prompt=req.system_prompt,
                created_at=utcnow(),
                updated_at=utcnow()
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)

        yield f"data: {json.dumps({'event': 'conversation', 'conversation_id': conv.id})}\n\n"

        # 2. Save user message immediately if not already existing
        user_msg = existing_user_message
        if not user_msg:
            if req.message_id:
                user_msg = db.query(Message).filter(
                    Message.id == req.message_id,
                    Message.conversation_id == conv.id
                ).first()
            if not user_msg:
                user_msg = Message(
                    id=req.message_id or str(uuid.uuid4()),
                    conversation_id=conv.id,
                    role="user",
                    content=req.content,
                    status="completed",
                    token_count=estimate_tokens(req.content),
                    created_at=utcnow(),
                    updated_at=utcnow()
                )
                db.add(user_msg)
                conv.updated_at = utcnow()
                db.commit()
                db.refresh(user_msg)

        yield f"data: {json.dumps({'event': 'user_message_saved', 'message_id': user_msg.id})}\n\n"

        effective_content = req.content

        # 3. Vision Processing (if image attached)
        if req.image_base64:
            yield f"data: {json.dumps({'event': 'tool_start', 'tool': 'vision', 'status': 'Analyzing image with vision model...'})}\n\n"
            img_desc = await vision_service.describe_image(req.image_base64)
            yield f"data: {json.dumps({'event': 'tool_end', 'tool': 'vision'})}\n\n"
            effective_content = f"[Attached Image Visual Description]:\n{img_desc}\n\n[User Message]:\n{req.content}"

        # 4. Tool Decision & Execution
        has_docs = db.query(Document).filter(Document.user_id == user_id).count() > 0
        tool_decision = await tool_service.decide_tool(
            effective_content,
            web_search_enabled=req.web_search,
            has_documents=has_docs
        )

        tool_observation = None
        tool_citations = None
        tool_metadata = None

        if tool_decision and tool_decision.get("tool") != "none":
            tool_name = tool_decision["tool"]
            tool_args = tool_decision.get("args", {})

            initial_status = f"Executing {tool_name}..."
            yield f"data: {json.dumps({'event': 'tool_start', 'tool': tool_name, 'status': initial_status})}\n\n"

            obs, status_label, citations = await tool_service.execute_tool(
                tool_name, tool_args, db, user_id, document_ids=req.document_ids
            )
            tool_observation = obs
            tool_citations = citations
            tool_metadata = {"tool": tool_name, "args": tool_args, "status": status_label}

            yield f"data: {json.dumps({'event': 'tool_end', 'tool': tool_name, 'status': status_label})}\n\n"

            if citations:
                yield f"data: {json.dumps({'event': 'citations', 'citations': citations})}\n\n"

        # 5. Build intelligent context
        messages, _ = await context_service.build_context_messages(
            db=db,
            conversation=conv,
            current_user_content=effective_content,
            system_prompt=req.system_prompt,
            language=req.language or "en",
            memory_enabled=req.memory_enabled,
            tool_observation=tool_observation,
            tool_citations=tool_citations,
            recent_window_size=settings.RECENT_MESSAGES_COUNT
        )

        # 6. Initialize assistant message in DB upfront with status='streaming'
        default_model = settings.GROQ_MODEL if settings.LLM_PROVIDER.lower() == "groq" else settings.OLLAMA_MODEL
        target_model = req.model or conv.model_name or default_model

        assistant_msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            role="assistant",
            content="",
            status="streaming",
            model=target_model,
            tool_calls=json.dumps(tool_metadata) if tool_metadata else None,
            citations=json.dumps(tool_citations) if tool_citations else None,
            token_count=0,
            created_at=utcnow(),
            updated_at=utcnow()
        )
        db.add(assistant_msg)
        conv.model_name = target_model
        conv.updated_at = utcnow()
        db.commit()
        db.refresh(assistant_msg)

        yield f"data: {json.dumps({'event': 'assistant_started', 'message_id': assistant_msg.id})}\n\n"

        # 7. Stream tokens from Ollama with periodic DB check-pointing
        model_options = {
            "temperature": req.temperature if req.temperature is not None else 0.7,
            "top_p": req.top_p if req.top_p is not None else 0.9,
            "top_k": req.top_k if req.top_k is not None else 40,
            "repeat_penalty": req.repeat_penalty if req.repeat_penalty is not None else 1.1,
            "num_predict": req.max_tokens if req.max_tokens is not None else 1500
        }

        last_flush_time = time.time()
        tokens_since_flush = 0

        async for token in ollama_service.chat_stream(
            messages=messages,
            model=target_model,
            options=model_options
        ):
            full_response_chunks.append(token)
            tokens_since_flush += 1
            yield f"data: {json.dumps({'event': 'token', 'content': token})}\n\n"

            now = time.time()
            if now - last_flush_time >= 2.0 or tokens_since_flush >= 30:
                try:
                    assistant_msg.content = "".join(full_response_chunks)
                    assistant_msg.updated_at = utcnow()
                    db.commit()
                    last_flush_time = now
                    tokens_since_flush = 0
                except Exception as fe:
                    logger.debug(f"Checkpoint flush notice: {fe}")

        full_assistant_content = "".join(full_response_chunks).strip()

        # 8. Mark assistant message as completed
        assistant_msg.content = full_assistant_content
        assistant_msg.status = "completed"
        assistant_msg.tool_calls = json.dumps(tool_metadata) if tool_metadata else None
        assistant_msg.citations = json.dumps(tool_citations) if tool_citations else None
        assistant_msg.token_count = estimate_tokens(full_assistant_content)
        assistant_msg.updated_at = utcnow()
        conv.updated_at = utcnow()
        db.commit()

        # 9. Smart Title generation for new chats
        if is_new_conv or conv.title == "New Chat":
            clean_title = generate_local_title(req.content)
            if clean_title and clean_title != conv.title:
                conv.title = clean_title
                conv.updated_at = utcnow()
                db.commit()
                yield f"data: {json.dumps({'event': 'title_updated', 'title': clean_title})}\n\n"

        # 10. Memory auto-extraction
        if req.memory_enabled:
            try:
                await memory_service.auto_extract_memory(db, user_id, req.content)
            except Exception as e:
                logger.debug(f"Memory extraction skipped: {e}")

        # Final done event
        yield f"data: {json.dumps({'event': 'done', 'message_id': assistant_msg.id, 'status': 'completed'})}\n\n"

    except Exception as e:
        logger.error(f"SSE Chat generator error: {e}", exc_info=True)
        if assistant_msg:
            try:
                assistant_msg.status = "error"
                if full_response_chunks:
                    assistant_msg.content = "".join(full_response_chunks).strip()
                assistant_msg.updated_at = utcnow()
                db.commit()
            except Exception:
                pass
        yield f"data: {json.dumps({'event': 'error', 'message': f'Server error: {str(e)}'})}\n\n"
    finally:
        try:
            if assistant_msg:
                # If stream disconnected or was aborted while streaming, mark cancelled
                refreshed_msg = db.query(Message).filter(Message.id == assistant_msg.id).first()
                if refreshed_msg and refreshed_msg.status == "streaming":
                    refreshed_msg.status = "cancelled"
                    if full_response_chunks:
                        refreshed_msg.content = "".join(full_response_chunks).strip()
                    refreshed_msg.updated_at = utcnow()
                    db.commit()
        except Exception as clex:
            logger.debug(f"Stream exit cleanup notice: {clex}")
        finally:
            db.close()

@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """Initiates an SSE streaming chat turn."""
    return StreamingResponse(
        sse_chat_generator(current_user.id, req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/regenerate")
async def regenerate(
    req: RegenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Regenerates response for the latest or designated user message."""
    conv = db.query(Conversation).filter(
        Conversation.id == req.conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    if not messages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conversation has no messages")

    # If target message specified, find it, else find last user message
    target_user_msg = None
    if req.message_id:
        for i, m in enumerate(messages):
            if m.id == req.message_id and m.role == "user":
                target_user_msg = m
                for sub in messages[i+1:]:
                    db.delete(sub)
                db.commit()
                break
    else:
        # Delete last assistant message if exists, then find last user message
        if messages[-1].role == "assistant":
            db.delete(messages[-1])
            db.commit()
            messages = messages[:-1]
        if messages and messages[-1].role == "user":
            target_user_msg = messages[-1]

    if not target_user_msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No user message found to regenerate")

    chat_req = ChatRequest(
        conversation_id=conv.id,
        content=target_user_msg.content,
        model=conv.model_name
    )

    return StreamingResponse(
        sse_chat_generator(current_user.id, chat_req, existing_user_message=target_user_msg),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )

@router.post("/edit")
async def edit_message(
    req: EditMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Edits a previous user message, discards subsequent turns, and branches new response."""
    msg = db.query(Message).filter(Message.id == req.message_id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    conv = db.query(Conversation).filter(
        Conversation.id == msg.conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    msg.content = req.content
    msg.token_count = estimate_tokens(req.content)
    msg.updated_at = utcnow()

    all_msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    found_idx = -1
    for i, m in enumerate(all_msgs):
        if m.id == msg.id:
            found_idx = i
            break

    if found_idx != -1 and found_idx < len(all_msgs) - 1:
        for to_del in all_msgs[found_idx+1:]:
            db.delete(to_del)
    db.commit()

    chat_req = ChatRequest(
        conversation_id=conv.id,
        content=req.content,
        model=conv.model_name
    )

    return StreamingResponse(
        sse_chat_generator(current_user.id, chat_req, existing_user_message=msg),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )
