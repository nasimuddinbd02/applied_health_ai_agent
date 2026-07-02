"use client";
import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, CalendarPlus, Trash2 } from "lucide-react";
import { api } from "@/providers/apiProvider";
import type { Doctor, ManagedSlot } from "@/models/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";

const WEEKDAYS = [
  { label: "Mon", value: 0 }, { label: "Tue", value: 1 }, { label: "Wed", value: 2 },
  { label: "Thu", value: 3 }, { label: "Fri", value: 4 }, { label: "Sat", value: 5 },
  { label: "Sun", value: 6 },
];

export default function AdminDoctorDetail() {
  const params = useParams();
  const id = Number(params.id);
  const [doctor, setDoctor] = useState<Doctor | null>(null);
  const [slots, setSlots] = useState<ManagedSlot[] | null>(null);

  const loadSlots = useCallback(async () => {
    setSlots(await api.doctorSlots(id));
  }, [id]);

  useEffect(() => {
    api.doctor(id).then(setDoctor);
    loadSlots();
  }, [id, loadSlots]);

  return (
    <div className="space-y-6 max-w-5xl">
      <Link href="/admin/doctors" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-brand">
        <ArrowLeft className="h-4 w-4" /> Back to doctors
      </Link>

      <div>
        <h1 className="text-2xl font-bold">{doctor ? doctor.name : <Skeleton className="h-8 w-48 inline-block" />}</h1>
        <p className="text-slate-500">{doctor?.specialty}</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {doctor && <ProfileCard doctor={doctor} onSaved={setDoctor} />}
        <ScheduleBuilder doctorId={id} onGenerated={loadSlots} />
      </div>

      <SlotsCard slots={slots} onDelete={loadSlots} />
    </div>
  );
}

