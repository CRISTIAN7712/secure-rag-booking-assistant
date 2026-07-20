from datetime import date
from typing import Any
from uuid import UUID

from src.repositories.appointment_repository import AppointmentRepository


class AppointmentService:
    def __init__(self, repository: AppointmentRepository) -> None:
        self._repository = repository

    def list_services(self) -> list[dict[str, Any]]:
        return self._repository.services()

    def availability(self, service_id: UUID, selected_date: date) -> list[dict[str, Any]]:
        return self._repository.available_slots(service_id, selected_date)

    def book(self, slot_id: UUID, name: str, email: str, notes: str = "") -> dict[str, Any]:
        return self._repository.book(slot_id, name.strip(), email.strip(), notes.strip())

    def cancel(self, appointment_id: UUID) -> bool:
        return self._repository.cancel(appointment_id)

    def upcoming_for_email(self, customer_email: str) -> list[dict[str, Any]]:
        return self._repository.upcoming_for_email(customer_email.strip().lower())

    def reschedule(self, appointment_id: UUID, new_slot_id: UUID) -> dict[str, Any]:
        return self._repository.reschedule(appointment_id, new_slot_id)

    def conversation_state(self, session_id: UUID) -> dict[str, Any]:
        return self._repository.conversation_state(session_id)

    def save_conversation_state(self, session_id: UUID, state: dict[str, Any]) -> None:
        self._repository.save_conversation_state(session_id, state)

    def clear_conversation_state(self, session_id: UUID) -> None:
        self._repository.clear_conversation_state(session_id)
