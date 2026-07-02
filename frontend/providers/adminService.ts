// Admin-only operations: doctor onboarding + schedule management.
import type {
  AdminOverview,
  Doctor,
  DoctorCreate,
  DoctorUpdate,
  ManagedSlot,
  ScheduleResult,
  ScheduleTemplate,
} from "@/models/types";
import { BaseService } from "./baseService";

export class AdminService extends BaseService {
  overview() {
    return this.http.get<AdminOverview>("/api/admin/overview");
  }
  createDoctor(body: DoctorCreate) {
    return this.http.post<{ doctor: Doctor; login_email: string }>("/api/admin/doctors", body);
  }
  updateDoctor(id: number, body: DoctorUpdate) {
    return this.http.patch<Doctor>(`/api/admin/doctors/${id}`, body);
  }
  doctorSlots(id: number) {
    return this.http.get<ManagedSlot[]>(`/api/admin/doctors/${id}/slots`);
  }
  generateSchedule(id: number, body: ScheduleTemplate) {
    return this.http.post<ScheduleResult>(`/api/admin/doctors/${id}/schedule`, body);
  }
  deleteSlot(slotId: number) {
    return this.http.del<{ deleted: number }>(`/api/admin/slots/${slotId}`);
  }
}
