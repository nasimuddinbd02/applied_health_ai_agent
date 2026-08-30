import Link from "next/link";
import { ArrowLeft, Mail, MapPin, DollarSign } from "lucide-react";
import { api } from "@/lib/api/client";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { InitialsAvatar, MetaItem } from "@/components/common/ui";
import BookPanel from "@/components/booking/BookPanel";

export default async function DoctorPage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const [doctor, slots] = await Promise.all([
    api.doctor(id),
    api.doctorAvailability(id).catch(() => []),
  ]);

  return (
    <div className="space-y-6">
      <Link href="/doctors" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-brand">
        <ArrowLeft className="h-4 w-4" /> All doctors
      </Link>

      <Card>
        <CardContent className="p-6">
          <div className="flex items-start gap-4">
            <InitialsAvatar name={doctor.name} className="h-16 w-16 text-xl" />
            <div className="min-w-0">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">{doctor.name}</h1>
              <Badge variant="secondary" className="mt-1">{doctor.specialty}</Badge>
              {doctor.bio && <p className="mt-3 text-slate-600">{doctor.bio}</p>}
              <div className="mt-4 grid gap-2 sm:grid-cols-3">
                <MetaItem icon={MapPin}>{doctor.room || "—"}</MetaItem>
                <MetaItem icon={Mail}>{doctor.email || "—"}</MetaItem>
                <MetaItem icon={DollarSign}>Consultation ${doctor.consultation_fee}</MetaItem>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <BookPanel doctorId={id} slots={slots} />
    </div>
  );
}
