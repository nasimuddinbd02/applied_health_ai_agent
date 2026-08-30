"""Admin business logic: onboard doctors and build their schedules.

Admin-only operations that were previously only possible through ``seed.py``:
creating a doctor (with an auto-provisioned login), editing the profile, and
generating availability slots from a weekly template.
"""

from datetime import date, datetime, timedelta

from app.models import today_iso
from app.repositories.domain import DomainRepository
from app.services.auth import AuthError, AuthService


class AdminError(Exception):
    """Raised on an invalid admin request (bad input, taken email, booked slot)."""


class AdminService:
    def __init__(self, domain_repo: DomainRepository, auth: AuthService) -> None:
        self._domain = domain_repo
        self._auth = auth

    # ----------------------------------------------------------------- #
    # Doctors
    # ----------------------------------------------------------------- #
    def create_doctor(self, profile: dict, login_email: str, login_password: str) -> dict:
        """Create the doctor profile + a linked ``doctor`` login in one flow.

        The login email is checked up front so we never leave an orphaned
        doctor row behind if the email is already taken.
        """
        if not profile.get("name"):
            raise AdminError("Doctor name is required.")
        if not login_email or not login_password:
            raise AdminError("A login email and temporary password are required.")
        if self._auth.email_exists(login_email):
            raise AdminError(f"Email '{login_email}' is already registered.")

        # keep the login email on the profile too, so it shows in the directory
        profile = {**profile, "email": login_email}
        doctor = self._domain.create_doctor(**profile)
        try:
            self._auth.create_user(
                login_email, login_password, role="doctor", doctor_id=doctor.id
            )
        except AuthError as err:  # extremely unlikely after the pre-check
            raise AdminError(str(err)) from err
        return {"doctor": doctor, "login_email": login_email}

    def update_doctor(self, doctor_id: int, changes: dict):
        doctor = self._domain.update_doctor(doctor_id, **changes)
        if doctor is None:
            raise AdminError(f"Doctor {doctor_id} not found.")
        return doctor

    # ----------------------------------------------------------------- #
    # Schedule
    # ----------------------------------------------------------------- #
    def generate_schedule(
        self, doctor_id: int, *, weekdays: list[int], start_time: str, end_time: str,
        slot_minutes: int, weeks: int, start_date: str | None = None,
    ) -> dict:
        """Expand a weekly template into concrete slots. Idempotent: re-running
        with an overlapping range skips slots that already exist."""
        if self._domain.get_doctor(doctor_id) is None:
            raise AdminError(f"Doctor {doctor_id} not found.")
        if not weekdays or any(d < 0 or d > 6 for d in weekdays):
            raise AdminError("Pick at least one valid weekday (0=Mon … 6=Sun).")
        if slot_minutes <= 0 or weeks <= 0:
            raise AdminError("Slot length and number of weeks must be positive.")

        try:
            start_t = datetime.strptime(start_time, "%H:%M").time()
            end_t = datetime.strptime(end_time, "%H:%M").time()
        except ValueError as err:
            raise AdminError("Times must be in HH:MM format.") from err
        if end_t <= start_t:
            raise AdminError("End time must be after start time.")

        begin = date.fromisoformat(start_date) if start_date else date.today()
        wanted = set(weekdays)
        step = timedelta(minutes=slot_minutes)
        created = skipped = 0

        for offset in range(weeks * 7):
            day = begin + timedelta(days=offset)
            if day.weekday() not in wanted:
                continue
            cursor = datetime.combine(day, start_t)
            day_end = datetime.combine(day, end_t)
            while cursor + step <= day_end:
                starts_at = cursor.isoformat()
                if self._domain.slot_exists(doctor_id, starts_at):
                    skipped += 1
                else:
                    self._domain.create_slot(doctor_id, starts_at, slot_minutes)
                    created += 1
                cursor += step

        return {"created": created, "skipped": skipped}

    def list_slots(self, doctor_id: int) -> list[dict]:
        return [
            {
                "slot_id": sl.id, "doctor_id": sl.doctor_id, "starts_at": sl.starts_at,
                "duration_min": sl.duration_min, "is_booked": sl.is_booked,
            }
            for sl in self._domain.list_all_slots(doctor_id)
        ]

    def remove_slot(self, slot_id: int) -> None:
        if not self._domain.delete_slot(slot_id):
            raise AdminError("Slot not found, or it is already booked and can't be removed.")

    # ----------------------------------------------------------------- #
    # Dashboard
    # ----------------------------------------------------------------- #
    def overview(self) -> dict:
        return {
            "doctors": len(self._domain.list_doctors()),
            "patients": len(self._domain.list_patients()),
            "appointments_today": len(self._domain.list_appointments_on(today_iso())),
            "appointments_total": self._domain.count_appointments(),
        }
