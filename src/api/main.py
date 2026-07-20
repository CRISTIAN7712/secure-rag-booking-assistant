import json
import logging
import tempfile
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from src.api.dependencies import (
    get_appointment_chat_service, get_appointment_service, get_rag_service, get_service, set_database,
)
from src.config.logging import configure_logging
from src.config.settings import get_settings
from src.database.connection import Database
from src.database.init_db import initialize_database
from src.models.schemas import (
    ChatRequest, ChatResponse, ChatSource, DocumentResponse, HealthResponse, SearchRequest, SearchResponse,
    AppointmentCreate, AppointmentResponse, AppointmentServiceResponse, AvailableSlotResponse,
)
from src.repositories.appointment_repository import SlotUnavailableError
from src.services.appointment_service import AppointmentService
from src.services.appointment_chat_service import AppointmentChatService
from src.services.document_service import DocumentService
from src.services.openrouter import OpenRouterError
from src.services.rag_service import RagService
from src.api.security import require_admin

logger = logging.getLogger(__name__)
settings = get_settings()
configure_logging(settings.log_level)
database = Database(settings.database_url)


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.open()
    initialize_database(database)
    set_database(database)
    logger.info("Application started")
    yield
    database.close()


app = FastAPI(title="pgvector RAG API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null", "http://localhost", "http://127.0.0.1"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(ValueError)
async def value_error_handler(_, exc: ValueError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED,
          dependencies=[Depends(require_admin)])
async def upload_document(file: UploadFile = File(...), metadata: str = Form("{}"),
                          service: DocumentService = Depends(get_service)) -> DocumentResponse:
    try:
        parsed = json.loads(metadata)
        if not isinstance(parsed, dict):
            raise ValueError("metadata must be a JSON object")
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "metadata must be valid JSON") from exc
    suffix = Path(file.filename or "document.txt").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        temp.write(await file.read())
        path = Path(temp.name)
    try:
        document_id = service.ingest(path, {"original_filename": file.filename, **parsed})
    finally:
        path.unlink(missing_ok=True)
    return DocumentResponse(id=document_id, filename=file.filename or "document", content_type=suffix[1:], metadata=parsed)


@app.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT,
            dependencies=[Depends(require_admin)])
def delete_document(document_id: UUID, service: DocumentService = Depends(get_service)) -> None:
    if not service.delete(document_id):
        raise HTTPException(404, "Document not found")


@app.get("/documents", response_model=list[DocumentResponse], dependencies=[Depends(require_admin)])
def list_documents(service: DocumentService = Depends(get_service)) -> list[DocumentResponse]:
    return [DocumentResponse(id=d.id, filename=d.filename, content_type=d.content_type, metadata=d.metadata)
            for d in service.list_documents()]


@app.post("/search", response_model=list[SearchResponse], dependencies=[Depends(require_admin)])
def search(request: SearchRequest, service: DocumentService = Depends(get_service)) -> list[SearchResponse]:
    return [
        SearchResponse(
            score=result.score,
            text=result.text,
            metadata=result.metadata,
            document_id=result.document_id,
        )
        for result in service.search(request.query, request.top_k, request.metadata, request.category)
    ]


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    rag: RagService = Depends(get_rag_service),
    appointment_chat: AppointmentChatService = Depends(get_appointment_chat_service),
) -> ChatResponse:
    appointment_result = appointment_chat.respond(request.session_id, request.message)
    if appointment_result:
        appointment = (
            AppointmentResponse(**appointment_result.appointment)
            if appointment_result.appointment else None
        )
        return ChatResponse(
            answer=appointment_result.answer,
            model="appointment-engine",
            sources=[],
            appointment=appointment,
        )
    try:
        result = rag.chat(request.message, request.history, request.top_k, request.category)
    except OpenRouterError as exc:
        logger.warning("LLM request failed: %s", exc)
        raise HTTPException(502, str(exc)) from exc
    return ChatResponse(
        answer=result.answer,
        model=result.model,
        sources=[
            ChatSource(
                number=index, document_id=source.document_id, score=source.score,
                text=source.text if settings.expose_source_text else "",
                metadata={
                    "source": source.metadata.get(
                        "original_filename", source.metadata.get("source", "documento")
                    )
                },
            )
            for index, source in enumerate(result.sources, start=1)
        ],
    )


@app.get("/appointments/services", response_model=list[AppointmentServiceResponse])
def appointment_services(
    service: AppointmentService = Depends(get_appointment_service),
) -> list[AppointmentServiceResponse]:
    return [AppointmentServiceResponse(**item) for item in service.list_services()]


@app.get("/appointments/availability", response_model=list[AvailableSlotResponse])
def appointment_availability(
    service_id: UUID,
    selected_date: date,
    service: AppointmentService = Depends(get_appointment_service),
) -> list[AvailableSlotResponse]:
    return [AvailableSlotResponse(**item) for item in service.availability(service_id, selected_date)]


@app.post("/appointments", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    request: AppointmentCreate,
    service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentResponse:
    try:
        return AppointmentResponse(**service.book(
            request.slot_id, request.customer_name, request.customer_email, request.notes
        ))
    except SlotUnavailableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@app.get("/appointments", response_model=list[AppointmentResponse])
def list_appointments(
    customer_email: str,
    service: AppointmentService = Depends(get_appointment_service),
) -> list[AppointmentResponse]:
    return [AppointmentResponse(**item) for item in service.upcoming_for_email(customer_email)]


@app.delete("/appointments/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_appointment(
    appointment_id: UUID,
    service: AppointmentService = Depends(get_appointment_service),
) -> None:
    if not service.cancel(appointment_id):
        raise HTTPException(404, "La cita no existe o ya está cancelada")


@app.put("/appointments/{appointment_id}", response_model=AppointmentResponse)
def reschedule_appointment(
    appointment_id: UUID,
    slot_id: UUID,
    service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentResponse:
    try:
        return AppointmentResponse(**service.reschedule(appointment_id, slot_id))
    except SlotUnavailableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@app.get("/health", response_model=HealthResponse)
def health(service: DocumentService = Depends(get_service)) -> HealthResponse:
    try:
        service._repository.ping()
        return HealthResponse(status="ok", database="ok")
    except Exception as exc:
        logger.exception("Health check failed")
        raise HTTPException(503, "Database unavailable") from exc
