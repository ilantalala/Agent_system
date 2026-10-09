from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Literal


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    role: str
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str
class ReviewItem(BaseModel):
    passed: bool
    note: str

class DraftReview(BaseModel):
    role_clarity: ReviewItem
    tasks: ReviewItem
    tone: ReviewItem
    edge_cases: ReviewItem
    examples: ReviewItem

class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    owner_id: int
    created_at: datetime
    draft_system_prompt: str | None = None
    draft_review: DraftReview | None = None


class ChatMessage(BaseModel):
    role: Literal["user","assistant"]
    content: str

class ArchitectChatRequest(BaseModel):
    content: str

class ArchitectChatResponse(BaseModel):
    message: ChatMessage
    draft_system_prompt: str | None = None
    draft_review: DraftReview | None = None

class TestChatRequest(BaseModel):
    content: str

class TestChatResponse(BaseModel):
    message: ChatMessage
