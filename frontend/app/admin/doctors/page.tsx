"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Plus, Settings2 } from "lucide-react";
import { api } from "@/providers/apiProvider";
import type { Doctor } from "@/models/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";

export default function AdminDoctorsPage() {
  const [doctors, setDoctors] = useState<Doctor[] | null>(null);

  async function refresh() {
    setDoctors(await api.doctors());
  }
  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">Doctors & schedules</h1>
          <p className="text-slate-500">Onboard doctors and open up their appointment slots.</p>
        </div>
        <AddDoctorDialog onCreated={refresh} />
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Specialty</TableHead>
                <TableHead>Room</TableHead>
                <TableHead>Fee</TableHead>
                <TableHead className="text-right">Manage</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {doctors === null &&
                Array.from({ length: 4 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={5}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  </TableRow>
                ))}
              {doctors?.map((d) => (
                <TableRow key={d.id}>
                  <TableCell className="font-medium">{d.name}</TableCell>
                  <TableCell>{d.specialty || "—"}</TableCell>
                  <TableCell>{d.room || "—"}</TableCell>
                  <TableCell>${d.consultation_fee}</TableCell>
                  <TableCell className="text-right">
                    <Link
                      href={`/admin/doctors/${d.id}`}
                      className="inline-flex items-center gap-1.5 text-brand hover:underline text-sm"
                    >
                      <Settings2 className="h-4 w-4" /> Schedule
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
              {doctors?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-slate-400 py-8">
                    No doctors yet — add your first one.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

const EMPTY = {
  name: "", specialty: "", room: "", phone: "", bio: "",
  consultation_fee: "", login_email: "", login_password: "",
};

function AddDoctorDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ ...EMPTY });
  const [saving, setSaving] = useState(false);

  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.createDoctor({
        name: form.name,
        specialty: form.specialty,
        room: form.room,
        phone: form.phone,
        bio: form.bio,
        consultation_fee: form.consultation_fee ? Number(form.consultation_fee) : 0,
        login_email: form.login_email,
        login_password: form.login_password,
      });
      toast.success(`${form.name} added`, {
        description: `Login: ${form.login_email} — share the temporary password so they can sign in.`,
      });
      setForm({ ...EMPTY });
      setOpen(false);
      onCreated();
    } catch (err: any) {
      toast.error("Could not add doctor", { description: err.message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4" /> Add doctor
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a doctor</DialogTitle>
          <DialogDescription>
            Creates the doctor's profile and a login so they can sign in immediately.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-2">
            <Label htmlFor="name">Full name</Label>
            <Input id="name" required value={form.name} onChange={set("name")} placeholder="Dr. Jane Doe" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="specialty">Specialty</Label>
              <Input id="specialty" value={form.specialty} onChange={set("specialty")} placeholder="Cardiology" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="room">Room</Label>
              <Input id="room" value={form.room} onChange={set("room")} placeholder="Room 201" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="phone">Phone</Label>
              <Input id="phone" value={form.phone} onChange={set("phone")} placeholder="555-0100" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="fee">Consultation fee ($)</Label>
              <Input id="fee" type="number" min="0" value={form.consultation_fee} onChange={set("consultation_fee")} placeholder="100" />
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="bio">Short bio</Label>
            <Input id="bio" value={form.bio} onChange={set("bio")} placeholder="Consultant, 10 years' experience." />
          </div>
          <div className="border-t pt-4 grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="login_email">Login email</Label>
              <Input id="login_email" type="email" required value={form.login_email} onChange={set("login_email")} placeholder="jane@clinic.test" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="login_password">Temp password</Label>
              <Input id="login_password" required value={form.login_password} onChange={set("login_password")} placeholder="temp1234" />
            </div>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={saving}>
              {saving ? "Adding…" : "Add doctor"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
