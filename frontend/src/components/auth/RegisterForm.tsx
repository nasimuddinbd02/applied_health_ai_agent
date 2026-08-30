"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { landingPathFor, useAuth } from "@/context/AuthContext";
import type { AuthUser } from "@/types";
import { Card, CardContent } from "@/components/ui/card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const empty = {
  name: "", email: "", password: "", phone: "", gender: "", date_of_birth: "",
  address: "", blood_group: "", notes: "",
};

export default function RegisterForm() {
  const { signup } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState(empty);
  const [created, setCreated] = useState<AuthUser | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function set(k: string, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      setCreated(await signup(form));
    } catch (err: any) {
      setError(err.message || "Could not register");
    } finally {
      setLoading(false);
    }
  }

  if (created) {
    return (
      <Card className="border-emerald-200 bg-emerald-50/60">
        <CardContent className="p-6 space-y-3">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="h-6 w-6 text-emerald-600 shrink-0" />
            <div>
              <p className="font-semibold text-emerald-900">Welcome aboard!</p>
              <p className="text-sm text-emerald-700/80">
                Your patient ID is <b>#{created.patient_id}</b> and you're signed in.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => router.push(landingPathFor(created))} className={cn(buttonVariants({ size: "sm" }))}>
              View my profile
            </button>
            <Link href="/doctors" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>Find a doctor</Link>
            <Link href="/agent" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>Book via assistant</Link>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-6">
        <form onSubmit={submit} className="space-y-4">
          <Field label="Full name" required value={form.name} onChange={(v) => set("name", v)} />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Email" type="email" required value={form.email} onChange={(v) => set("email", v)} />
            <Field label="Password" type="password" required value={form.password} onChange={(v) => set("password", v)} />
          </div>
          <Field label="Phone" value={form.phone} onChange={(v) => set("phone", v)} />
          <div className="grid grid-cols-3 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="gender">Gender</Label>
              <select id="gender" value={form.gender} onChange={(e) => set("gender", e.target.value)}
                className="h-10 rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
                <option value="">—</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
              </select>
            </div>
            <Field label="Date of birth" type="date" value={form.date_of_birth} onChange={(v) => set("date_of_birth", v)} />
            <Field label="Blood group" value={form.blood_group} onChange={(v) => set("blood_group", v)} />
          </div>
          <Field label="Address" value={form.address} onChange={(v) => set("address", v)} />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={loading || !form.name || !form.email || !form.password} className="w-full">
            {loading ? "Registering…" : "Create profile"}
          </Button>
          <p className="text-center text-sm text-slate-400">
            Already registered? <Link href="/login" className="text-brand hover:underline">Sign in</Link>
          </p>
        </form>
      </CardContent>
    </Card>
  );
}

function Field({ label, value, onChange, type = "text", required = false }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; required?: boolean;
}) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}{required && <span className="text-destructive"> *</span>}</Label>
      <Input id={id} type={type} value={value} required={required} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
