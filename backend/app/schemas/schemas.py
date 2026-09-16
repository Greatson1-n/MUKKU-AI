from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# User & Auth
class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=4)

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    is_guest: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# Messages
class MessageBase(BaseModel):
    role: str
    content: str
    tool_calls: Optional[str] = None
    citations: Optional[str] = None

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: str
    conversation_id: str
    token_count: int
    created_at: datetime

    class Config:
        from_attributes = True

# Conversations
class ConversationCreate(BaseModel):
    title: Optional[str] = "New Chat"
    model_name: Optional[str] = None
    system_prompt: Optional[str] = None

class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    system_prompt: Optional[str] = None

class ConversationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    summary: Optional[str] = ""
    model_name: str
    system_prompt: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = 0

    class Config:
        from_attributes = True

class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageResponse] = []

# Chat Streaming Request
class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    content: str = Field(..., min_length=1)
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    top_k: Optional[int] = 40
    repeat_penalty: Optional[float] = 1.1
    max_tokens: Optional[int] = 1500
    system_prompt: Optional[str] = None
    web_search: bool = False
    memory_enabled: bool = True
    document_ids: Optional[List[str]] = None
    language: Optional[str] = "en"
    image_base64: Optional[str] = None

# Edit / Regenerate
class EditMessageRequest(BaseModel):
    message_id: str
    content: str

class RegenerateRequest(BaseModel):
    conversation_id: str
    message_id: Optional[str] = None

# Memory
class MemoryCreate(BaseModel):
    category: Optional[str] = "preference"
    content: str = Field(..., min_length=1)

class MemoryUpdate(BaseModel):
    category: Optional[str] = None
    content: Optional[str] = None
    is_active: Optional[bool] = None

class MemoryResponse(BaseModel):
    id: str
    category: str
    content: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Documents
class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    mime_type: str
    chunk_count: int
    created_at: datetime

    class Config:
        from_attributes = True

class DocumentChunkCitation(BaseModel):
    document_name: str
    page_number: int
    chunk_index: int
    snippet: str
    score: float

# Ollama Health & Models
class OllamaModelItem(BaseModel):
    name: str
    size: Optional[int] = None
    modified_at: Optional[str] = None

class OllamaStatusResponse(BaseModel):
    is_online: bool
    ollama_host: str
    configured_model: str
    model_installed: bool
    embedding_model: str
    embedding_model_installed: bool
    vision_model: str
    vision_model_installed: bool
    available_models: List[OllamaModelItem] = []
    error: Optional[str] = None
    provider: Optional[str] = None

    class Config:
        extra = "ignore"

# App Settings
class SettingsUpdate(BaseModel):
    ollama_model: Optional[str] = None
    temperature: Optional[float] = None
    system_prompt: Optional[str] = None
    language: Optional[str] = None
    response_style: Optional[str] = None
    web_search_enabled: Optional[bool] = None
    memory_enabled: Optional[bool] = None
    theme: Optional[str] = None
