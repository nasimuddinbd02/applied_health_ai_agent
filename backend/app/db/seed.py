"""Synthetic hospital seed data.

Run with ``python -m app.db.seed``. Deterministic (fixed RNG seed). Seeds
doctors, two weeks of availability, patients, and a few completed appointments
with treatment history.

**This DELETES every row in every table first**, so the result is reproducible.
Never run it against a database you care about. To create the schema without
touching data, use ``python -m app.db.session`` instead — that is what the
container and Kubernetes init steps call.
"""

import random
from datetime import datetime, timedelta

from sqlmodel import Session, delete

from app.db.session import database, engine, init_db
from app.models import (
    Appointment,
    AvailabilitySlot,
    ChatMessage,
    Doctor,
    Medicine,
    Patient,
    Treatment,
    User,
)
from app.repositories.user import UserRepository
from app.services.auth import AuthService

RNG = random.Random(42)

DEFAULT_PASSWORD = "clinic123"

DOCTORS = [
    ("Dr. Sarah Chen", "Cardiology", "Room 201", "Consultant cardiologist, 15 years' experience.", 120.0),
    ("Dr. James Okafor", "Dermatology", "Room 105", "Specialist in skin conditions and allergies.", 90.0),
    ("Dr. Priya Nair", "Pediatrics", "Room 110", "Caring for children from newborn to teens.", 80.0),
    ("Dr. Marco Rossi", "Orthopedics", "Room 305", "Bone, joint and sports-injury specialist.", 110.0),
    ("Dr. Aisha Khan", "Neurology", "Room 410", "Headache, migraine and nerve disorders.", 130.0),
    ("Dr. Tom Becker", "General Medicine", "Room 101", "Family medicine and routine check-ups.", 70.0),
]

PATIENTS = [
    ("Olivia Bennett", "female", "O+"),
    ("Liam Carter", "male", "A-"),
    ("Emma Davis", "female", "B+"),
    ("Noah Evans", "male", "AB+"),
    ("Ava Foster", "female", "O-"),
    ("William Grant", "male", "A+"),
    ("Sophia Hughes", "female", "B-"),
    ("Mason Irving", "male", "O+"),
]

MEDICINES = [
    ("Amlodipine", "tablet", "5mg", 120, 0.15),
    ("Amoxicillin", "capsule", "500mg", 80, 0.30),
    ("Ibuprofen", "tablet", "400mg", 200, 0.10),
    ("Paracetamol", "tablet", "500mg", 300, 0.05),
    ("Hydrocortisone", "cream", "1%", 40, 2.50),
    ("Salbutamol", "inhaler", "100mcg", 25, 6.00),
    ("Omeprazole", "capsule", "20mg", 8, 0.40),  # intentionally low stock
    ("Metformin", "tablet", "500mg", 150, 0.12),
]

DIAGNOSES = [
    ("Hypertension", "Amlodipine 5mg once daily", "Monitor blood pressure weekly."),
    ("Mild eczema", "Hydrocortisone 1% cream twice daily", "Avoid known irritants."),
    ("Seasonal flu", "Rest, fluids, paracetamol as needed", "Return if fever persists >3 days."),
    ("Sprained ankle", "Ibuprofen 400mg, rest and ice", "Follow-up X-ray in 2 weeks."),
    ("Tension headache", "Hydration and stress management", "Keep a headache diary."),
]


