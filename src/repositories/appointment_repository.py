from __future__ import annotations

from datetime import date
import json
from typing import Any
from uuid import UUID

from psycopg import errors
from psycopg.rows import dict_row

from src.database.connection import Database


class SlotUnavailableError(RuntimeError):
    pass


class AppointmentRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def services(self) -> list[dict[str, Any]]:
        with self._database.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                "SELECT id, name, description, duration_minutes FROM appointment_services "
                "WHERE active ORDER BY name"
            ).fetchall()

    def available_slots(self, service_id: UUID, selected_date: date) -> list[dict[str, Any]]:
        with self._database.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """SELECT sl.id, s.id AS service_id, s.name AS service_name,
                          p.name AS professional_name, sl.starts_at, sl.ends_at
                   FROM appointment_slots sl
                   JOIN professionals p ON p.id = sl.professional_id
                   JOIN appointment_services s ON s.id = p.service_id
                   LEFT JOIN appointments a ON a.slot_id = sl.id AND a.status = 'confirmed'
                   WHERE s.id = %s AND (sl.starts_at AT TIME ZONE 'America/Bogota')::date = %s
                     AND sl.starts_at > now() AND sl.active AND p.active AND s.active AND a.id IS NULL
                   ORDER BY sl.starts_at""",
                (service_id, selected_date),
            ).fetchall()

    def book(self, slot_id: UUID, customer_name: str, customer_email: str,
             notes: str) -> dict[str, Any]:
        try:
            with self._database.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
                slot = cursor.execute(
                    """SELECT sl.id AS slot_id, sl.starts_at, sl.ends_at, s.name AS service_name,
                              p.name AS professional_name
                       FROM appointment_slots sl
                       JOIN professionals p ON p.id=sl.professional_id
                       JOIN appointment_services s ON s.id=p.service_id
                       WHERE sl.id=%s AND sl.active AND sl.starts_at > now() FOR UPDATE OF sl""",
                    (slot_id,),
                ).fetchone()
                if not slot:
                    raise SlotUnavailableError("El horario no existe o ya pasó")
                occupied = cursor.execute(
                    "SELECT 1 FROM appointments WHERE slot_id=%s AND status='confirmed'", (slot_id,)
                ).fetchone()
                if occupied:
                    raise SlotUnavailableError("El horario acaba de ser reservado")
                appointment = cursor.execute(
                    """INSERT INTO appointments(slot_id, customer_name, customer_email, notes)
                       VALUES (%s,%s,%s,%s) RETURNING id, status, customer_name, customer_email""",
                    (slot_id, customer_name, customer_email.lower(), notes),
                ).fetchone()
                return {**appointment, **slot}
        except errors.UniqueViolation as exc:
            raise SlotUnavailableError("El horario acaba de ser reservado") from exc

    def cancel(self, appointment_id: UUID) -> bool:
        with self._database.connection() as conn:
            result = conn.execute(
                """UPDATE appointments SET status='cancelled', cancelled_at=now()
                   WHERE id=%s AND status='confirmed'""", (appointment_id,)
            )
            return result.rowcount > 0

    def upcoming_for_email(self, customer_email: str) -> list[dict[str, Any]]:
        with self._database.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                """SELECT a.id, a.status, s.id AS service_id, s.name AS service_name, p.name AS professional_name,
                          sl.starts_at, sl.ends_at, a.customer_name, a.customer_email
                   FROM appointments a
                   JOIN appointment_slots sl ON sl.id=a.slot_id
                   JOIN professionals p ON p.id=sl.professional_id
                   JOIN appointment_services s ON s.id=p.service_id
                   WHERE lower(a.customer_email)=lower(%s) AND a.status='confirmed'
                     AND sl.starts_at > now()
                   ORDER BY sl.starts_at""",
                (customer_email,),
            ).fetchall()

    def reschedule(self, appointment_id: UUID, new_slot_id: UUID) -> dict[str, Any]:
        try:
            with self._database.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
                current = cursor.execute(
                    """SELECT a.id, p.service_id FROM appointments a
                       JOIN appointment_slots sl ON sl.id=a.slot_id
                       JOIN professionals p ON p.id=sl.professional_id
                       WHERE a.id=%s AND a.status='confirmed' FOR UPDATE OF a""",
                    (appointment_id,),
                ).fetchone()
                if not current:
                    raise SlotUnavailableError("La cita ya no está activa")
                new_slot = cursor.execute(
                    """SELECT sl.id AS slot_id, sl.starts_at, sl.ends_at, s.name AS service_name,
                              p.name AS professional_name, p.service_id
                       FROM appointment_slots sl
                       JOIN professionals p ON p.id=sl.professional_id
                       JOIN appointment_services s ON s.id=p.service_id
                       WHERE sl.id=%s AND sl.active AND sl.starts_at>now() FOR UPDATE OF sl""",
                    (new_slot_id,),
                ).fetchone()
                if not new_slot or new_slot["service_id"] != current["service_id"]:
                    raise SlotUnavailableError("El nuevo horario no corresponde al servicio de la cita")
                occupied = cursor.execute(
                    """SELECT 1 FROM appointments WHERE slot_id=%s AND status='confirmed' AND id<>%s""",
                    (new_slot_id, appointment_id),
                ).fetchone()
                if occupied:
                    raise SlotUnavailableError("El nuevo horario acaba de ser reservado")
                appointment = cursor.execute(
                    """UPDATE appointments SET slot_id=%s, updated_at=now() WHERE id=%s
                       RETURNING id, status, customer_name, customer_email""",
                    (new_slot_id, appointment_id),
                ).fetchone()
                new_slot.pop("service_id", None)
                return {**appointment, **new_slot}
        except errors.UniqueViolation as exc:
            raise SlotUnavailableError("El nuevo horario acaba de ser reservado") from exc

    def conversation_state(self, session_id: UUID) -> dict[str, Any]:
        with self._database.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                "SELECT state FROM appointment_conversations WHERE session_id=%s", (session_id,)
            ).fetchone()
            return row["state"] if row else {}

    def save_conversation_state(self, session_id: UUID, state: dict[str, Any]) -> None:
        with self._database.connection() as conn:
            conn.execute(
                """INSERT INTO appointment_conversations(session_id, state) VALUES (%s,%s::jsonb)
                   ON CONFLICT(session_id) DO UPDATE SET state=EXCLUDED.state, updated_at=now()""",
                (session_id, json.dumps(state)),
            )

    def clear_conversation_state(self, session_id: UUID) -> None:
        with self._database.connection() as conn:
            conn.execute("DELETE FROM appointment_conversations WHERE session_id=%s", (session_id,))
