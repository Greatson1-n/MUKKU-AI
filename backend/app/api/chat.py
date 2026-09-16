import json
import uuid
import logging
from typing import AsyncGenerator
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

async def sse_chat_generator(
    user_id: str,
    req: ChatRequest,
    existing_user_message: Message = None
) -> AsyncGenerator[str, None]:
    """Generates Server-Sent Events (SSE) stream for chat interactions."""
    db: Session = SessionLocal()
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
            conv = Conversation(
                id=str(uuid.uuid4()),
                user_id=user_id,
                title="New Chat",
                model_name=req.model or settings.OLLAMA_MODEL,
                system_prompt=req.system_prompt
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)

        yield f"data: {json.dumps({'event': 'conversation', 'conversation_id': conv.id})}\n\n"

        # 2. Save user message if not already existing (from edit/regenerate)
        user_msg = existing_user_message
        if not user_msg:
            user_msg = Message(
                conversation_id=conv.id,
                role="user",
                content=req.content,
                token_count=estimate_tokens(req.content)
            )
            db.add(user_msg)
            db.commit()
            db.refresh(user_msg)

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

            # Notify frontend that tool has started
            initial_status = f"Executing {tool_name}..."
            yield f"data: {json.dumps({'event': 'tool_start', 'tool': tool_name, 'status': initial_status})}\n\n"

            obs, status_label, citations = await tool_service.execute_tool(
                tool_name, tool_args, db, user_id, document_ids=req.document_ids
            )
            tool_observation = obs
            tool_citations = citations
            tool_metadata = {"tool": tool_name, "args": tool_args, "status": status_label}

            # Update status / finish tool
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

        # 6. Stream tokens from Ollama
        model_options = {
            "temperature": req.temperature if req.temperature is not None else 0.7,
            "top_p": req.top_p if req.top_p is not None else 0.9,
            "top_k": req.top_k if req.top_k is not None else 40,
            "repeat_penalty": req.repeat_penalty if req.repeat_penalty is not None else 1.1,
            "num_predict": req.max_tokens if req.max_tokens is not None else 1500
        }

        full_response_chunks = []
        async for token in ollama_service.chat_stream(
            messages=messages,
            model=req.model or conv.model_name or settings.OLLAMA_MODEL,
            options=model_options
        ):
            full_response_chunks.append(token)
            yield f"data: {json.dumps({'event': 'token', 'content': token})}\n\n"

        full_assistant_content = "".join(full_response_chunks).strip()

        # 7. Persist assistant message in DB
        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=full_assistant_content,
            tool_calls=json.dumps(tool_metadata) if tool_metadata else None,
            citations=json.dumps(tool_citations) if tool_citations else None,
            token_count=estimate_tokens(full_assistant_content)
        )
        db.add(assistant_msg)
        conv.model_name = req.model or conv.model_name or settings.OLLAMA_MODEL
        db.commit()
        db.refresh(assistant_msg)

        # 8. Title generation for new chats
        if is_new_conv or conv.title == "New Chat":
            title_prompt = (
                f"Generate a very short 3 to 5 word title summarizing this message: \"{req.content[:150]}\". "
                "Do not use quotes, punctuation, or 'Title:' prefix."
            )
            try:
                new_title = await ollama_service.generate(
                    prompt=title_prompt,
                    options={"temperature": 0.4, "num_predict": 15}
                )
                clean_title = new_title.strip().strip('"').strip("'")
                if clean_title and len(clean_title) <= 60:
                    conv.title = clean_title
                    db.commit()
                    yield f"data: {json.dumps({'event': 'title_updated', 'title': clean_title})}\n\n"
            except Exception as e:
                logger.debug(f"Title generation error: {e}")

        # 9. Trigger background memory extraction if enabled
        if req.memory_enabled:
            try:
                await memory_service.auto_extract_memory(db, user_id, req.content)
            except Exception as e:
                logger.debug(f"Memory extraction skipped: {e}")

        # Final done event
        yield f"data: {json.dumps({'event': 'done', 'message_id': assistant_msg.id})}\n\n"

    except Exception as e:
        logger.error(f"SSE Chat generator error: {e}", exc_info=True)
        yield f"data: {json.dumps({'event': 'error', 'message': f'Server error: {str(e)}'})}\n\n"
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
                # Delete following messages
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

    # Update content
    msg.content = req.content
    msg.token_count = estimate_tokens(req.content)

    # Delete all messages after this one
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
