// Appointment booking + lifecycle.
import type {
  Appointment, Doctor, Invoice, Patient, Prescription, PrescriptionItem, Treatment,
} from "@/models/types";
import { BaseService } from "./baseService";

export interface BookRequest {
  patient_id: number;
  doctor_id: number;
  slot_id: number;
  reason?: string;
}

export interface AppointmentDetail {
  appointment: Appointment;
  patient: Patient | null;
  doctor: Doctor | null;
  treatment: Treatment | null;
  invoice: Invoice | null;
  prescriptions: Prescription[];
}

export class AppointmentService extends BaseService {
  book(body: BookRequest) {
    return this.http.post<{ appointment_id: number; status: string }>("/api/appointments", body);
  }
  get(id: number) {
    return this.http.get<AppointmentDetail>(`/api/appointments/${id}`);
  }
  checkIn(id: number) {
    return this.http.post<Appointment>(`/api/appointments/${id}/check-in`);
  }
  treatment(id: number, body: {
    diagnosis: string; prescription: string; notes: string; prescriptions?: PrescriptionItem[];
  }) {
    return this.http.post<Treatment>(`/api/appointments/${id}/treatment`, body);
  }
  checkout(id: number) {
    return this.http.post<Appointment>(`/api/appointments/${id}/checkout`);
  }
  cancel(id: number) {
    return this.http.post<Appointment>(`/api/appointments/${id}/cancel`);
  }
}
