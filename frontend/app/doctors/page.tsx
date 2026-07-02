import Link from "next/link";
import { Stethoscope, Clock, ArrowRight, DollarSign } from "lucide-react";
import { api } from "@/providers/apiProvider";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader, InitialsAvatar, EmptyState } from "../_components/ui";

export default async function DoctorsPage() {
  const doctors = await api.doctors().catch(() => []);
  return (
    <div className="space-y-6">
      <PageHeader
        title="Find a doctor"
        subtitle="Browse our specialists and check their availability."
        icon={Stethoscope}
      />

      {doctors.length === 0 ? (
        <Card><CardContent><EmptyState icon={Stethoscope} title="No doctors available yet" /></CardContent></Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {doctors.map((d) => (
            <Link key={d.id} href={`/doctors/${d.id}`} className="group">
              <Card className="h-full transition group-hover:border-brand/40 group-hover:shadow-md">
                <CardContent className="p-5 flex h-full flex-col">
                  <div className="flex items-center gap-3">
                    <InitialsAvatar name={d.name} className="h-12 w-12 text-base" />
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-900 truncate">{d.name}</p>
                      <Badge variant="secondary" className="mt-1">{d.specialty}</Badge>
                    </div>
                  </div>
                  {d.bio && <p className="mt-3 text-sm text-slate-500 line-clamp-2">{d.bio}</p>}
                  <div className="mt-4 flex items-center gap-4 text-sm text-slate-500">
                    <span className="inline-flex items-center gap-1.5">
                      <Clock className="h-4 w-4 text-slate-400" /> {d.room || "—"}
                    </span>
                    <span className="inline-flex items-center gap-1 font-medium text-slate-700">
                      <DollarSign className="h-4 w-4 text-slate-400" />{d.consultation_fee}
                    </span>
                  </div>
                  <div className="mt-4 flex items-center gap-1 text-sm font-medium text-brand">
                    View & book <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
