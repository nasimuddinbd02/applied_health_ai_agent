"use client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Pill, AlertTriangle } from "lucide-react";
import { api } from "@/providers/apiProvider";
import type { Medicine } from "@/models/types";
import { Formatter } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";

const LOW_STOCK = 10;

export default function AdminPharmacyPage() {
  const [medicines, setMedicines] = useState<Medicine[] | null>(null);

  async function refresh() {
    setMedicines(await api.medicines());
  }
  useEffect(() => { refresh(); }, []);

  const lowCount = medicines?.filter((m) => m.stock_count <= LOW_STOCK).length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Pharmacy</h1>
          <p className="text-slate-500">Medicine stock and inventory intake.</p>
        </div>
        <AddMedicineDialog onCreated={refresh} />
      </div>

      {lowCount > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
          <AlertTriangle className="h-4 w-4" />
          {lowCount} medicine{lowCount > 1 ? "s are" : " is"} low on stock (≤ {LOW_STOCK}).
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Medicine</TableHead>
                <TableHead>Form</TableHead>
                <TableHead>Unit</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead className="text-right">In stock</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {medicines === null &&
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}><TableCell colSpan={5}><Skeleton className="h-5 w-full" /></TableCell></TableRow>
                ))}
              {medicines?.length === 0 && (
                <TableRow><TableCell colSpan={5} className="text-center text-slate-400 py-8">No medicines yet.</TableCell></TableRow>
              )}
              {medicines?.map((m) => (
                <TableRow key={m.id}>
                  <TableCell className="font-medium">
                    <span className="inline-flex items-center gap-2">
                      <Pill className="h-4 w-4 text-brand" /> {m.name}
                    </span>
                  </TableCell>
                  <TableCell className="text-slate-500">{m.dosage_form || "—"}</TableCell>
                  <TableCell className="text-slate-500">{m.unit || "—"}</TableCell>
                  <TableCell className="text-right tabular-nums">{Formatter.usd(m.unit_price, 2)}</TableCell>
                  <TableCell className="text-right">
                    {m.stock_count <= LOW_STOCK ? (
                      <Badge variant="warning">{m.stock_count} low</Badge>
                    ) : (
                      <span className="tabular-nums font-medium">{m.stock_count}</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

const EMPTY = { name: "", dosage_form: "", unit: "", stock_count: "", unit_price: "" };

function AddMedicineDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ ...EMPTY });
  const [saving, setSaving] = useState(false);
  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.addMedicine({
        name: form.name, dosage_form: form.dosage_form, unit: form.unit,
        stock_count: form.stock_count ? Number(form.stock_count) : 0,
        unit_price: form.unit_price ? Number(form.unit_price) : 0,
      });
      toast.success(`${form.name} added to stock`);
      setForm({ ...EMPTY });
      setOpen(false);
      onCreated();
    } catch (err: any) {
      toast.error("Could not add medicine", { description: err.message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button><Plus className="h-4 w-4" /> Add medicine</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add medicine to stock</DialogTitle>
          <DialogDescription>Register a new medicine or restock an existing line.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-2">
            <Label htmlFor="m-name">Name</Label>
            <Input id="m-name" required value={form.name} onChange={set("name")} placeholder="Amoxicillin" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="m-form">Form</Label>
              <Input id="m-form" value={form.dosage_form} onChange={set("dosage_form")} placeholder="capsule" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="m-unit">Unit</Label>
              <Input id="m-unit" value={form.unit} onChange={set("unit")} placeholder="500mg" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="m-stock">Stock count</Label>
              <Input id="m-stock" type="number" min="0" value={form.stock_count} onChange={set("stock_count")} placeholder="100" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="m-price">Unit price ($)</Label>
              <Input id="m-price" type="number" min="0" step="0.01" value={form.unit_price} onChange={set("unit_price")} placeholder="0.30" />
            </div>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={saving}>{saving ? "Adding…" : "Add medicine"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
