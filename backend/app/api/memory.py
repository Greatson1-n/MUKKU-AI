from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.models import User
from app.schemas.schemas import MemoryCreate, MemoryUpdate, MemoryResponse
from app.services.memory_service import memory_service

router = APIRouter(prefix="/api/memory", tags=["Memory"])

@router.get("", response_model=List[MemoryResponse])
def get_memories(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    memories = memory_service.get_user_memories(db, current_user.id, active_only=active_only)
    return [MemoryResponse.model_validate(m) for m in memories]

@router.post("", response_model=MemoryResponse)
def add_memory(
    req: MemoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    mem = memory_service.add_memory(db, current_user.id, req.content, req.category or "preference")
    return MemoryResponse.model_validate(mem)

@router.patch("/{memory_id}", response_model=MemoryResponse)
def update_memory(
    memory_id: str,
    req: MemoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    mem = memory_service.update_memory(
        db, memory_id, current_user.id,
        content=req.content,
        is_active=req.is_active,
        category=req.category
    )
    if not mem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory item not found")
    return MemoryResponse.model_validate(mem)

@router.delete("/{memory_id}")
def delete_memory(
    memory_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success = memory_service.delete_memory(db, memory_id, current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory item not found")
    return {"status": "success", "message": "Memory deleted"}
