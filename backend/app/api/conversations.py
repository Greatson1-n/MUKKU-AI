from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.models import User, Conversation, Message
from app.schemas.schemas import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationDetailResponse,
    MessageResponse
)

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])

@router.get("", response_model=List[ConversationResponse])
def list_conversations(
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
    conv = Conversation(
        user_id=current_user.id,
        title=req.title or "New Chat",
        model_name=req.model_name or "qwen2.5:3b",
        system_prompt=req.system_prompt
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    res = ConversationResponse.model_validate(conv)
    res.message_count = 0
    return res

@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
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
    db.commit()
    return {"status": "success", "message": "Conversation cleared"}
