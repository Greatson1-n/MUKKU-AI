import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, text

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.models import User, Conversation, Message
from app.schemas.schemas import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationDetailResponse,
    ConversationExport,
    MessageCreate,
    MessageResponse,
    MessageListResponse
)

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])
messages_router = APIRouter(prefix="/api/messages", tags=["Messages"])

def utcnow():
    return datetime.now(timezone.utc)

@router.get("", response_model=List[ConversationResponse])
def list_conversations(
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List conversations for the authenticated user, sorted by updated_at descending."""
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)
    if search:
        query = query.filter(Conversation.title.ilike(f"%{search}%"))
    conversations = query.order_by(desc(Conversation.updated_at)).offset(offset).limit(limit).all()

    result = []
    for conv in conversations:
        msg_count = db.query(Message).filter(Message.conversation_id == conv.id).count()
        item = ConversationResponse.model_validate(conv)
        item.message_count = msg_count
        result.append(item)
    return result

@router.post("", response_model=ConversationResponse)
def create_conversation(
    req: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new conversation, supporting client-generated UUID for offline sync."""
    conv_id = req.id if req.id else str(uuid.uuid4())
    
    # Idempotency check: if conversation already exists for this user, return it
    existing = db.query(Conversation).filter(
        Conversation.id == conv_id,
        Conversation.user_id == current_user.id
    ).first()
    if existing:
        res = ConversationResponse.model_validate(existing)
        res.message_count = db.query(Message).filter(Message.conversation_id == existing.id).count()
        return res

    conv = Conversation(
        id=conv_id,
        user_id=current_user.id,
        title=req.title or "New Chat",
        model_name=req.model_name or "qwen2.5:3b",
        system_prompt=req.system_prompt,
        created_at=utcnow(),
        updated_at=utcnow()
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    res = ConversationResponse.model_validate(conv)
    res.message_count = 0
    return res

@router.get("/search")
def search_conversations(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Server-side full search across both conversation titles and message content."""
    query_str = f"%{q.strip()}%"
    
    # 1. Match by conversation title
    title_matches = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id, Conversation.title.ilike(query_str))
        .order_by(desc(Conversation.updated_at))
        .limit(limit)
        .all()
    )
    
    matched_conv_ids = {c.id for c in title_matches}
    results = []
    
    for c in title_matches:
        results.append({
            "id": c.id,
            "conversation_id": c.id,
            "title": c.title,
            "match_type": "title",
            "snippet": c.title,
            "updated_at": c.updated_at.isoformat()
        })

    # 2. Match by message content
    msg_matches = (
        db.query(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == current_user.id, Message.content.ilike(query_str))
        .order_by(desc(Message.created_at))
        .limit(limit * 2)
        .all()
    )

    for m in msg_matches:
        if m.conversation_id not in matched_conv_ids:
            matched_conv_ids.add(m.conversation_id)
            conv = db.query(Conversation).filter(Conversation.id == m.conversation_id).first()
            if conv:
                idx = m.content.lower().find(q.lower())
                start = max(0, idx - 40)
                end = min(len(m.content), idx + len(q) + 40)
                snippet = ("..." if start > 0 else "") + m.content[start:end] + ("..." if end < len(m.content) else "")
                
                results.append({
                    "id": conv.id,
                    "conversation_id": conv.id,
                    "title": conv.title,
                    "match_type": "content",
                    "snippet": snippet,
                    "updated_at": conv.updated_at.isoformat()
                })
        if len(results) >= limit:
            break

    return {"query": q, "results": results}

@router.get("/export")
def export_all_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export all conversations and messages for the user as a JSON structure."""
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(desc(Conversation.created_at))
        .all()
    )

    exported = []
    for conv in conversations:
        messages = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(Message.created_at.asc())
            .all()
        )
        exported.append({
            "conversation_id": conv.id,
            "title": conv.title,
            "summary": conv.summary or "",
            "model_name": conv.model_name,
            "system_prompt": conv.system_prompt,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "status": m.status or "completed",
                    "model": m.model,
                    "tool_calls": m.tool_calls,
                    "citations": m.citations,
                    "created_at": m.created_at.isoformat(),
                    "updated_at": m.updated_at.isoformat() if m.updated_at else None
                }
                for m in messages
            ]
        })

    return {"version": "1.0", "exported_at": utcnow().isoformat(), "conversations": exported}

