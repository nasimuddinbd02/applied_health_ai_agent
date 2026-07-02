// Wire types mirroring the backend DTOs / entities (models tier).

export interface Patient {
  id: number;
  name: string;
  email: string;
  phone: string;
  gender: string;
  date_of_birth: string | null;
  address: string;
  blood_group: string;
  notes: string;
  created_at: string;
}

export interface Doctor {
  id: number;
  name: string;
  specialty: string;
  email: string;
  phone: string;
  room: string;
  bio: string;
  consultation_fee: number;
}

export interface Slot {
  slot_id: number;
  doctor_id: number;
  starts_at: string;
  duration_min: number;
}

export type AppointmentStatus =
  | "booked"
  | "checked_in"
  | "in_treatment"
  | "completed"
  | "cancelled";

export interface Appointment {
  id: number;
  patient_id: number;
  doctor_id: number;
  slot_id: number | null;
  starts_at: string;
  duration_min: number;
  reason: string;
  status: AppointmentStatus;
  created_at: string;
}

export interface Treatment {
  id: number;
  appointment_id: number;
  patient_id: number;
  doctor_id: number;
  diagnosis: string;
  prescription: string;
  notes: string;
  created_at: string;
}

export interface PatientMatch {
  id: number;
  name: string;
  date_of_birth: string | null;
  gender: string;
}

export interface PatientCreate {
  name: string;
  email?: string;
  phone?: string;
  gender?: string;
  date_of_birth?: string | null;
  address?: string;
  blood_group?: string;
  notes?: string;
}

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  result?: unknown;
}

export interface TranscriptEntry {
  type: string;
  content: string;
}

export interface AgentResponse {
  thread_id: string;
  final_text: string;
  transcript: TranscriptEntry[];
  tool_calls: ToolCall[];
}

export interface ChatMessage {
  id: number;
  thread_id: string;
  patient_id: number | null;
  role: "patient" | "agent";
  content: string;
  created_at: string;
}

export type UserRole = "admin" | "doctor" | "receptionist" | "patient";

export interface AuthUser {
  id: number;
  email: string;
  role: UserRole;
  /** Display name resolved from the linked patient/doctor record ("" for
   * accounts with no linked person, e.g. admin). */
  name: string;
  patient_id: number | null;
  doctor_id: number | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface PatientSignup {
  email: string;
  password: string;
  name: string;
  phone?: string;
  gender?: string;
  date_of_birth?: string | null;
  address?: string;
  blood_group?: string;
}

export interface AuditResponse {
  total_estimated_cost_usd: number;
  total_tokens_in: number;
  total_tokens_out: number;
  count: number;
  events: any[];
}

// --- Admin ---------------------------------------------------------------- #
export interface AdminOverview {
  doctors: number;
  patients: number;
  appointments_today: number;
  appointments_total: number;
}

export interface DoctorCreate {
  name: string;
  specialty?: string;
  room?: string;
  bio?: string;
  phone?: string;
  consultation_fee?: number;
  login_email: string;
  login_password: string;
}

export interface DoctorUpdate {
  name?: string;
  specialty?: string;
  room?: string;
  bio?: string;
  phone?: string;
  consultation_fee?: number;
}

export interface ManagedSlot {
  slot_id: number;
  doctor_id: number;
  starts_at: string;
  duration_min: number;
  is_booked: boolean;
}

export interface ScheduleTemplate {
  weekdays: number[]; // 0=Mon … 6=Sun
  start_time: string; // "HH:MM"
  end_time: string; // "HH:MM"
  slot_minutes: number;
  weeks: number;
  start_date?: string | null;
}

export interface ScheduleResult {
  created: number;
  skipped: number;
}

// --- Reception ------------------------------------------------------------ #
export interface QueueEntry {
  appointment_id: number;
  starts_at: string;
  duration_min: number;
  status: AppointmentStatus;
  reason: string;
  patient_id: number;
  patient_name: string;
  doctor_id: number;
  doctor_name: string;
  room: string;
}

export interface ReceptionOverview {
  total_today: number;
  waiting: number;
  checked_in: number;
  in_treatment: number;
  completed: number;
  active: number;
}

// --- Billing -------------------------------------------------------------- #
export type InvoiceStatus = "draft" | "issued" | "paid" | "void";

export interface Invoice {
  id: number;
  patient_id: number;
  appointment_id: number | null;
  status: InvoiceStatus;
  subtotal: number;
  total: number;
  created_at: string;
  paid_at: string | null;
}

export interface InvoiceLineItem {
  id: number;
  invoice_id: number;
  description: string;
  amount: number;
  kind: "consultation" | "medicine" | "other";
}

export interface InvoiceDetail {
  invoice: Invoice;
  items: InvoiceLineItem[];
}

// --- Pharmacy ------------------------------------------------------------- #
export interface Medicine {
  id: number;
  name: string;
  dosage_form: string;
  unit: string;
  stock_count: number;
  unit_price: number;
}

export interface MedicineCreate {
  name: string;
  dosage_form?: string;
  unit?: string;
  stock_count?: number;
  unit_price?: number;
}

export interface PrescriptionItem {
  medicine_id: number;
  quantity: number;
  frequency?: string;
  duration_days?: number;
}

export interface Prescription {
  id: number;
  medicine_id: number;
  medicine_name: string;
  unit: string;
  quantity: number;
  frequency: string;
  duration_days: number;
  dispensed_at: string | null;
}
