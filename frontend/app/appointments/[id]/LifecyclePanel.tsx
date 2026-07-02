"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LogIn, LogOut, Ban, Check, Stethoscope, Pill, Plus, X } from "lucide-react";
import { api } from "@/providers/apiProvider";
import { useAuth } from "../../_auth/AuthContext";
import type { AppointmentStatus, Medicine, PrescriptionItem } from "@/models/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const STEPS = ["booked", "checked_in", "in_treatment", "completed"] as const;
const STEP_LABEL: Record<string, string> = {
  booked: "Scheduled", checked_in: "Checked in", in_treatment: "In treatment", completed: "Completed",
};

interface RxRow { medicine_id: number | ""; quantity: string; frequency: string; duration_days: string }
const emptyRow: RxRow = { medicine_id: "", quantity: "1", frequency: "", duration_days: "" };

export default function LifecyclePanel({ appointmentId, status }: {
  appointmentId: number; status: AppointmentStatus;
}) {
  const router = useRouter();
  const { loading: authLoading } = useAuth();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [tx, setTx] = useState({ diagnosis: "", prescription: "", notes: "" });
  const [rows, setRows] = useState<RxRow[]>([]);
  const [medicines, setMedicines] = useState<Medicine[]>([]);

  // Load the medicine catalogue for the prescription builder (auth-gated).
  useEffect(() => {
    if (authLoading || status !== "checked_in") return;
    api.medicines().then(setMedicines).catch(() => setMedicines([]));
  }, [authLoading, status]);

  async function run(fn: () => Promise<unknown>) {
    setError("");
    setBusy(true);
    try {
      await fn();
      router.refresh();
    } catch (err: any) {
      setError(err.message || "Action failed");
    } finally {
      setBusy(false);
    }
  }

  function saveTreatment() {
    const prescriptions: PrescriptionItem[] = rows
      .filter((r) => r.medicine_id !== "" && Number(r.quantity) > 0)
      .map((r) => ({
        medicine_id: Number(r.medicine_id),
        quantity: Number(r.quantity),
        frequency: r.frequency,
        duration_days: r.duration_days ? Number(r.duration_days) : 0,
      }));
    return run(() => api.recordTreatment(appointmentId, { ...tx, prescriptions }));
  }

  function setRow(i: number, patch: Partial<RxRow>) {
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  return (
    <Card>
      <CardHeader><CardTitle>Workflow</CardTitle></CardHeader>
      <CardContent className="space-y-5">
        <Stepper status={status} />

        <div className="flex flex-wrap gap-2">
          {status === "booked" && (
            <Button onClick={() => run(() => api.checkIn(appointmentId))} disabled={busy}>
              <LogIn className="h-4 w-4" /> Check in
            </Button>
          )}
          {status === "in_treatment" && (
            <Button onClick={() => run(() => api.checkout(appointmentId))} disabled={busy}>
              <LogOut className="h-4 w-4" /> Check out
            </Button>
          )}
          {["booked", "checked_in"].includes(status) && (
            <Button variant="outline" onClick={() => run(() => api.cancelAppointment(appointmentId))} disabled={busy}
              className="text-destructive hover:text-destructive">
              <Ban className="h-4 w-4" /> Cancel
            </Button>
          )}
        </div>

        {status === "checked_in" && (
          <div className="border-t pt-5 space-y-4">
            <h3 className="flex items-center gap-2 text-sm font-medium text-slate-700">
              <Stethoscope className="h-4 w-4 text-brand" /> Doctor — record treatment
            </h3>
            <div className="grid gap-3">
              <div className="grid gap-2">
                <Label htmlFor="dx">Diagnosis</Label>
                <Input id="dx" placeholder="e.g. Hypertension" value={tx.diagnosis}
                  onChange={(e) => setTx({ ...tx, diagnosis: e.target.value })} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="rx">Prescription notes (free text)</Label>
                <Input id="rx" placeholder="e.g. rest, fluids" value={tx.prescription}
                  onChange={(e) => setTx({ ...tx, prescription: e.target.value })} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="notes">Notes</Label>
                <textarea id="notes" placeholder="Any follow-up notes…" value={tx.notes}
                  onChange={(e) => setTx({ ...tx, notes: e.target.value })}
                  className="flex min-h-[4.5rem] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2" />
              </div>
            </div>

            {/* Structured prescriptions (dispensed from pharmacy stock) */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="flex items-center gap-1.5"><Pill className="h-4 w-4 text-brand" /> Dispense medicines</Label>
                <Button type="button" variant="outline" size="sm" disabled={medicines.length === 0}
                  onClick={() => setRows((r) => [...r, { ...emptyRow }])}>
                  <Plus className="h-4 w-4" /> Add
                </Button>
              </div>
              {medicines.length === 0 && (
                <p className="text-xs text-slate-400">No medicines in stock, or you don't have access.</p>
              )}
              {rows.map((row, i) => (
                <div key={i} className="flex flex-wrap items-end gap-2 rounded-lg border border-slate-200 p-2.5">
                  <div className="grid gap-1 min-w-[10rem] flex-1">
                    <Label className="text-xs text-slate-400">Medicine</Label>
                    <select value={row.medicine_id}
                      onChange={(e) => setRow(i, { medicine_id: e.target.value ? Number(e.target.value) : "" })}
                      className="h-9 rounded-md border border-input bg-background px-2 text-sm">
                      <option value="">Select…</option>
                      {medicines.map((m) => (
                        <option key={m.id} value={m.id} disabled={m.stock_count <= 0}>
                          {m.name} {m.unit} ({m.stock_count} left)
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="grid gap-1 w-16">
                    <Label className="text-xs text-slate-400">Qty</Label>
                    <Input className="h-9" type="number" min="1" value={row.quantity}
                      onChange={(e) => setRow(i, { quantity: e.target.value })} />
                  </div>
                  <div className="grid gap-1 w-32">
                    <Label className="text-xs text-slate-400">Frequency</Label>
                    <Input className="h-9" placeholder="twice daily" value={row.frequency}
                      onChange={(e) => setRow(i, { frequency: e.target.value })} />
                  </div>
                  <div className="grid gap-1 w-20">
                    <Label className="text-xs text-slate-400">Days</Label>
                    <Input className="h-9" type="number" min="0" value={row.duration_days}
                      onChange={(e) => setRow(i, { duration_days: e.target.value })} />
                  </div>
                  <Button type="button" variant="ghost" size="icon" className="h-9 w-9 text-slate-400"
                    onClick={() => setRows((rs) => rs.filter((_, idx) => idx !== i))}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>

            <Button onClick={saveTreatment} disabled={busy || !tx.diagnosis}>
              <Check className="h-4 w-4" /> Save treatment & start
            </Button>
          </div>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}

function Stepper({ status }: { status: AppointmentStatus }) {
  if (status === "cancelled") {
    return (
      <div className="flex items-center gap-2 rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-600">
        <Ban className="h-4 w-4" /> This appointment was cancelled.
      </div>
    );
  }
  const idx = STEPS.indexOf(status as (typeof STEPS)[number]);
  return (
    <div className="flex items-center">
      {STEPS.map((s, i) => {
        const done = i <= idx;
        return (
          <div key={s} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center gap-1.5">
              <span className={cn(
                "grid h-8 w-8 place-items-center rounded-full text-xs font-semibold transition",
                done ? "bg-brand text-white" : "bg-slate-100 text-slate-400",
              )}>
                {done ? <Check className="h-4 w-4" /> : i + 1}
              </span>
              <span className={cn("text-[11px] whitespace-nowrap", done ? "text-slate-700 font-medium" : "text-slate-400")}>
                {STEP_LABEL[s]}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={cn("mx-2 mb-5 h-0.5 flex-1", i < idx ? "bg-brand" : "bg-slate-200")} />
            )}
          </div>
        );
      })}
    </div>
  );
}
