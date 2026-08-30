// Billing: patient invoices + payment actions.
import type { Invoice, InvoiceDetail } from "@/types";
import { BaseService } from "./base";

export class BillingService extends BaseService {
  listForPatient(patientId: number) {
    return this.http.get<Invoice[]>(`/api/patients/${patientId}/invoices`);
  }
  get(invoiceId: number) {
    return this.http.get<InvoiceDetail>(`/api/invoices/${invoiceId}`);
  }
  pay(invoiceId: number) {
    return this.http.post<Invoice>(`/api/invoices/${invoiceId}/pay`);
  }
  void(invoiceId: number) {
    return this.http.post<Invoice>(`/api/invoices/${invoiceId}/void`);
  }
}
