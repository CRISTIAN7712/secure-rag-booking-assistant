from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=100)
    metadata: dict[str, Any] | None = None
    category: str | None = None


class SearchResponse(BaseModel):
    score: float
    text: str
    metadata: dict[str, Any]
    document_id: UUID


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str
    metadata: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    database: str


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    top_k: int | None = Field(default=None, ge=1, le=20)
    category: str | None = None
    session_id: UUID | None = None


class ChatSource(BaseModel):
    number: int
    document_id: UUID
    score: float
    text: str
    metadata: dict[str, Any]


class AppointmentServiceResponse(BaseModel):
    id: UUID
    name: str
    description: str
    duration_minutes: int


class AvailableSlotResponse(BaseModel):
    id: UUID
    service_id: UUID
    service_name: str
    professional_name: str
    starts_at: datetime
    ends_at: datetime


class AppointmentCreate(BaseModel):
    slot_id: UUID
    customer_name: str = Field(min_length=2, max_length=120)
    customer_email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    notes: str = Field(default="", max_length=1000)


class AppointmentResponse(BaseModel):
    id: UUID
    status: str
    service_name: str
    professional_name: str
    starts_at: datetime
    ends_at: datetime
    customer_name: str
    customer_email: str


class ChatResponse(BaseModel):
    answer: str
    model: str
    sources: list[ChatSource]
    appointment: AppointmentResponse | None = None
