import hashlib
from pathlib import Path
from typing import Any
from uuid import UUID

from src.embeddings.provider import EmbeddingProvider
from src.models.domain import DocumentSummary, SearchResult
from src.repositories.document_repository import DocumentRepository
from src.services.chunking import TextChunker
from src.services.loaders import load_text


class DocumentService:
    def __init__(self, repository: DocumentRepository, embeddings: EmbeddingProvider,
                 chunker: TextChunker) -> None:
        self._repository, self._embeddings, self._chunker = repository, embeddings, chunker

    def ingest(self, path: Path, metadata: dict[str, Any] | None = None) -> UUID:
        raw = path.read_bytes()
        text = load_text(path)
        combined = {"source": path.name, **(metadata or {})}
        chunks = self._chunker.split(text, combined)
        if not chunks:
            raise ValueError("Document contains no extractable text")
        vectors = self._embeddings.encode([chunk.text for chunk in chunks])
        return self._repository.create(
            path.name, path.suffix.lower().lstrip("."), combined,
            hashlib.sha256(raw).hexdigest(), chunks, vectors, self._embeddings.model_name,
        )

    def search(self, query: str, top_k: int = 5, metadata: dict[str, Any] | None = None,
               category: str | None = None) -> list[SearchResult]:
        vector = self._embeddings.encode([query])[0]
        return self._repository.search(vector, top_k, metadata, category)

    def list_documents(self) -> list[DocumentSummary]:
        return self._repository.list()

    def delete(self, document_id: UUID) -> bool:
        return self._repository.delete(document_id)

    def rebuild_embeddings(self, document_id: UUID | None = None) -> int:
        chunks = self._repository.chunks_for_reembedding(document_id)
        if not chunks:
            return 0
        vectors = self._embeddings.encode([item["text"] for item in chunks])
        self._repository.update_embeddings(chunks, vectors, self._embeddings.model_name)
        return len(chunks)

