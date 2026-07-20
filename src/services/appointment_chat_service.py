from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from src.services.appointment_service import AppointmentService
from src.repositories.appointment_repository import SlotUnavailableError


@dataclass(frozen=True, slots=True)
class AppointmentChatResult:
    answer: str
    appointment: dict[str, Any] | None = None


class AppointmentChatService:
    """Deterministic appointment state machine; the LLM never writes bookings."""

    _intent_words = ("agendar", "reservar", "cita", "disponibilidad", "turno")
    _weekdays = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4,
                 "sabado": 5, "domingo": 6}

    def __init__(self, appointments: AppointmentService) -> None:
        self._appointments = appointments

    def respond(self, session_id: UUID | None, message: str) -> AppointmentChatResult | None:
        normalized = self._normalize(message)
        if session_id is None:
            if any(word in normalized for word in self._intent_words):
                return AppointmentChatResult("No pude iniciar la agenda porque falta el identificador de sesión.")
            return None
        state = self._appointments.conversation_state(session_id)
        if normalized in {"salir", "cancelar proceso", "cancelar agenda"} and state:
            self._appointments.clear_conversation_state(session_id)
            return AppointmentChatResult("Cancelé el proceso de agendamiento. No se creó ninguna cita.")
        # These explicit intents can interrupt any stale or incomplete conversation.
        if (any(word in normalized for word in ("cambiar", "actualizar", "modificar", "reprogramar"))
                and ("cita" in normalized or "reserva" in normalized or "fecha" in normalized)):
            self._appointments.save_conversation_state(session_id, {"step": "reschedule_email"})
            return AppointmentChatResult(
                "Para reprogramar tu cita, escribe el correo usado en la reserva."
            )
        if "cancelar" in normalized and ("cita" in normalized or "reserva" in normalized):
            self._appointments.save_conversation_state(session_id, {"step": "cancel_email"})
            return AppointmentChatResult(
                "Para buscar la cita que deseas cancelar, escribe el correo usado en la reserva."
            )
        if any(phrase in normalized for phrase in
               ("mis citas", "ver citas", "consultar citas", "citas programadas")):
            self._appointments.save_conversation_state(session_id, {"step": "list_email"})
            return AppointmentChatResult(
                "Escribe el correo usado al reservar y consultaré tus citas programadas."
            )
        if any(phrase in normalized for phrase in
               ("citas disponibles", "horarios disponibles", "ver disponibilidad")):
            self._appointments.clear_conversation_state(session_id)
            return self._start(session_id)
        if (("agendar" in normalized or "reservar" in normalized)
                and ("cita" in normalized or "turno" in normalized)):
            self._appointments.clear_conversation_state(session_id)
            return self._start(session_id)
        if not state:
            if not any(word in normalized for word in self._intent_words):
                return None
            return self._start(session_id)
        step = state.get("step")
        handlers = {
            "service": self._choose_service,
            "date": self._choose_date,
            "slot": self._choose_slot,
            "name": self._capture_name,
            "email": self._capture_email,
            "list_email": self._list_by_email,
            "cancel_email": self._cancel_by_email,
            "cancel_select": self._select_cancellation,
            "cancel_confirm": self._confirm_cancellation,
            "reschedule_email": self._reschedule_by_email,
            "reschedule_select": self._select_reschedule_appointment,
            "reschedule_date": self._choose_reschedule_date,
            "reschedule_slot": self._choose_reschedule_slot,
            "reschedule_confirm": self._confirm_reschedule,
        }
        handler = handlers.get(step)
        if not handler:
            self._appointments.clear_conversation_state(session_id)
            return self._start(session_id)
        return handler(session_id, state, message)

    def _start(self, session_id: UUID) -> AppointmentChatResult:
        services = self._appointments.list_services()
        self._appointments.save_conversation_state(session_id, {"step": "service"})
        options = "\n".join(f"{i}. {service['name']} ({service['duration_minutes']} min)"
                            for i, service in enumerate(services, 1))
        return AppointmentChatResult(f"Claro. ¿Qué servicio deseas reservar?\n\n{options}\n\nEscribe el número o el nombre.")

    def _choose_service(self, session_id: UUID, state: dict[str, Any], message: str) -> AppointmentChatResult:
        services = self._appointments.list_services()
        chosen = self._select_option(services, message, "name")
        if not chosen:
            return AppointmentChatResult("No reconocí el servicio. Escribe 1, 2, 3 o su nombre.")
        state.update({"step": "date", "service_id": str(chosen["id"]), "service_name": chosen["name"]})
        self._appointments.save_conversation_state(session_id, state)
        return AppointmentChatResult(
            f"Elegiste {chosen['name']}. ¿Para qué fecha? Puedes escribir “mañana”, “lunes” o “25/07/2026”."
        )

    def _choose_date(self, session_id: UUID, state: dict[str, Any], message: str) -> AppointmentChatResult:
        selected = self._parse_date(message)
        if not selected or selected < date.today():
            return AppointmentChatResult("No reconocí una fecha futura. Prueba con “mañana” o DD/MM/AAAA.")
        slots = self._appointments.availability(UUID(state["service_id"]), selected)
        if not slots:
            return AppointmentChatResult(
                f"No hay horarios disponibles el {selected.strftime('%d/%m/%Y')}. Indica otra fecha."
            )
        state.update({"step": "slot", "date": selected.isoformat(),
                      "slots": [str(slot["id"]) for slot in slots]})
        self._appointments.save_conversation_state(session_id, state)
        options = "\n".join(
            f"{index}. {slot['starts_at'].astimezone().strftime('%H:%M')} con {slot['professional_name']}"
            for index, slot in enumerate(slots, 1)
        )
        return AppointmentChatResult(
            f"Horarios disponibles para el {selected.strftime('%d/%m/%Y')}:\n\n{options}\n\nElige un número."
        )

    def _choose_slot(self, session_id: UUID, state: dict[str, Any], message: str) -> AppointmentChatResult:
        match = re.search(r"\d+", message)
        index = int(match.group()) - 1 if match else -1
        slots = state.get("slots", [])
        if index < 0 or index >= len(slots):
            return AppointmentChatResult(f"Elige un horario entre 1 y {len(slots)}.")
        state.update({"step": "name", "slot_id": slots[index]})
        state.pop("slots", None)
        self._appointments.save_conversation_state(session_id, state)
        return AppointmentChatResult("Perfecto. ¿Cuál es tu nombre completo?")

    def _capture_name(self, session_id: UUID, state: dict[str, Any], message: str) -> AppointmentChatResult:
        name = message.strip()
        if len(name) < 2:
            return AppointmentChatResult("Escribe un nombre válido de al menos dos caracteres.")
        state.update({"step": "email", "customer_name": name})
        self._appointments.save_conversation_state(session_id, state)
        return AppointmentChatResult("¿Cuál es tu correo electrónico para confirmar la cita?")

    def _capture_email(self, session_id: UUID, state: dict[str, Any], message: str) -> AppointmentChatResult:
        email = message.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            return AppointmentChatResult("El correo no parece válido. Escríbelo nuevamente.")
        try:
            appointment = self._appointments.book(
                UUID(state["slot_id"]), state["customer_name"], email,
                "Reserva creada desde el chatbot",
            )
        except SlotUnavailableError:
            self._appointments.clear_conversation_state(session_id)
            return AppointmentChatResult(
                "Ese horario acaba de ocuparse. Escribe “agendar cita” para elegir otro."
            )
        self._appointments.clear_conversation_state(session_id)
        when = appointment["starts_at"].astimezone().strftime("%d/%m/%Y a las %H:%M")
        return AppointmentChatResult(
            f"Cita confirmada para {appointment['service_name']} el {when} con "
            f"{appointment['professional_name']}. Tu código es {appointment['id']}.",
            appointment,
        )

    def _list_by_email(self, session_id: UUID, state: dict[str, Any], message: str) -> AppointmentChatResult:
        email = self._valid_email(message)
        if not email:
            return AppointmentChatResult("El correo no parece válido. Escríbelo nuevamente.")
        appointments = self._appointments.upcoming_for_email(email)
        self._appointments.clear_conversation_state(session_id)
        if not appointments:
            return AppointmentChatResult(f"No encontré citas futuras activas para {email}.")
        return AppointmentChatResult(
            "Tus citas programadas son:\n\n" + self._format_appointments(appointments)
        )

    def _cancel_by_email(self, session_id: UUID, state: dict[str, Any], message: str) -> AppointmentChatResult:
        email = self._valid_email(message)
        if not email:
            return AppointmentChatResult("El correo no parece válido. Escríbelo nuevamente.")
        appointments = self._appointments.upcoming_for_email(email)
        if not appointments:
            self._appointments.clear_conversation_state(session_id)
            return AppointmentChatResult(f"No encontré citas futuras activas para {email}.")
        state.update({"step": "cancel_select", "appointment_ids": [str(item["id"]) for item in appointments]})
        self._appointments.save_conversation_state(session_id, state)
        return AppointmentChatResult(
            "Estas son tus citas:\n\n" + self._format_appointments(appointments)
            + "\n\nEscribe el número de la cita que deseas cancelar."
        )

    def _select_cancellation(self, session_id: UUID, state: dict[str, Any], message: str) -> AppointmentChatResult:
        match = re.search(r"\d+", message)
        index = int(match.group()) - 1 if match else -1
        appointment_ids = state.get("appointment_ids", [])
        if index < 0 or index >= len(appointment_ids):
            return AppointmentChatResult(f"Elige un número entre 1 y {len(appointment_ids)}.")
        state.update({"step": "cancel_confirm", "appointment_id": appointment_ids[index]})
        state.pop("appointment_ids", None)
        self._appointments.save_conversation_state(session_id, state)
        return AppointmentChatResult("¿Confirmas que deseas cancelar esa cita? Responde “sí” o “no”.")

    def _confirm_cancellation(self, session_id: UUID, state: dict[str, Any], message: str) -> AppointmentChatResult:
        answer = self._normalize(message)
        if answer in {"no", "cancelar proceso", "salir"}:
            self._appointments.clear_conversation_state(session_id)
            return AppointmentChatResult("Conservé la cita. No se realizó ninguna cancelación.")
        if answer not in {"si", "confirmo", "confirmar"}:
            return AppointmentChatResult("Responde “sí” para cancelar la cita o “no” para conservarla.")
        cancelled = self._appointments.cancel(UUID(state["appointment_id"]))
        self._appointments.clear_conversation_state(session_id)
        if not cancelled:
            return AppointmentChatResult("La cita ya estaba cancelada o no se encontró.")
        return AppointmentChatResult("La cita fue cancelada correctamente. El horario volvió a estar disponible.")

    def _reschedule_by_email(self, session_id: UUID, state: dict[str, Any], message: str) -> AppointmentChatResult:
        email = self._valid_email(message)
        if not email:
            return AppointmentChatResult("El correo no parece válido. Escríbelo nuevamente.")
        appointments = self._appointments.upcoming_for_email(email)
        if not appointments:
            self._appointments.clear_conversation_state(session_id)
            return AppointmentChatResult(f"No encontré citas futuras activas para {email}.")
        state.update({
            "step": "reschedule_select",
            "appointments": [
                {"id": str(item["id"]), "service_id": str(item["service_id"])}
                for item in appointments
            ],
        })
        self._appointments.save_conversation_state(session_id, state)
        return AppointmentChatResult(
            "Estas son tus citas:\n\n" + self._format_appointments(appointments)
            + "\n\nEscribe el número de la cita que deseas reprogramar."
        )

    def _select_reschedule_appointment(self, session_id: UUID, state: dict[str, Any],
                                       message: str) -> AppointmentChatResult:
        match = re.search(r"\d+", message)
        index = int(match.group()) - 1 if match else -1
        appointments = state.get("appointments", [])
        if index < 0 or index >= len(appointments):
            return AppointmentChatResult(f"Elige un número entre 1 y {len(appointments)}.")
        chosen = appointments[index]
        state.update({"step": "reschedule_date", "appointment_id": chosen["id"],
                      "service_id": chosen["service_id"]})
        state.pop("appointments", None)
        self._appointments.save_conversation_state(session_id, state)
        return AppointmentChatResult(
            "¿Cuál será la nueva fecha? Puedes escribir “mañana”, “lunes” o DD/MM/AAAA."
        )

    def _choose_reschedule_date(self, session_id: UUID, state: dict[str, Any],
                                message: str) -> AppointmentChatResult:
        selected = self._parse_date(message)
        if not selected or selected < date.today():
            return AppointmentChatResult("No reconocí una fecha futura. Prueba con “mañana” o DD/MM/AAAA.")
        slots = self._appointments.availability(UUID(state["service_id"]), selected)
        if not slots:
            return AppointmentChatResult(
                f"No hay horarios disponibles el {selected.strftime('%d/%m/%Y')}. Indica otra fecha."
            )
        state.update({"step": "reschedule_slot", "new_date": selected.isoformat(),
                      "slots": [str(slot["id"]) for slot in slots]})
        self._appointments.save_conversation_state(session_id, state)
        options = "\n".join(
            f"{index}. {slot['starts_at'].astimezone().strftime('%H:%M')} con {slot['professional_name']}"
            for index, slot in enumerate(slots, 1)
        )
        return AppointmentChatResult(
            f"Horarios disponibles para el {selected.strftime('%d/%m/%Y')}:\n\n{options}\n\nElige un número."
        )

    def _choose_reschedule_slot(self, session_id: UUID, state: dict[str, Any],
                                message: str) -> AppointmentChatResult:
        match = re.search(r"\d+", message)
        index = int(match.group()) - 1 if match else -1
        slots = state.get("slots", [])
        if index < 0 or index >= len(slots):
            return AppointmentChatResult(f"Elige un horario entre 1 y {len(slots)}.")
        state.update({"step": "reschedule_confirm", "new_slot_id": slots[index]})
        state.pop("slots", None)
        self._appointments.save_conversation_state(session_id, state)
        return AppointmentChatResult(
            f"¿Confirmas el cambio para el {state['new_date']}? Responde “sí” o “no”."
        )

    def _confirm_reschedule(self, session_id: UUID, state: dict[str, Any],
                            message: str) -> AppointmentChatResult:
        answer = self._normalize(message)
        if answer == "no":
            self._appointments.clear_conversation_state(session_id)
            return AppointmentChatResult("No modifiqué la cita; conserva su fecha y horario anteriores.")
        if answer not in {"si", "confirmo", "confirmar"}:
            return AppointmentChatResult("Responde “sí” para actualizar la cita o “no” para conservarla.")
        try:
            appointment = self._appointments.reschedule(
                UUID(state["appointment_id"]), UUID(state["new_slot_id"])
            )
        except SlotUnavailableError as exc:
            self._appointments.clear_conversation_state(session_id)
            return AppointmentChatResult(f"No pude actualizar la cita: {exc}. Inténtalo nuevamente.")
        self._appointments.clear_conversation_state(session_id)
        when = appointment["starts_at"].astimezone().strftime("%d/%m/%Y a las %H:%M")
        return AppointmentChatResult(
            f"Cita actualizada correctamente: {appointment['service_name']} el {when} con "
            f"{appointment['professional_name']}. El código sigue siendo {appointment['id']}.",
            appointment,
        )

    @staticmethod
    def _valid_email(value: str) -> str | None:
        email = value.strip().lower()
        return email if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) else None

    @staticmethod
    def _format_appointments(appointments: list[dict[str, Any]]) -> str:
        return "\n".join(
            f"{index}. {item['service_name']} · "
            f"{item['starts_at'].astimezone().strftime('%d/%m/%Y %H:%M')} · "
            f"{item['professional_name']} · código {item['id']}"
            for index, item in enumerate(appointments, 1)
        )

    def _select_option(self, options: list[dict[str, Any]], message: str, key: str) -> dict[str, Any] | None:
        normalized = self._normalize(message)
        number = re.search(r"\d+", normalized)
        if number and 1 <= int(number.group()) <= len(options):
            return options[int(number.group()) - 1]
        return next((option for option in options if self._normalize(option[key]) in normalized), None)

    def _parse_date(self, value: str) -> date | None:
        normalized = self._normalize(value)
        today = date.today()
        if "manana" in normalized:
            return today + timedelta(days=1)
        if normalized == "hoy" or "para hoy" in normalized:
            return today
        numeric = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?\b", normalized)
        if numeric:
            try:
                return date(int(numeric.group(3) or today.year), int(numeric.group(2)), int(numeric.group(1)))
            except ValueError:
                return None
        for name, weekday in self._weekdays.items():
            if name in normalized:
                days = (weekday - today.weekday()) % 7
                return today + timedelta(days=days or 7)
        return None

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(character for character in unicodedata.normalize("NFD", value.lower())
                       if unicodedata.category(character) != "Mn").strip()
