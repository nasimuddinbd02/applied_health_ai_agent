import Link from "next/link";
import {
  CalendarPlus, CalendarDays, FileText, Phone, Droplet, User, Stethoscope, ChevronRight,
} from "lucide-react";
import { api } from "@/providers/apiProvider";
import { Formatter } from "@/lib/format";
import type { Doctor } from "@/models/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { InitialsAvatar, StatusBadge, EmptyState, MetaItem } from "../../_components/ui";
import PatientInvoices from "./PatientInvoices";
import { cn } from "@/lib/utils";

export default async function PatientPage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const [patient, appointments, treatments, doctors] = await Promise.all([
    api.patient(id),
    api.patientAppointments(id).catch(() => []),
    api.patientTreatments(id).catch(() => []),
    api.doctors().catch(() => []),
  ]);
  const docName = (did: number) => doctors.find((d: Doctor) => d.id === did)?.name || `Doctor #${did}`;

  return (
    <div className="space-y-6">
      {/* Identity header */}
      <Card>
        <CardContent className="p-6 flex items-center gap-4">
          <InitialsAvatar name={patient.name} className="h-16 w-16 text-xl" />
          <div className="min-w-0">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">{patient.name}</h1>
            <p className="text-sm text-slate-400">Patient #{patient.id}</p>
            <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
              <MetaItem icon={User}>{patient.gender || "—"}</MetaItem>
              <MetaItem icon={Droplet}>{patient.blood_group || "—"}</MetaItem>
              {patient.phone && <MetaItem icon={Phone}>{patient.phone}</MetaItem>}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Appointments */}
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="flex items-center gap-2">
            <CalendarDays className="h-5 w-5 text-brand" /> Appointments
          </CardTitle>
          <Link href="/doctors" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
            <CalendarPlus className="h-4 w-4" /> Book new
          </Link>
        </CardHeader>
        <CardContent>
          {appointments.length === 0 ? (
            <EmptyState icon={CalendarDays} title="No appointments yet" description="Book a visit to get started." />
          ) : (
            <ul className="divide-y divide-slate-100">
              {appointments.map((a) => (
                <li key={a.id}>
                  <Link href={`/appointments/${a.id}`} className="flex items-center gap-3 py-3 group">
                    <span className="grid h-9 w-9 place-items-center rounded-lg bg-slate-100 text-slate-500">
                      <Stethoscope className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-slate-800 group-hover:text-brand">{docName(a.doctor_id)}</p>
                      <p className="text-xs text-slate-400">{Formatter.dateTime(a.starts_at)} · {a.reason || "—"}</p>
                    </div>
                    <StatusBadge status={a.status} />
                    <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-slate-400" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Invoices (client-fetched — auth-gated) */}
      <PatientInvoices patientId={id} />

      {/* Treatment history */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-brand" /> Treatment history
          </CardTitle>
        </CardHeader>
        <CardContent>
          {treatments.length === 0 ? (
            <EmptyState icon={FileText} title="No treatments recorded yet" />
          ) : (
            <ol className="relative space-y-4 border-l border-slate-200 pl-5">
              {treatments.map((t) => (
                <li key={t.id} className="relative">
                  <span className="absolute -left-[1.6rem] top-1.5 h-3 w-3 rounded-full border-2 border-white bg-brand" />
                  <div className="rounded-lg border border-slate-200 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium text-slate-900">{t.diagnosis || "—"}</p>
                      <span className="text-xs text-slate-400">{Formatter.dateTime(t.created_at)}</span>
                    </div>
                    <p className="text-sm text-slate-500">By {docName(t.doctor_id)}</p>
                    {t.prescription && (
                      <p className="mt-2 text-sm"><span className="text-slate-400">Rx:</span> {t.prescription}</p>
                    )}
                    {t.notes && <p className="mt-1 text-sm text-slate-500">{t.notes}</p>}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
