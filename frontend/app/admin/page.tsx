"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Stethoscope, Users, CalendarDays, CalendarCheck, ArrowRight } from "lucide-react";
import { api } from "@/providers/apiProvider";
import type { AdminOverview } from "@/models/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const KPIS = [
  { key: "doctors", label: "Doctors", icon: Stethoscope },
  { key: "patients", label: "Patients", icon: Users },
  { key: "appointments_today", label: "Appointments today", icon: CalendarCheck },
  { key: "appointments_total", label: "Appointments (all time)", icon: CalendarDays },
] as const;

export default function AdminDashboard() {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.adminOverview().then(setData).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-slate-500">Overview of your clinic at a glance.</p>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {KPIS.map(({ key, label, icon: Icon }) => (
          <Card key={key}>
            <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-500">{label}</CardTitle>
              <Icon className="h-4 w-4 text-brand" />
            </CardHeader>
            <CardContent>
              {data ? (
                <div className="text-3xl font-bold">{data[key]}</div>
              ) : (
                <Skeleton className="h-9 w-16" />
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Get started</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-slate-600">
          <p>Onboard a new doctor and open up their appointment slots so patients can book.</p>
          <Link href="/admin/doctors" className={cn(buttonVariants({ size: "sm" }))}>
            Manage doctors & schedules <ArrowRight className="h-4 w-4" />
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
