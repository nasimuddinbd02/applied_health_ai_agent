import Link from "next/link";
import { Clock, Stethoscope, User, FileText, ClipboardCheck, Receipt, ChevronRight, Pill } from "lucide-react";
import { api } from "@/lib/api/client";
import { Formatter } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge, InvoiceStatusBadge, MetaItem } from "@/components/common/ui";
import LifecyclePanel from "@/components/appointments/LifecyclePanel";

export default async function AppointmentPage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const data = await api.appointment(id);
  const { appointment, patient, doctor, treatment, invoice, prescriptions } = data;

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between gap-4">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">Appointment #{appointment.id}</h1>
            <StatusBadge status={appointment.status} />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <MetaItem icon={Clock}>{Formatter.dateTime(appointment.starts_at)} · {appointment.duration_min} min</MetaItem>
            <MetaItem icon={Stethoscope}>{doctor?.name} ({doctor?.specialty})</MetaItem>
            <MetaItem icon={User}>
              <Link href={`/patients/${patient?.id}`} className="text-brand hover:underline">{patient?.name}</Link>
            </MetaItem>
            <MetaItem icon={FileText}>{appointment.reason || "—"}</MetaItem>
          </div>
        </CardContent>
      </Card>

      {treatment && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ClipboardCheck className="h-5 w-5 text-brand" /> Treatment record
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div><span className="text-slate-400">Diagnosis:</span> <span className="font-medium">{treatment.diagnosis || "—"}</span></div>
            <div><span className="text-slate-400">Prescription:</span> {treatment.prescription || "—"}</div>
            {treatment.notes && <div><span className="text-slate-400">Notes:</span> {treatment.notes}</div>}

            {prescriptions.length > 0 && (
              <div className="pt-3 border-t mt-3">
                <p className="mb-2 flex items-center gap-1.5 font-medium text-slate-700">
                  <Pill className="h-4 w-4 text-brand" /> Dispensed medicines
                </p>
                <ul className="space-y-1.5">
                  {prescriptions.map((rx) => (
                    <li key={rx.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                      <span className="font-medium text-slate-800">
                        {rx.medicine_name} {rx.unit && <span className="text-slate-400 font-normal">{rx.unit}</span>}
                      </span>
                      <span className="text-slate-500 text-xs">
                        ×{rx.quantity}{rx.frequency && ` · ${rx.frequency}`}{rx.duration_days > 0 && ` · ${rx.duration_days} days`}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {invoice && (
        <Link href={`/invoices/${invoice.id}`} className="block group">
          <Card className="transition group-hover:border-brand/40 group-hover:shadow-md">
            <CardContent className="p-4 flex items-center gap-3">
              <span className="grid h-9 w-9 place-items-center rounded-lg bg-brand/10 text-brand">
                <Receipt className="h-4 w-4" />
              </span>
              <div className="flex-1">
                <p className="font-medium text-slate-800 group-hover:text-brand">Invoice #{invoice.id}</p>
                <p className="text-xs text-slate-400">{Formatter.usd(invoice.total, 2)}</p>
              </div>
              <InvoiceStatusBadge status={invoice.status} />
              <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-slate-400" />
            </CardContent>
          </Card>
        </Link>
      )}

      <LifecyclePanel appointmentId={id} status={appointment.status} />
    </div>
  );
}
