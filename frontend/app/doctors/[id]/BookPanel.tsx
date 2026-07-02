"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { CalendarPlus, CheckCircle2, CalendarX, UserRound } from "lucide-react";
import { api } from "@/providers/apiProvider";
import { useAuth } from "../../_auth/AuthContext";
import IdentityPicker, { type PatientIdentity } from "../../_components/IdentityPicker";
import type { Slot } from "@/models/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export default function BookPanel({ doctorId, slots }: { doctorId: number; slots: Slot[] }) {
  const { user, loading: authLoading } = useAuth();
  const [identity, setIdentity] = useState<PatientIdentity | null>(null);
  const [reason, setReason] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [result, setResult] = useState<{ id: number } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Logged-in patients skip the identity step entirely — we already know them.
  useEffect(() => {
    if (user?.role === "patient" && user.patient_id) {
      setIdentity({ id: user.patient_id, label: user.name || `Patient #${user.patient_id}` });
    }
  }, [user]);

  // Group open slots by calendar day for the date strip.
  const groups = useMemo(() => {
    const g: Record<string, Slot[]> = {};
    for (const s of slots) (g[s.starts_at.slice(0, 10)] ??= []).push(s);
    return g;
  }, [slots]);
  const days = useMemo(() => Object.keys(groups).sort(), [groups]);

  useEffect(() => {
    if (days.length > 0 && (!selectedDay || !days.includes(selectedDay))) setSelectedDay(days[0]);
  }, [days, selectedDay]);

  const daySlots = selectedDay ? groups[selectedDay] ?? [] : [];
  const morning = daySlots.filter((s) => s.starts_at.slice(11, 13) < "12");
  const afternoon = daySlots.filter((s) => s.starts_at.slice(11, 13) >= "12");
  const selectedSlot = slots.find((s) => s.slot_id === selected);

  async function book() {
    setError("");
    if (!identity || !selected) return;
    setLoading(true);
    try {
      const res = await api.book({ patient_id: identity.id, doctor_id: doctorId, slot_id: selected, reason });
      setResult({ id: res.appointment_id });
    } catch (err: any) {
      setError(err.message || "Booking failed");
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    return (
      <Card className="border-emerald-200 bg-emerald-50/60">
        <CardContent className="p-6 flex items-start gap-3">
          <CheckCircle2 className="h-6 w-6 text-emerald-600 shrink-0" />
          <div>
            <p className="font-semibold text-emerald-900">
              You're booked{identity ? `, ${identity.label.split(" ")[0]}` : ""} — appointment #{result.id}
            </p>
            <p className="text-sm text-emerald-700/80">We've reserved your slot. You can view the details any time.</p>
            <Link href={`/appointments/${result.id}`} className={cn(buttonVariants({ size: "sm" }), "mt-3")}>
              View appointment
            </Link>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarPlus className="h-5 w-5 text-brand" /> Book an appointment
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Step 1 — who is booking */}
        <section className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Step 1 · Your details</p>
          {identity ? (
            <div className="flex items-center gap-3 rounded-xl border border-teal-200 bg-teal-50/50 px-4 py-3">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand text-sm font-semibold text-white">
                {identity.label.charAt(0).toUpperCase()}
              </span>
              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-medium text-slate-800">Booking as {identity.label}</p>
                <p className="text-xs text-slate-400">Patient #{identity.id}</p>
              </div>
              {!user && (
                <button
                  type="button"
                  onClick={() => setIdentity(null)}
                  className="text-xs text-slate-500 hover:text-brand hover:underline"
                >
                  Not you?
                </button>
              )}
            </div>
          ) : authLoading ? (
            <p className="text-sm text-slate-400">Checking your account…</p>
          ) : (
            <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
              <div className="mb-3 flex items-center gap-2 text-sm text-slate-600">
                <UserRound className="h-4 w-4 text-brand" /> Tell us who you are — your name is enough.
              </div>
              <IdentityPicker onIdentified={setIdentity} />
            </div>
          )}
        </section>

        {/* Step 2 — pick a time */}
        <section className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Step 2 · Pick a time</p>
          {slots.length === 0 ? (
            <div className="flex items-center gap-2 rounded-lg border border-dashed border-slate-200 p-4 text-sm text-slate-400">
              <CalendarX className="h-4 w-4" /> No open slots for this doctor right now — check back soon.
            </div>
          ) : (
            <>
              <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1">
                {days.map((day) => {
                  const d = new Date(day + "T00:00:00");
                  const isSelected = day === selectedDay;
                  return (
                    <button
                      key={day}
                      type="button"
                      onClick={() => { setSelectedDay(day); setSelected(null); }}
                      className={`flex w-16 shrink-0 flex-col items-center rounded-xl border px-2 py-2 transition ${
                        isSelected
                          ? "border-brand bg-brand text-white shadow-sm"
                          : "border-slate-200 bg-white text-slate-700 hover:border-brand/40"
                      }`}
                    >
                      <span className={`text-[10px] font-semibold uppercase tracking-wide ${isSelected ? "text-teal-100" : "text-slate-400"}`}>
                        {d.toLocaleDateString(undefined, { weekday: "short" })}
                      </span>
                      <span className="text-lg font-bold leading-tight">{d.getDate()}</span>
                      <span className={`text-[10px] ${isSelected ? "text-teal-100" : "text-slate-400"}`}>
                        {d.toLocaleDateString(undefined, { month: "short" })}
                      </span>
                    </button>
                  );
                })}
              </div>

              {[{ label: "Morning", items: morning }, { label: "Afternoon", items: afternoon }]
                .filter((g) => g.items.length > 0)
                .map((g) => (
                  <div key={g.label}>
                    <p className="mb-2 text-xs font-medium text-slate-400">{g.label}</p>
                    <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-6">
                      {g.items.map((s) => (
                        <button
                          key={s.slot_id}
                          type="button"
                          onClick={() => setSelected(s.slot_id)}
                          className={cn(
                            "rounded-lg border py-2 text-center text-sm font-medium tabular-nums transition",
                            selected === s.slot_id
                              ? "border-brand bg-brand text-white shadow-sm"
                              : "border-slate-200 bg-white text-slate-700 hover:border-brand/50",
                          )}
                        >
                          {new Date(s.starts_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
            </>
          )}
        </section>

        {/* Step 3 — reason + confirm */}
        <section className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Step 3 · Confirm</p>
          <div className="grid gap-2">
            <Label htmlFor="b-reason">Reason for visit <span className="text-slate-400 font-normal">(optional)</span></Label>
            <Input
              id="b-reason" value={reason} onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. annual check-up"
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={book} disabled={loading || !identity || !selected}>
              {loading ? "Booking…" : "Confirm booking"}
            </Button>
            {selectedSlot && (
              <p className="text-sm text-slate-500">
                {new Date(selectedSlot.starts_at).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}
                {" · "}
                {new Date(selectedSlot.starts_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
              </p>
            )}
          </div>
          {!identity && !authLoading && (
            <p className="text-xs text-slate-400">Complete step 1 so we know who the appointment is for.</p>
          )}
        </section>
      </CardContent>
    </Card>
  );
}
