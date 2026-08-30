// The API client: composes the feature services into one flat surface.
//
// Pages call `api.<method>()`; methods are bound (arrow fields) so they can be
// passed around as callbacks without losing `this`. This module is the
// composition root of the frontend — `HttpClient` is constructed once here and
// injected into every service.
import type {
  DoctorCreate,
  DoctorUpdate,
  MedicineCreate,
  PatientCreate,
  PatientSignup,
  PrescriptionItem,
  ScheduleTemplate,
} from "@/types";
import { HttpClient } from "@/lib/api/httpClient";
import { AdminService } from "./services/admin";
import { AgentRequest, AgentService } from "./services/agent";
import { AppointmentService, BookRequest } from "./services/appointment";
import { AuthService } from "./services/auth";
import { BillingService } from "./services/billing";
import { DomainService } from "./services/domain";
import { OpsService } from "./services/ops";
import { PharmacyService } from "./services/pharmacy";
import { ReceptionService } from "./services/reception";

export class ApiClient {
  readonly http: HttpClient;
  readonly domain: DomainService;
  readonly appointments: AppointmentService;
  readonly agentSvc: AgentService;
  readonly ops: OpsService;
  readonly authSvc: AuthService;
  readonly adminSvc: AdminService;
  readonly receptionSvc: ReceptionService;
  readonly billingSvc: BillingService;
  readonly pharmacySvc: PharmacyService;

  constructor(http: HttpClient = new HttpClient()) {
    this.http = http;
    this.domain = new DomainService(http);
    this.appointments = new AppointmentService(http);
    this.agentSvc = new AgentService(http);
    this.ops = new OpsService(http);
    this.authSvc = new AuthService(http);
    this.adminSvc = new AdminService(http);
    this.receptionSvc = new ReceptionService(http);
    this.billingSvc = new BillingService(http);
    this.pharmacySvc = new PharmacyService(http);
  }

  setToken = (token: string | null) => this.http.setToken(token);

  // auth
  login = (email: string, password: string) => this.authSvc.login(email, password);
  me = () => this.authSvc.me();
  signup = (b: PatientSignup) => this.authSvc.signup(b);

  // ops
  health = () => this.ops.health();
  audit = () => this.ops.audit();

  // patients
  registerPatient = (b: PatientCreate) => this.domain.registerPatient(b);
  patients = () => this.domain.patients();
  patient = (id: number) => this.domain.patient(id);
  patientAppointments = (id: number) => this.domain.patientAppointments(id);
  patientTreatments = (id: number) => this.domain.patientTreatments(id);
  lookupPatient = (firstName: string, lastName: string) => this.domain.lookupPatient(firstName, lastName);

  // doctors
  doctors = () => this.domain.doctors();
  doctor = (id: number) => this.domain.doctor(id);
  doctorAvailability = (id: number) => this.domain.doctorAvailability(id);
  doctorAppointments = (id: number) => this.domain.doctorAppointments(id);

  // appointments
  book = (b: BookRequest) => this.appointments.book(b);
  appointment = (id: number) => this.appointments.get(id);
  checkIn = (id: number) => this.appointments.checkIn(id);
  recordTreatment = (
    id: number,
    b: { diagnosis: string; prescription: string; notes: string; prescriptions?: PrescriptionItem[] },
  ) => this.appointments.treatment(id, b);
  checkout = (id: number) => this.appointments.checkout(id);
  cancelAppointment = (id: number) => this.appointments.cancel(id);

  // agent
  agent = (b: AgentRequest) => this.agentSvc.chat(b);
  agentHistory = (threadId: string) => this.agentSvc.history(threadId);

  // admin
  adminOverview = () => this.adminSvc.overview();
  createDoctor = (b: DoctorCreate) => this.adminSvc.createDoctor(b);
  updateDoctor = (id: number, b: DoctorUpdate) => this.adminSvc.updateDoctor(id, b);
  doctorSlots = (id: number) => this.adminSvc.doctorSlots(id);
  generateSchedule = (id: number, b: ScheduleTemplate) => this.adminSvc.generateSchedule(id, b);
  deleteSlot = (slotId: number) => this.adminSvc.deleteSlot(slotId);

  // reception
  receptionQueue = () => this.receptionSvc.queue();
  receptionOverview = () => this.receptionSvc.overview();

  // billing
  patientInvoices = (id: number) => this.billingSvc.listForPatient(id);
  invoice = (id: number) => this.billingSvc.get(id);
  payInvoice = (id: number) => this.billingSvc.pay(id);
  voidInvoice = (id: number) => this.billingSvc.void(id);

  // pharmacy
  medicines = () => this.pharmacySvc.medicines();
  addMedicine = (b: MedicineCreate) => this.pharmacySvc.addMedicine(b);
  treatmentPrescriptions = (treatmentId: number) => this.pharmacySvc.treatmentPrescriptions(treatmentId);
}

// Application-wide singleton (composition root for the frontend).
export const api = new ApiClient();

// Factory for server components that need an authenticated request (reads the
// session token from a cookie via next/headers and attaches it per-request).
export function createServerApi(token: string | null): ApiClient {
  return new ApiClient(new HttpClient(undefined, token));
}
