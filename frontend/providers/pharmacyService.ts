// Pharmacy: medicine stock + a treatment's prescriptions.
import type { Medicine, MedicineCreate, Prescription } from "@/models/types";
import { BaseService } from "./baseService";

export class PharmacyService extends BaseService {
  medicines() {
    return this.http.get<Medicine[]>("/api/medicines");
  }
  addMedicine(body: MedicineCreate) {
    return this.http.post<Medicine>("/api/medicines", body);
  }
  treatmentPrescriptions(treatmentId: number) {
    return this.http.get<Prescription[]>(`/api/treatments/${treatmentId}/prescriptions`);
  }
}
