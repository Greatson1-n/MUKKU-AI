import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Index
)
from sqlalchemy.orm import relationship
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    is_guest = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    title = Column(String(255), default="New Chat")
    summary = Column(Text, default="")
    model_name = Column(String(100), default="qwen2.5:3b")
    system_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id"), index=True, nullable=False)
    role = Column(String(20), nullable=False)  # "user", "assistant", "system", "tool"
    content = Column(Text, nullable=False, default="")
    tool_calls = Column(Text, nullable=True)  # JSON text of tool execution details
    citations = Column(Text, nullable=True)   # JSON text of sources
    token_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    conversation = relationship("Conversation", back_populates="messages")

class Memory(Base):
    __tablename__ = "memories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    category = Column(String(50), default="preference")  # "preference", "project", "fact"
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="memories")

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    mime_type = Column(String(100), default="text/plain")
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id"), index=True, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, default=1)
    content = Column(Text, nullable=False)
    embedding = Column(Text, nullable=True)  # JSON string representation of float list
    created_at = Column(DateTime, default=utcnow)

    document = relationship("Document", back_populates="chunks")

class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)
    key = Column(String(100), index=True, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