@router.post("/import")
def import_conversations(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Import previously exported conversations with duplicate ID prevention and transactions."""
    conv_list = payload.get("conversations", [])
    if not isinstance(conv_list, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid import format")

    imported_count = 0
    message_count = 0

    try:
        for item in conv_list:
            orig_id = item.get("conversation_id")
            title = item.get("title", "Imported Chat")
            model_name = item.get("model_name", "qwen2.5:3b")
            system_prompt = item.get("system_prompt")
            messages = item.get("messages", [])

            # Generate new UUID if original ID already belongs to any user
            target_id = str(uuid.uuid4())
            if orig_id:
                existing_conv = db.query(Conversation).filter(Conversation.id == orig_id).first()
                if not existing_conv:
                    target_id = orig_id

            new_conv = Conversation(
                id=target_id,
                user_id=current_user.id,
                title=title,
                model_name=model_name,
                system_prompt=system_prompt,
                created_at=utcnow(),
                updated_at=utcnow()
            )
            db.add(new_conv)

            for m in messages:
                msg_id = str(uuid.uuid4())
                orig_m_id = m.get("id")
                if orig_m_id:
                    existing_msg = db.query(Message).filter(Message.id == orig_m_id).first()
                    if not existing_msg:
                        msg_id = orig_m_id

                new_msg = Message(
                    id=msg_id,
                    conversation_id=target_id,
                    role=m.get("role", "user"),
                    content=m.get("content", ""),
                    status=m.get("status", "completed"),
                    model=m.get("model"),
                    tool_calls=m.get("tool_calls"),
                    citations=m.get("citations"),
                    created_at=utcnow(),
                    updated_at=utcnow()
                )
                db.add(new_msg)
                message_count += 1

            imported_count += 1

        db.commit()
        return {
            "status": "success",
            "imported_conversations": imported_count,
            "imported_messages": message_count
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )

@router.delete("")
def delete_all_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete all conversations belonging to the authenticated user in an atomic transaction."""
    try:
        user_convs = db.query(Conversation).filter(Conversation.user_id == current_user.id).all()
        count = len(user_convs)
        for conv in user_convs:
            db.delete(conv)
        db.commit()
        return {"status": "success", "message": "All conversations deleted successfully", "deleted_count": count}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete conversations: {str(e)}"
        )

@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get single conversation metadata and recent messages."""
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
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

    res = ConversationDetailResponse.model_validate(conv)
    res.messages = [MessageResponse.model_validate(m) for m in messages]
    res.message_count = len(messages)
    return res

@router.get("/{conversation_id}/export")
def export_single_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export single conversation as JSON."""
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
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

    return {
        "conversation_id": conv.id,
        "title": conv.title,
        "summary": conv.summary or "",
        "model_name": conv.model_name,
        "system_prompt": conv.system_prompt,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "status": m.status or "completed",
                "model": m.model,
                "tool_calls": m.tool_calls,
                "citations": m.citations,
                "created_at": m.created_at.isoformat(),
                "updated_at": m.updated_at.isoformat() if m.updated_at else None
            }
            for m in messages
        ]
    }

@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: str,
    req: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if req.title is not None:
        conv.title = req.title.strip() or "Untitled Chat"
    if req.system_prompt is not None:
        conv.system_prompt = req.system_prompt.strip()
    if req.model_name is not None:
        conv.model_name = req.model_name.strip()

    conv.updated_at = utcnow()
    db.commit()
    db.refresh(conv)
    return ConversationResponse.model_validate(conv)

@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    db.delete(conv)
    db.commit()
    return {"status": "success", "message": "Conversation deleted"}

@router.post("/{conversation_id}/clear")
def clear_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    db.query(Message).filter(Message.conversation_id == conv.id).delete()
    conv.summary = ""
    conv.updated_at = utcnow()
    db.commit()
    return {"status": "success", "message": "Conversation cleared"}

# ==============================================================================
# Paginated Messages API
# ==============================================================================

@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=100),
    before: Optional[str] = Query(None, description="Message ID cursor to load older messages"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cursor-based pagination for messages in a conversation."""
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    query = db.query(Message).filter(Message.conversation_id == conv.id)
    total_count = query.count()

    if before:
        pivot = db.query(Message).filter(Message.id == before, Message.conversation_id == conv.id).first()
        if pivot:
            query = query.filter(Message.created_at < pivot.created_at)

    recent_slice = query.order_by(desc(Message.created_at)).limit(limit + 1).all()
    has_more = len(recent_slice) > limit
    messages_to_return = recent_slice[:limit]
    messages_to_return.reverse()

    next_cursor = messages_to_return[0].id if has_more and messages_to_return else None

    return MessageListResponse(
        messages=[MessageResponse.model_validate(m) for m in messages_to_return],
        has_more=has_more,
        total_count=total_count,
        next_cursor=next_cursor
    )

@router.post("/{conversation_id}/messages", response_model=MessageResponse)
def create_message(
    conversation_id: str,
    req: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Immediately persists a user or assistant message, supporting client-generated UUID."""
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg_id = req.id if req.id else str(uuid.uuid4())
    
    existing = db.query(Message).filter(
        Message.id == msg_id,
        Message.conversation_id == conv.id
    ).first()
    if existing:
        existing.content = req.content
        if req.status:
            existing.status = req.status
        existing.updated_at = utcnow()
        conv.updated_at = utcnow()
        db.commit()
        db.refresh(existing)
        return MessageResponse.model_validate(existing)

    msg = Message(
        id=msg_id,
        conversation_id=conv.id,
        role=req.role,
        content=req.content,
        status=req.status or "completed",
        model=req.model,
        created_at=req.created_at or utcnow(),
        updated_at=utcnow()
    )
    db.add(msg)
    conv.updated_at = utcnow()
    db.commit()
    db.refresh(msg)
    return MessageResponse.model_validate(msg)

@messages_router.delete("/{message_id}")
def delete_message(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a single message by ID, verifying conversation ownership."""
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    conv = db.query(Conversation).filter(
        Conversation.id == msg.conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    db.delete(msg)
    conv.updated_at = utcnow()
    db.commit()
    return {"status": "success", "message": "Message deleted"}

@router.delete("/{conversation_id}/messages/{message_id}")
def delete_conversation_message(
    conversation_id: str,
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return delete_message(message_id, db, current_user)
