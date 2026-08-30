// Patient + doctor reads/writes.
import type {
  Appointment,
  Doctor,
  Patient,
  PatientCreate,
  PatientMatch,
  Slot,
  Treatment,
} from "@/types";
import { BaseService } from "./base";

export class DomainService extends BaseService {
  // Patients
  registerPatient(body: PatientCreate) {
    return this.http.post<Patient>("/api/patients", body);
  }
  patients() {
    return this.http.get<Patient[]>("/api/patients");
  }
  patient(id: number) {
    return this.http.get<Patient>(`/api/patients/${id}`);
  }
  patientAppointments(id: number) {
    return this.http.get<Appointment[]>(`/api/patients/${id}/appointments`);
  }
  patientTreatments(id: number) {
    return this.http.get<Treatment[]>(`/api/patients/${id}/treatments`);
  }
  lookupPatient(firstName: string, lastName: string) {
    const q = new URLSearchParams({ first_name: firstName, last_name: lastName });
    return this.http.get<PatientMatch[]>(`/api/patients/lookup?${q}`);
  }

  // Doctors
  doctors() {
    return this.http.get<Doctor[]>("/api/doctors");
  }
  doctor(id: number) {
    return this.http.get<Doctor>(`/api/doctors/${id}`);
  }
  doctorAvailability(id: number) {
    return this.http.get<Slot[]>(`/api/doctors/${id}/availability`);
  }
  doctorAppointments(id: number) {
    return this.http.get<Appointment[]>(`/api/doctors/${id}/appointments`);
  }
}
