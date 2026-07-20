from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ChunkInput:
    text: str
    index: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SearchResult:
    score: float
    text: str
    metadata: dict[str, Any]
    document_id: UUID


@dataclass(frozen=True, slots=True)
class DocumentSummary:
    id: UUID
    filename: str
    content_type: str
    metadata: dict[str, Any]
    created_at: datetime

