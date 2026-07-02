import Link from "next/link";
import {
  MessageSquare, Stethoscope, CalendarCheck, ShieldCheck, Clock, ArrowRight, UserPlus,
} from "lucide-react";
import { api } from "@/providers/apiProvider";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { InitialsAvatar } from "./_components/ui";
import { cn } from "@/lib/utils";

export default async function Home() {
  const [doctors, health] = await Promise.all([
    api.doctors().catch(() => []),
    api.health().catch(() => null),
  ]);

  return (
    <div className="space-y-12">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-teal-700 via-teal-600 to-emerald-600 text-white">
        <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-white/10 blur-2xl" />
        <div className="absolute -bottom-24 -left-10 h-72 w-72 rounded-full bg-emerald-400/20 blur-3xl" />
        <div className="relative px-6 py-14 sm:px-12 sm:py-20 max-w-2xl">
          <span className="inline-flex items-center gap-2 rounded-full bg-white/15 px-3 py-1 text-xs font-medium backdrop-blur">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" />
            {health?.has_provider_key ? "AI assistant online" : "Welcome"}
          </span>
          <h1 className="mt-4 text-4xl sm:text-5xl font-bold tracking-tight leading-tight">
            Your health, booked in seconds.
          </h1>
          <p className="mt-4 text-lg text-teal-50/90">
            Find the right specialist, check real availability, and book your visit — or just
            chat with our assistant and it handles everything for you. No login needed.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/agent"
              className="inline-flex items-center gap-2 rounded-lg bg-white px-5 py-2.5 font-medium text-teal-700 shadow-sm transition hover:bg-teal-50"
            >
              <MessageSquare className="h-4 w-4" /> Chat to book
            </Link>
            <Link
              href="/register"
              className="inline-flex items-center gap-2 rounded-lg bg-white/15 px-5 py-2.5 font-medium text-white backdrop-blur transition hover:bg-white/25"
            >
              <UserPlus className="h-4 w-4" /> Register as patient
            </Link>
          </div>
        </div>
      </section>

      {/* Value props */}
      <section className="grid gap-4 sm:grid-cols-3">
        {[
          { icon: MessageSquare, title: "Book with AI", text: "Describe your symptoms and our assistant finds a doctor and a time." },
          { icon: CalendarCheck, title: "Real availability", text: "Every slot you see is live — no phone tag, no waiting on hold." },
          { icon: ShieldCheck, title: "Your records, together", text: "Appointments, prescriptions and visit history in one place." },
        ].map(({ icon: Icon, title, text }) => (
          <Card key={title} className="border-slate-200">
            <CardContent className="p-5">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand/10 text-brand">
                <Icon className="h-5 w-5" />
              </span>
              <h3 className="mt-3 font-semibold text-slate-900">{title}</h3>
              <p className="mt-1 text-sm text-slate-500">{text}</p>
            </CardContent>
          </Card>
        ))}
      </section>

      {/* Specialists */}
      <section>
        <div className="mb-4 flex items-end justify-between">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-slate-900">Meet our specialists</h2>
            <p className="text-sm text-slate-500">Browse doctors and check their availability.</p>
          </div>
          <Link href="/doctors" className="text-sm font-medium text-brand hover:underline inline-flex items-center gap-1">
            View all <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {doctors.slice(0, 6).map((d) => (
            <Link key={d.id} href={`/doctors/${d.id}`} className="group">
              <Card className="h-full transition group-hover:border-brand/40 group-hover:shadow-md">
                <CardContent className="p-5">
                  <div className="flex items-center gap-3">
                    <InitialsAvatar name={d.name} className="h-11 w-11 text-sm" />
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-900 truncate">{d.name}</p>
                      <Badge variant="secondary" className="mt-0.5">{d.specialty}</Badge>
                    </div>
                  </div>
                  <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
                    <span className="inline-flex items-center gap-1.5">
                      <Clock className="h-4 w-4 text-slate-400" /> {d.room || "—"}
                    </span>
                    <span className="font-medium text-slate-700">${d.consultation_fee}</span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      {/* CTA band */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-brand/10 text-brand">
            <Stethoscope className="h-6 w-6" />
          </span>
          <div>
            <h3 className="font-semibold text-slate-900">New here?</h3>
            <p className="text-sm text-slate-500">Create a patient profile in under a minute and book your first visit.</p>
          </div>
        </div>
        <Link href="/register" className={cn(buttonVariants(), "shrink-0")}>
          Get started <ArrowRight className="h-4 w-4" />
        </Link>
      </section>
    </div>
  );
}
