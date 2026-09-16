import os
import uuid
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.models import User, Document, DocumentChunk
from app.schemas.schemas import DocumentResponse, DocumentChunkCitation
from app.services.rag_service import rag_service

router = APIRouter(prefix="/api/documents", tags=["Documents & RAG"])

@router.get("", response_model=List[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    docs = db.query(Document).filter(Document.user_id == current_user.id).order_by(Document.created_at.desc()).all()
    return [DocumentResponse.model_validate(d) for d in docs]

@router.post("", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    filename = file.filename
    ext = Path(filename).suffix.lower()

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    # Safe local storage
    file_id = str(uuid.uuid4())
    save_name = f"{file_id}_{filename}"
    file_path = settings.UPLOAD_DIR / save_name

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = os.path.getsize(file_path)
    if file_size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    doc = Document(
        id=file_id,
        user_id=current_user.id,
        filename=filename,
        file_path=str(file_path),
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Chunk and embed via RAG service
    await rag_service.process_document(db, doc)
    db.refresh(doc)

    return DocumentResponse.model_validate(doc)

@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Remove file on disk
    try:
        Path(doc.file_path).unlink(missing_ok=True)
    except Exception:
        pass

    db.delete(doc)
    db.commit()
    return {"status": "success", "message": "Document deleted"}

@router.post("/search", response_model=List[DocumentChunkCitation])
async def search_documents(
    query: str = Form(...),
    document_ids: Optional[List[str]] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    chunks = await rag_service.search_relevant_chunks(db, query, current_user.id, document_ids=document_ids, top_k=5)
    return [
        DocumentChunkCitation(
            document_name=c["document_name"],
            page_number=c["page_number"],
            chunk_index=c["chunk_index"],
            snippet=c["content"],
            score=c["score"]
        )
        for c in chunks
    ]