function ProfileCard({ doctor, onSaved }: { doctor: Doctor; onSaved: (d: Doctor) => void }) {
  const [form, setForm] = useState({
    name: doctor.name, specialty: doctor.specialty, room: doctor.room,
    phone: doctor.phone, bio: doctor.bio, consultation_fee: String(doctor.consultation_fee),
  });
  const [saving, setSaving] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await api.updateDoctor(doctor.id, {
        name: form.name, specialty: form.specialty, room: form.room,
        phone: form.phone, bio: form.bio,
        consultation_fee: form.consultation_fee ? Number(form.consultation_fee) : 0,
      });
      onSaved(updated);
      toast.success("Profile updated");
    } catch (err: any) {
      toast.error("Update failed", { description: err.message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={save} className="space-y-3">
          <div className="grid gap-2">
            <Label htmlFor="p-name">Name</Label>
            <Input id="p-name" value={form.name} onChange={set("name")} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="p-spec">Specialty</Label>
              <Input id="p-spec" value={form.specialty} onChange={set("specialty")} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="p-room">Room</Label>
              <Input id="p-room" value={form.room} onChange={set("room")} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="p-phone">Phone</Label>
              <Input id="p-phone" value={form.phone} onChange={set("phone")} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="p-fee">Fee ($)</Label>
              <Input id="p-fee" type="number" min="0" value={form.consultation_fee} onChange={set("consultation_fee")} />
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="p-bio">Bio</Label>
            <Input id="p-bio" value={form.bio} onChange={set("bio")} />
          </div>
          <Button type="submit" disabled={saving} size="sm">
            {saving ? "Saving…" : "Save profile"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function ScheduleBuilder({ doctorId, onGenerated }: { doctorId: number; onGenerated: () => void }) {
  const [weekdays, setWeekdays] = useState<number[]>([0, 1, 2, 3, 4]);
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("17:00");
  const [slotMinutes, setSlotMinutes] = useState("30");
  const [weeks, setWeeks] = useState("2");
  const [startDate, setStartDate] = useState("");
  const [busy, setBusy] = useState(false);

  function toggle(day: number) {
    setWeekdays((w) => (w.includes(day) ? w.filter((d) => d !== day) : [...w, day]));
  }

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await api.generateSchedule(doctorId, {
        weekdays, start_time: startTime, end_time: endTime,
        slot_minutes: Number(slotMinutes), weeks: Number(weeks),
        start_date: startDate || null,
      });
      toast.success("Schedule generated", {
        description: `${res.created} slot(s) created, ${res.skipped} already existed.`,
      });
      onGenerated();
    } catch (err: any) {
      toast.error("Could not generate schedule", { description: err.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader><CardTitle>Build schedule</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={generate} className="space-y-4">
          <div className="grid gap-2">
            <Label>Working days</Label>
            <div className="flex flex-wrap gap-3">
              {WEEKDAYS.map((d) => (
                <label key={d.value} className="flex items-center gap-1.5 text-sm cursor-pointer">
                  <Checkbox checked={weekdays.includes(d.value)} onCheckedChange={() => toggle(d.value)} />
                  {d.label}
                </label>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="s-start">Start time</Label>
              <Input id="s-start" type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="s-end">End time</Label>
              <Input id="s-end" type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="s-len">Slot (min)</Label>
              <Input id="s-len" type="number" min="5" step="5" value={slotMinutes} onChange={(e) => setSlotMinutes(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="s-weeks">Weeks</Label>
              <Input id="s-weeks" type="number" min="1" value={weeks} onChange={(e) => setWeeks(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="s-from">From</Label>
              <Input id="s-from" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
          </div>
          <Button type="submit" disabled={busy || weekdays.length === 0} size="sm">
            <CalendarPlus className="h-4 w-4" /> {busy ? "Generating…" : "Generate slots"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function SlotsCard({ slots, onDelete }: { slots: ManagedSlot[] | null; onDelete: () => void }) {
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  async function remove(slotId: number) {
    try {
      await api.deleteSlot(slotId);
      toast.success("Slot removed");
      onDelete();
    } catch (err: any) {
      toast.error("Could not remove slot", { description: err.message });
    }
  }

  // Group slots by calendar day for the date strip + selected-day grid.
  const groups: Record<string, ManagedSlot[]> = {};
  for (const s of slots ?? []) {
    const day = s.starts_at.slice(0, 10);
    (groups[day] ??= []).push(s);
  }
  const days = Object.keys(groups).sort();
  const bookedTotal = (slots ?? []).filter((s) => s.is_booked).length;

  // Keep the selection valid as slots load/refresh (e.g. a day's last slot deleted).
  useEffect(() => {
    if (days.length === 0) {
      if (selectedDay !== null) setSelectedDay(null);
    } else if (!selectedDay || !days.includes(selectedDay)) {
      setSelectedDay(days[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slots]);

  const active = selectedDay ? groups[selectedDay] ?? [] : [];
  const morning = active.filter((s) => s.starts_at.slice(11, 13) < "12");
  const afternoon = active.filter((s) => s.starts_at.slice(11, 13) >= "12");

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Availability</CardTitle>
        {slots && slots.length > 0 && (
          <div className="flex items-center gap-2 text-sm">
            <Badge variant="secondary">{slots.length - bookedTotal} open</Badge>
            {bookedTotal > 0 && <Badge variant="warning">{bookedTotal} booked</Badge>}
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-5">
        {slots === null && <Skeleton className="h-32 w-full" />}
        {slots?.length === 0 && (
          <div className="flex flex-col items-center gap-1 py-8 text-center">
            <CalendarPlus className="h-8 w-8 text-slate-300" />
            <p className="text-sm font-medium text-slate-600">No availability yet</p>
            <p className="text-sm text-slate-400">Use “Build schedule” above to open up appointment slots.</p>
          </div>
        )}

        {days.length > 0 && (
          <>
            {/* Date strip */}
            <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1">
              {days.map((day) => {
                const d = new Date(day + "T00:00:00");
                const open = groups[day].filter((s) => !s.is_booked).length;
                const isSelected = day === selectedDay;
                return (
                  <button
                    key={day}
                    onClick={() => setSelectedDay(day)}
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
                    <span
                      className={`mt-1 rounded-full px-1.5 text-[10px] font-medium ${
                        isSelected ? "bg-white/20 text-white" : open > 0 ? "bg-teal-50 text-brand" : "bg-slate-100 text-slate-400"
                      }`}
                    >
                      {open} open
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Selected day's slots, split by morning / afternoon */}
            {[{ label: "Morning", items: morning }, { label: "Afternoon", items: afternoon }]
              .filter((g) => g.items.length > 0)
              .map((g) => (
                <div key={g.label}>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{g.label}</p>
                  <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8">
                    {g.items.map((s) => (
                      <div
                        key={s.slot_id}
                        className={`group relative rounded-lg border py-2 text-center text-sm ${
                          s.is_booked
                            ? "border-amber-200 bg-amber-50 text-amber-700"
                            : "border-slate-200 bg-white text-slate-700"
                        }`}
                      >
                        <span className="font-medium tabular-nums">
                          {new Date(s.starts_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
                        </span>
                        {s.is_booked ? (
                          <span className="block text-[10px] font-medium">Booked</span>
                        ) : (
                          <button
                            onClick={() => remove(s.slot_id)}
                            aria-label="Delete slot"
                            title="Delete slot"
                            className="absolute -right-1.5 -top-1.5 grid h-5 w-5 place-items-center rounded-full border border-slate-200 bg-white text-slate-400 opacity-0 shadow-sm transition hover:border-red-200 hover:text-red-500 group-hover:opacity-100"
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
          </>
        )}
      </CardContent>
    </Card>
  );
}
