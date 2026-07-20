from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID, uuid4

import numpy as np
from psycopg.rows import dict_row

from src.database.connection import Database
from src.models.domain import ChunkInput, DocumentSummary, SearchResult


class DocumentRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, filename: str, content_type: str, metadata: dict[str, Any], checksum: str,
               chunks: Sequence[ChunkInput], vectors: np.ndarray, model: str) -> UUID:
        document_id = uuid4()
        with self._database.connection() as conn:
            conn.execute(
                "INSERT INTO documents(id, filename, content_type, metadata, checksum) VALUES (%s,%s,%s,%s,%s)",
                (document_id, filename, content_type, json.dumps(metadata), checksum),
            )
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk_id = uuid4()
                conn.execute(
                    "INSERT INTO chunks(id, document_id, text, metadata, chunk_index) VALUES (%s,%s,%s,%s,%s)",
                    (chunk_id, document_id, chunk.text, json.dumps(chunk.metadata), chunk.index),
                )
                conn.execute(
                    "INSERT INTO embeddings(chunk_id, model, embedding) VALUES (%s,%s,%s)",
                    (chunk_id, model, vector),
                )
        return document_id

    def list(self) -> list[DocumentSummary]:
        with self._database.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                rows = cursor.execute(
                    "SELECT id, filename, content_type, metadata, created_at "
                    "FROM documents ORDER BY created_at DESC"
                ).fetchall()
        return [DocumentSummary(**row) for row in rows]

    def delete(self, document_id: UUID) -> bool:
        with self._database.connection() as conn:
            result = conn.execute("DELETE FROM documents WHERE id = %s", (document_id,))
            return result.rowcount > 0

    def search(self, vector: np.ndarray, top_k: int, metadata: dict[str, Any] | None = None,
               category: str | None = None) -> list[SearchResult]:
        filters, params = [], [vector]
        if metadata:
            filters.append("c.metadata @> %s::jsonb")
            params.append(json.dumps(metadata))
        if category:
            filters.append("c.metadata->>'category' = %s")
            params.append(category)
        where = "WHERE " + " AND ".join(filters) if filters else ""
        params.extend([vector, top_k])
        query = f"""
            SELECT c.document_id, c.text, c.metadata,
                   1 - (e.embedding <=> %s) AS score
            FROM embeddings e JOIN chunks c ON c.id = e.chunk_id
            {where}
            ORDER BY e.embedding <=> %s LIMIT %s
        """
        with self._database.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                rows = cursor.execute(query, params).fetchall()
        return [SearchResult(**row) for row in rows]

    def chunks_for_reembedding(self, document_id: UUID | None = None) -> list[dict[str, Any]]:
        where, params = ("WHERE c.document_id = %s", [document_id]) if document_id else ("", [])
        with self._database.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                return cursor.execute(
                    f"SELECT c.id, c.text FROM chunks c {where} ORDER BY c.document_id, c.chunk_index",
                    params,
                ).fetchall()

    def update_embeddings(self, items: Sequence[dict[str, Any]], vectors: np.ndarray, model: str) -> None:
        with self._database.connection() as conn:
            for item, vector in zip(items, vectors, strict=True):
                conn.execute(
                    """INSERT INTO embeddings(chunk_id, model, embedding) VALUES (%s,%s,%s)
                       ON CONFLICT(chunk_id) DO UPDATE SET model=EXCLUDED.model,
                       embedding=EXCLUDED.embedding, updated_at=now()""",
                    (item["id"], model, vector),
                )

    def ping(self) -> bool:
        with self._database.connection() as conn:
            return conn.execute("SELECT 1").fetchone()[0] == 1
