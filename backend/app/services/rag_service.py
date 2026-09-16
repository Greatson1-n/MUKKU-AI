import os
import csv
import json
import math
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from pypdf import PdfReader
import docx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Document, DocumentChunk
from app.services.ollama_service import ollama_service

logger = logging.getLogger(__name__)

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculates cosine similarity between two numeric vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return dot / (mag1 * mag2)

class RAGService:
    @staticmethod
    def extract_text_from_file(file_path: Path, mime_type: str) -> List[Tuple[int, str]]:
        """
        Extracts text from file.
        Returns a list of tuples: (page_number, text_content).
        """
        results: List[Tuple[int, str]] = []
        ext = file_path.suffix.lower()

        if ext == ".pdf":
            try:
                reader = PdfReader(str(file_path))
                for i, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    if text.strip():
                        results.append((i + 1, text.strip()))
            except Exception as e:
                logger.error(f"Error reading PDF {file_path}: {e}")

        elif ext == ".docx":
            try:
                doc = docx.Document(str(file_path))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                full_text = "\n\n".join(paragraphs)
                if full_text.strip():
                    results.append((1, full_text.strip()))
            except Exception as e:
                logger.error(f"Error reading DOCX {file_path}: {e}")

        elif ext == ".csv":
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.reader(f)
                    rows = [", ".join(row) for row in reader if any(row)]
                    full_text = "\n".join(rows)
                    if full_text.strip():
                        results.append((1, full_text.strip()))
            except Exception as e:
                logger.error(f"Error reading CSV {file_path}: {e}")

        else: # txt, md, json, etc.
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    full_text = f.read()
                    if full_text.strip():
                        results.append((1, full_text.strip()))
            except Exception as e:
                logger.error(f"Error reading text file {file_path}: {e}")

        return results

    @staticmethod
    def chunk_text(page_texts: List[Tuple[int, str]], chunk_size: int = 500, overlap: int = 80) -> List[Dict[str, Any]]:
        """Splits page texts into overlapping chunks."""
        chunks = []
        chunk_idx = 0

        for page_num, text in page_texts:
            text = text.strip()
            if not text:
                continue

            # Split into chunks
            start = 0
            while start < len(text):
                end = start + chunk_size
                chunk_str = text[start:end]
                # Break on word boundary if possible
                if end < len(text):
                    last_space = chunk_str.rfind(" ")
                    if last_space > chunk_size // 2:
                        chunk_str = chunk_str[:last_space]
                        end = start + last_space

                chunk_str = chunk_str.strip()
                if chunk_str:
                    chunks.append({
                        "chunk_index": chunk_idx,
                        "page_number": page_num,
                        "content": chunk_str
                    })
                    chunk_idx += 1

                start += max(1, len(chunk_str) - overlap)

        return chunks

    @classmethod
    async def process_document(cls, db: Session, doc: Document) -> int:
        """Extracts text, generates chunks and embeddings, and saves to database."""
        file_path = Path(doc.file_path)
        if not file_path.exists():
            return 0

        page_texts = cls.extract_text_from_file(file_path, doc.mime_type)
        raw_chunks = cls.chunk_text(page_texts)

        if not raw_chunks:
            return 0

        chunk_texts = [c["content"] for c in raw_chunks]
        embeddings = await ollama_service.embed(chunk_texts)

        for i, c in enumerate(raw_chunks):
            emb = embeddings[i] if i < len(embeddings) else []
            chunk_record = DocumentChunk(
                document_id=doc.id,
                chunk_index=c["chunk_index"],
                page_number=c["page_number"],
                content=c["content"],
                embedding=json.dumps(emb) if emb else None
            )
            db.add(chunk_record)

        doc.chunk_count = len(raw_chunks)
        db.commit()
        return len(raw_chunks)

    @classmethod
    async def search_relevant_chunks(
        cls,
        db: Session,
        query: str,
        user_id: str,
        document_ids: List[str] = None,
        top_k: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Embeds query and computes similarity against chunks.
        Returns top_k most relevant chunks with metadata.
        """
        query_emb_list = await ollama_service.embed([query])
        if not query_emb_list or not query_emb_list[0]:
            return []
        query_emb = query_emb_list[0]

        # Fetch candidate chunks from DB
        q = db.query(DocumentChunk, Document.filename).join(Document, DocumentChunk.document_id == Document.id)
        q = q.filter(Document.user_id == user_id)
        if document_ids:
            q = q.filter(Document.id.in_(document_ids))

        rows = q.all()
        scored_chunks = []

        for chunk, filename in rows:
            if not chunk.embedding:
                continue
            try:
                emb = json.loads(chunk.embedding)
                score = cosine_similarity(query_emb, emb)
                if score > 0.25: # minimum relevance threshold
                    scored_chunks.append({
                        "document_id": chunk.document_id,
                        "document_name": filename,
                        "page_number": chunk.page_number,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "score": round(score, 4)
                    })
            except Exception:
                continue

        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        return scored_chunks[:top_k]

rag_service = RAGService()
