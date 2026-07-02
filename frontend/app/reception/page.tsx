"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { LogIn, LogOut, RefreshCw, Ban } from "lucide-react";
import { api } from "@/providers/apiProvider";
import type { AppointmentStatus, QueueEntry, ReceptionOverview } from "@/models/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const KPIS: { key: keyof ReceptionOverview; label: string }[] = [
  { key: "waiting", label: "Waiting" },
  { key: "checked_in", label: "Checked in" },
  { key: "in_treatment", label: "In treatment" },
  { key: "completed", label: "Completed" },
];

const STATUS_BADGE: Record<AppointmentStatus, { label: string; variant: "default" | "secondary" | "warning" | "success" | "destructive" | "outline" }> = {
  booked: { label: "Waiting", variant: "secondary" },
  checked_in: { label: "Checked in", variant: "default" },
  in_treatment: { label: "In treatment", variant: "warning" },
  completed: { label: "Completed", variant: "success" },
  cancelled: { label: "Cancelled", variant: "outline" },
};

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export default function ReceptionQueue() {
  const [queue, setQueue] = useState<QueueEntry[] | null>(null);
  const [overview, setOverview] = useState<ReceptionOverview | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    const [q, o] = await Promise.all([api.receptionQueue(), api.receptionOverview()]);
    setQueue(q);
    setOverview(o);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function act(id: number, fn: () => Promise<unknown>, label: string) {
    setBusyId(id);
    try {
      await fn();
      toast.success(label);
      await refresh();
    } catch (err: any) {
      toast.error("Action failed", { description: err.message });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">Today's queue</h1>
          <p className="text-slate-500">Check patients in on arrival and out after their visit.</p>
        </div>
        <Button variant="outline" size="sm" onClick={refresh}>
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        {KPIS.map(({ key, label }) => (
          <Card key={key}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-slate-500">{label}</CardTitle>
            </CardHeader>
            <CardContent>
              {overview ? (
                <div className="text-3xl font-bold">{overview[key]}</div>
              ) : (
                <Skeleton className="h-9 w-12" />
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Patient</TableHead>
                <TableHead>Doctor</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {queue === null &&
                Array.from({ length: 4 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={6}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  </TableRow>
                ))}
              {queue?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-slate-400 py-8">
                    No appointments scheduled for today.
                  </TableCell>
                </TableRow>
              )}
              {queue?.map((row) => {
                const badge = STATUS_BADGE[row.status];
                const busy = busyId === row.appointment_id;
                return (
                  <TableRow key={row.appointment_id}>
                    <TableCell className="font-medium tabular-nums">{fmtTime(row.starts_at)}</TableCell>
                    <TableCell>
                      <Link href={`/patients/${row.patient_id}`} className="hover:text-brand hover:underline">
                        {row.patient_name}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {row.doctor_name}
                      {row.room && <span className="text-slate-400"> · {row.room}</span>}
                    </TableCell>
                    <TableCell className="max-w-[14rem] truncate text-slate-500">{row.reason || "—"}</TableCell>
                    <TableCell><Badge variant={badge.variant}>{badge.label}</Badge></TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        {row.status === "booked" && (
                          <>
                            <Button size="sm" disabled={busy}
                              onClick={() => act(row.appointment_id, () => api.checkIn(row.appointment_id), "Patient checked in")}>
                              <LogIn className="h-4 w-4" /> Check in
                            </Button>
                            <Button size="sm" variant="ghost" disabled={busy}
                              onClick={() => act(row.appointment_id, () => api.cancelAppointment(row.appointment_id), "Appointment cancelled")}>
                              <Ban className="h-4 w-4" />
                            </Button>
                          </>
                        )}
                        {row.status === "checked_in" && (
                          <Link href={`/appointments/${row.appointment_id}`}
                            className="text-sm text-brand hover:underline">
                            Open for treatment →
                          </Link>
                        )}
                        {row.status === "in_treatment" && (
                          <Button size="sm" variant="outline" disabled={busy}
                            onClick={() => act(row.appointment_id, () => api.checkout(row.appointment_id), "Patient checked out")}>
                            <LogOut className="h-4 w-4" /> Check out
                          </Button>
                        )}
                        {(row.status === "completed" || row.status === "cancelled") && (
                          <span className="text-slate-400 text-sm">—</span>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