def seed() -> dict:
    init_db()
    with Session(engine, expire_on_commit=False) as s:
        from app.models import (
            AuditEvent,
            Invoice,
            InvoiceLineItem,
            Prescription,
            RefillRequest,
        )
        # Children first so re-seeding is clean regardless of FK enforcement.
        for model in (
            Prescription, InvoiceLineItem, Invoice, RefillRequest, ChatMessage,
            Treatment, Appointment, AvailabilitySlot, Patient, Doctor, User,
            Medicine, AuditEvent,
        ):
            s.exec(delete(model))
        s.commit()

        # Pharmacy stock
        for name, form, unit, stock, price in MEDICINES:
            s.add(Medicine(name=name, dosage_form=form, unit=unit, stock_count=stock, unit_price=price))
        s.commit()

        # Doctors
        doctors: list[Doctor] = []
        for i, (name, spec, room, bio, fee) in enumerate(DOCTORS):
            d = Doctor(
                name=name, specialty=spec, room=room, bio=bio, consultation_fee=fee,
                email=f"{name.split()[-1].lower()}@cityhospital.example",
                phone=f"555-02{i:02d}",
            )
            s.add(d)
            doctors.append(d)
        s.commit()

        # Two weeks of availability slots (Mon-Fri, 4 slots/day) per doctor
        base = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        for d in doctors:
            for day in range(14):
                day_dt = base + timedelta(days=day)
                if day_dt.weekday() >= 5:  # skip weekends
                    continue
                for hour in range(4):
                    starts = day_dt + timedelta(hours=hour * 2)
                    s.add(AvailabilitySlot(
                        doctor_id=d.id, starts_at=starts.isoformat(), duration_min=30, is_booked=False
                    ))
        s.commit()

        # Patients
        patients: list[Patient] = []
        for i, (name, gender, blood) in enumerate(PATIENTS):
            p = Patient(
                name=name, gender=gender, blood_group=blood,
                email=f"{name.split()[0].lower()}@example.com",
                phone=f"555-03{i:02d}",
                date_of_birth=(datetime.now() - timedelta(days=RNG.randint(7000, 25000))).date().isoformat(),
                address=f"{100 + i} Maple Avenue",
            )
            s.add(p)
            patients.append(p)
        s.commit()

        # A few completed appointments + treatment history (in the past)
        completed = 0
        for i in range(5):
            patient = patients[i]
            doctor = doctors[i % len(doctors)]
            past = (base - timedelta(days=7 + i)).replace(hour=10).isoformat()
            appt = Appointment(
                patient_id=patient.id, doctor_id=doctor.id, slot_id=None,
                starts_at=past, duration_min=30,
                reason="Follow-up consultation", status="completed",
            )
            s.add(appt)
            s.commit()
            s.refresh(appt)
            dx, rx, note = DIAGNOSES[i % len(DIAGNOSES)]
            s.add(Treatment(
                appointment_id=appt.id, patient_id=patient.id, doctor_id=doctor.id,
                diagnosis=dx, prescription=rx, notes=note,
            ))
            completed += 1
        s.commit()

        # One upcoming booked appointment for patient 1 (reserve a real slot)
        from sqlmodel import select
        slot = s.exec(
            select(AvailabilitySlot).where(AvailabilitySlot.doctor_id == doctors[0].id)
        ).first()
        if slot:
            slot.is_booked = True
            s.add(slot)
            s.add(Appointment(
                patient_id=patients[0].id, doctor_id=doctors[0].id, slot_id=slot.id,
                starts_at=slot.starts_at, duration_min=slot.duration_min,
                reason="Chest pain check-up", status="booked",
            ))
            s.commit()

        counts = {"doctors": len(doctors), "patients": len(patients), "treatments": completed}

        # Login users: one admin/receptionist, one login per doctor, one per patient.
        from app.core.config import settings

        auth = AuthService(settings, UserRepository(database))
        auth.create_user("admin@clinic.test", DEFAULT_PASSWORD, role="admin")
        auth.create_user("reception@clinic.test", DEFAULT_PASSWORD, role="receptionist")
        for d in doctors:
            auth.create_user(d.email, DEFAULT_PASSWORD, role="doctor", doctor_id=d.id)
        for p in patients:
            auth.create_user(p.email, DEFAULT_PASSWORD, role="patient", patient_id=p.id)
        counts["users"] = 2 + len(doctors) + len(patients)

    print("Seeded:", counts)
    print(f"Default password for all seeded users: {DEFAULT_PASSWORD}")
    print("Login as: admin@clinic.test / reception@clinic.test / any doctor or patient email")
    return counts


if __name__ == "__main__":
    seed()
