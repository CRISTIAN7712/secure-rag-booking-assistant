from functools import lru_cache

from src.config.settings import get_settings
from src.database.connection import Database
from src.embeddings.sentence_transformer import SentenceTransformerProvider
from src.repositories.document_repository import DocumentRepository
from src.repositories.appointment_repository import AppointmentRepository
from src.services.appointment_service import AppointmentService
from src.services.appointment_chat_service import AppointmentChatService
from src.services.chunking import TextChunker
from src.services.document_service import DocumentService
from src.services.openrouter import OpenRouterClient
from src.services.rag_service import RagService

_database: Database | None = None


def set_database(database: Database) -> None:
    global _database
    _database = database
    get_service.cache_clear()
    get_rag_service.cache_clear()
    get_appointment_service.cache_clear()
    get_appointment_chat_service.cache_clear()


@lru_cache
def get_service() -> DocumentService:
    if _database is None:
        raise RuntimeError("Database is not initialized")
    settings = get_settings()
    return DocumentService(
        DocumentRepository(_database),
        SentenceTransformerProvider(settings.embedding_model),
        TextChunker(settings.chunk_size, settings.chunk_overlap),
    )


@lru_cache
def get_rag_service() -> RagService:
    settings = get_settings()
    return RagService(
        get_service(),
        OpenRouterClient(
            settings.openrouter_api_key, settings.openrouter_model, settings.openrouter_base_url,
            settings.openrouter_app_name, settings.openrouter_site_url,
        ),
        settings.rag_top_k, settings.rag_max_context_chars,
    )


@lru_cache
def get_appointment_service() -> AppointmentService:
    if _database is None:
        raise RuntimeError("Database is not initialized")
    return AppointmentService(AppointmentRepository(_database))


@lru_cache
def get_appointment_chat_service() -> AppointmentChatService:
    return AppointmentChatService(get_appointment_service())
