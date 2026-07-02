"""Auth: login, /me, role-gated routes, and invalid-token handling."""

from fastapi.testclient import TestClient

from app.container import container
from app.main import app
from app.seed import DEFAULT_PASSWORD

client = TestClient(app)


def _login(email: str, password: str = DEFAULT_PASSWORD):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return resp


def test_login_success_returns_token_and_user():
    resp = _login("admin@clinic.test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["role"] == "admin"
    assert body["access_token"]


def test_login_wrong_password_rejected():
    resp = _login("admin@clinic.test", "wrong-password")
    assert resp.status_code == 401


def test_me_requires_token():
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user():
    token = _login("admin@clinic.test").json()["access_token"]
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_audit_route_requires_admin_role():
    # "Olivia Bennett" is one of the deterministically seeded patients (seed.py PATIENTS).
    token = _login("olivia@example.com").json()["access_token"]
    resp = client.get("/api/audit", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_audit_route_allows_admin():
    token = _login("admin@clinic.test").json()["access_token"]
    resp = client.get("/api/audit", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_checkin_requires_staff_role():
    patient = container.appointments.register_patient({"name": "Auth Test Patient"})
    doctor = container.appointments.list_doctors()[0]
    slot = container.appointments.doctor_availability(doctor.id)[-1]
    booked = container.appointments.book(patient.id, doctor.id, slot["slot_id"], "x")

    container.auth.create_user(f"authtest{patient.id}@example.com", DEFAULT_PASSWORD, role="patient", patient_id=patient.id)
    token = _login(f"authtest{patient.id}@example.com").json()["access_token"]

    resp = client.post(
        f"/api/appointments/{booked['appointment_id']}/check-in",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_checkin_allows_receptionist():
    patient = container.appointments.register_patient({"name": "Auth Test Patient 2"})
    doctor = container.appointments.list_doctors()[0]
    slot = container.appointments.doctor_availability(doctor.id)[-1]
    booked = container.appointments.book(patient.id, doctor.id, slot["slot_id"], "x")

    token = _login("reception@clinic.test").json()["access_token"]
    resp = client.post(
        f"/api/appointments/{booked['appointment_id']}/check-in",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_patient_signup_creates_patient_and_user():
    resp = client.post("/api/auth/register", json={
        "email": "new.signup@example.com", "password": "s3cret-pw", "name": "New Signup",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["role"] == "patient"
    assert body["user"]["patient_id"] is not None


def test_invalid_token_rejected():
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
