"""Domain data access (repository class) for the hospital.

ALL persistence for the core entities lives here. Providers and controllers
call these methods and never issue ``select()`` / session code.

Atomic, guarantee-bearing writes (no double-booking) are single-transaction
methods so the data layer enforces them regardless of caller.
"""

from sqlmodel import select

from app.models import (
    Appointment,
    AvailabilitySlot,
    ChatMessage,
    Doctor,
    Patient,
    RefillRequest,
    Treatment,
)
from app.repositories.base import BaseRepository


class DomainRepository(BaseRepository):
    # ----------------------------------------------------------------- #
    # Patients
    # ----------------------------------------------------------------- #
    def create_patient(self, **fields) -> Patient:
        with self._session() as s:
            patient = Patient(**fields)
            s.add(patient)
            s.commit()
            s.refresh(patient)
            return patient

    def list_patients(self) -> list[Patient]:
        with self._session() as s:
            return list(s.exec(select(Patient).order_by(Patient.id.desc())).all())

    def get_patient(self, patient_id: int) -> Patient | None:
        with self._session() as s:
            return s.get(Patient, patient_id)

    def find_patients_by_name(self, first_name: str, last_name: str) -> list[Patient]:
        """Case-insensitive match on 'first last' — good enough for a small clinic's roster."""
        first, last = first_name.lower().strip(), last_name.lower().strip()
        with self._session() as s:
            patients = s.exec(select(Patient)).all()
            return [
                p for p in patients
                if p.name.lower().split() and
                p.name.lower().split()[0] == first and p.name.lower().split()[-1] == last
            ]

    # ----------------------------------------------------------------- #
    # Doctors
    # ----------------------------------------------------------------- #
    def list_doctors(self) -> list[Doctor]:
        with self._session() as s:
            return list(s.exec(select(Doctor).order_by(Doctor.name)).all())

    def get_doctor(self, doctor_id: int) -> Doctor | None:
        with self._session() as s:
            return s.get(Doctor, doctor_id)

    def create_doctor(self, **fields) -> Doctor:
        with self._session() as s:
            doctor = Doctor(**fields)
            s.add(doctor)
            s.commit()
            s.refresh(doctor)
            return doctor

    def update_doctor(self, doctor_id: int, **changes) -> Doctor | None:
        with self._session() as s:
            doctor = s.get(Doctor, doctor_id)
            if doctor is None:
                return None
            for key, value in changes.items():
                if value is not None and hasattr(doctor, key):
                    setattr(doctor, key, value)
            s.add(doctor)
            s.commit()
            s.refresh(doctor)
            return doctor

    def find_doctors_by_specialty(self, specialty: str) -> list[Doctor]:
        needle = specialty.lower().strip()
        with self._session() as s:
            docs = s.exec(select(Doctor)).all()
            return [d for d in docs if needle in d.specialty.lower()]

    # ----------------------------------------------------------------- #
    # Availability / schedule
    # ----------------------------------------------------------------- #
    def get_open_slots(self, doctor_id: int, after: str) -> list[AvailabilitySlot]:
        with self._session() as s:
            stmt = select(AvailabilitySlot).where(
                AvailabilitySlot.doctor_id == doctor_id,
                AvailabilitySlot.is_booked == False,  # noqa: E712
            )
            slots = [sl for sl in s.exec(stmt).all() if sl.starts_at >= after]
            slots.sort(key=lambda x: x.starts_at)
            return slots

    def get_slot(self, slot_id: int) -> AvailabilitySlot | None:
        with self._session() as s:
            return s.get(AvailabilitySlot, slot_id)

    def list_all_slots(self, doctor_id: int) -> list[AvailabilitySlot]:
        """Every slot for a doctor — open AND booked — for the admin schedule view."""
        with self._session() as s:
            slots = list(
                s.exec(
                    select(AvailabilitySlot).where(AvailabilitySlot.doctor_id == doctor_id)
                ).all()
            )
            slots.sort(key=lambda x: x.starts_at)
            return slots

    def slot_exists(self, doctor_id: int, starts_at: str) -> bool:
        with self._session() as s:
            stmt = select(AvailabilitySlot).where(
                AvailabilitySlot.doctor_id == doctor_id,
                AvailabilitySlot.starts_at == starts_at,
            )
            return s.exec(stmt).first() is not None

    def create_slot(self, doctor_id: int, starts_at: str, duration_min: int) -> AvailabilitySlot:
        with self._session() as s:
            slot = AvailabilitySlot(
                doctor_id=doctor_id, starts_at=starts_at, duration_min=duration_min, is_booked=False
            )
            s.add(slot)
            s.commit()
            s.refresh(slot)
            return slot

    def delete_slot(self, slot_id: int) -> bool:
        """Delete an open slot. Refuses (returns False) if it's already booked."""
        with self._session() as s:
            slot = s.get(AvailabilitySlot, slot_id)
            if slot is None or slot.is_booked:
                return False
            s.delete(slot)
            s.commit()
            return True

    # ----------------------------------------------------------------- #
    # Appointments
    # ----------------------------------------------------------------- #
    def book_appointment(self, patient_id: int, doctor_id: int, slot_id: int, reason: str) -> dict:
        """Atomically reserve a slot + create the appointment (no double-booking).

        ``with_for_update`` is what makes this safe on PostgreSQL: under READ
        COMMITTED two concurrent bookings would otherwise both read
        ``is_booked=False`` and both insert. The row lock serialises them, so
        the loser sees ``is_booked=True`` and gets the error. SQLAlchemy's
        SQLite dialect omits FOR UPDATE, where writes already serialise.
        """
        with self._session() as s:
            slot = s.get(AvailabilitySlot, slot_id, with_for_update=True)
            if slot is None:
                return {"error": f"Slot {slot_id} does not exist."}
            if slot.is_booked:
                return {"error": f"Slot {slot_id} is already booked."}
            if slot.doctor_id != doctor_id:
                return {"error": "Slot does not belong to that doctor."}
            if s.get(Patient, patient_id) is None:
                return {"error": f"Patient {patient_id} does not exist."}

            slot.is_booked = True
            appt = Appointment(
                patient_id=patient_id, doctor_id=doctor_id, slot_id=slot_id,
                starts_at=slot.starts_at, duration_min=slot.duration_min,
                reason=reason, status="booked",
            )
            s.add(slot)
            s.add(appt)
            s.commit()
            s.refresh(appt)
            return {
                "appointment_id": appt.id, "doctor_id": doctor_id,
                "starts_at": appt.starts_at, "status": appt.status,
            }

    def get_appointment(self, appointment_id: int) -> Appointment | None:
        with self._session() as s:
            return s.get(Appointment, appointment_id)

    def list_all_appointments(self) -> list[Appointment]:
        with self._session() as s:
            return list(
                s.exec(select(Appointment).order_by(Appointment.starts_at)).all()
            )

    def list_appointments_on(self, day_iso: str) -> list[Appointment]:
        """Appointments whose ``starts_at`` falls on the given ISO date —
        filtered in SQL (ISO strings sort lexicographically) instead of
        loading the whole table."""
        with self._session() as s:
            stmt = (
                select(Appointment)
                .where(Appointment.starts_at >= day_iso)
                .where(Appointment.starts_at < f"{day_iso}T24")
                .order_by(Appointment.starts_at)
            )
            return list(s.exec(stmt).all())

    def count_appointments(self) -> int:
        with self._session() as s:
            return len(s.exec(select(Appointment.id)).all())

    def list_appointments_by_patient(self, patient_id: int) -> list[Appointment]:
        with self._session() as s:
            return list(
                s.exec(
                    select(Appointment).where(Appointment.patient_id == patient_id)
                    .order_by(Appointment.starts_at.desc())
                ).all()
            )

    def list_appointments_by_doctor(self, doctor_id: int) -> list[Appointment]:
        with self._session() as s:
            return list(
                s.exec(
                    select(Appointment).where(Appointment.doctor_id == doctor_id)
                    .order_by(Appointment.starts_at)
                ).all()
            )

    def set_appointment_status(self, appointment_id: int, status: str, *, free_slot: bool = False) -> Appointment | None:
        with self._session() as s:
            appt = s.get(Appointment, appointment_id)
            if appt is None:
                return None
            appt.status = status
            s.add(appt)
            if free_slot and appt.slot_id:
                slot = s.get(AvailabilitySlot, appt.slot_id)
                if slot:
                    slot.is_booked = False
                    s.add(slot)
            s.commit()
            s.refresh(appt)
            return appt

    # ----------------------------------------------------------------- #
    # Treatments (history)
    # ----------------------------------------------------------------- #
    def add_treatment(self, appointment_id: int, patient_id: int, doctor_id: int,
                       diagnosis: str, prescription: str, notes: str) -> Treatment:
        with self._session() as s:
            t = Treatment(
                appointment_id=appointment_id, patient_id=patient_id, doctor_id=doctor_id,
                diagnosis=diagnosis, prescription=prescription, notes=notes,
            )
            s.add(t)
            s.commit()
            s.refresh(t)
            return t

    def list_treatments_by_patient(self, patient_id: int) -> list[Treatment]:
        with self._session() as s:
            return list(
                s.exec(
                    select(Treatment).where(Treatment.patient_id == patient_id)
                    .order_by(Treatment.created_at.desc())
                ).all()
            )

    def get_treatment_by_appointment(self, appointment_id: int) -> Treatment | None:
        with self._session() as s:
            return s.exec(
                select(Treatment).where(Treatment.appointment_id == appointment_id)
            ).first()

    # ----------------------------------------------------------------- #
    # Refill requests (lightweight — staff review the queue)
    # ----------------------------------------------------------------- #
    def create_refill_request(self, patient_id: int, medication: str, notes: str) -> RefillRequest:
        with self._session() as s:
            r = RefillRequest(patient_id=patient_id, medication=medication, notes=notes)
            s.add(r)
            s.commit()
            s.refresh(r)
            return r

    def list_refill_requests(self) -> list[RefillRequest]:
        with self._session() as s:
            return list(
                s.exec(select(RefillRequest).order_by(RefillRequest.created_at.desc())).all()
            )

    # ----------------------------------------------------------------- #
    # Appointment-agent chat
    # ----------------------------------------------------------------- #
    def add_chat_message(self, thread_id: str, patient_id: int | None, role: str, content: str) -> ChatMessage:
        with self._session() as s:
            m = ChatMessage(thread_id=thread_id, patient_id=patient_id, role=role, content=content)
            s.add(m)
            s.commit()
            s.refresh(m)
            return m

    def get_chat_messages(self, thread_id: str) -> list[ChatMessage]:
        with self._session() as s:
            return list(
                s.exec(
                    select(ChatMessage).where(ChatMessage.thread_id == thread_id)
                    .order_by(ChatMessage.id)
                ).all()
            )
