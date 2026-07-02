"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Receipt, CheckCircle2, Ban, CalendarDays, User } from "lucide-react";
import { api } from "@/providers/apiProvider";
import { useAuth } from "../../_auth/AuthContext";
import type { InvoiceDetail } from "@/models/types";
import { Formatter } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { InvoiceStatusBadge, MetaItem } from "../../_components/ui";

export default function InvoicePage() {
  const params = useParams();
  const id = Number(params.id);
  const { user, loading: authLoading } = useAuth();
  const [data, setData] = useState<InvoiceDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await api.invoice(id));
      setError("");
    } catch (err: any) {
      setError(err.message || "Could not load invoice");
    }
  }, [id]);

  // Wait for AuthContext to restore the token before fetching (the invoice
  // endpoint is auth-gated; fetching on mount would race and 401).
  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  const isStaff = user?.role === "receptionist" || user?.role === "admin";

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
    } catch (err: any) {
      setError(err.message || "Action failed");
    } finally {
      setBusy(false);
    }
  }

  if (error && !data) {
    return (
      <Card className="mx-auto max-w-md">
        <CardContent className="p-8 text-center text-slate-500">{error}</CardContent>
      </Card>
    );
  }
  if (!data) return <p className="text-slate-400">Loading…</p>;

  const { invoice, items } = data;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Link href={`/patients/${invoice.patient_id}`} className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-brand">
        <ArrowLeft className="h-4 w-4" /> Back to patient
      </Link>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="flex items-center gap-2">
            <Receipt className="h-5 w-5 text-brand" /> Invoice #{invoice.id}
          </CardTitle>
          <InvoiceStatusBadge status={invoice.status} />
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-2 sm:grid-cols-2">
            <MetaItem icon={CalendarDays}>Issued {Formatter.dateTime(invoice.created_at)}</MetaItem>
            <MetaItem icon={User}>
              <Link href={`/patients/${invoice.patient_id}`} className="text-brand hover:underline">
                Patient #{invoice.patient_id}
              </Link>
            </MetaItem>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Description</TableHead>
                <TableHead className="text-right">Amount</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((it) => (
                <TableRow key={it.id}>
                  <TableCell>{it.description}</TableCell>
                  <TableCell className="text-right tabular-nums">{Formatter.usd(it.amount, 2)}</TableCell>
                </TableRow>
              ))}
              <TableRow className="font-semibold">
                <TableCell>Total</TableCell>
                <TableCell className="text-right tabular-nums text-lg">{Formatter.usd(invoice.total, 2)}</TableCell>
              </TableRow>
            </TableBody>
          </Table>

          {invoice.status === "paid" && invoice.paid_at && (
            <p className="flex items-center gap-2 rounded-lg bg-emerald-50 px-4 py-2.5 text-sm text-emerald-700">
              <CheckCircle2 className="h-4 w-4" /> Paid on {Formatter.dateTime(invoice.paid_at)}
            </p>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}

          {isStaff && invoice.status !== "paid" && invoice.status !== "void" && (
            <div className="flex flex-wrap gap-2 border-t pt-4">
              <Button onClick={() => act(() => api.payInvoice(invoice.id))} disabled={busy}>
                <CheckCircle2 className="h-4 w-4" /> Mark as paid
              </Button>
              <Button variant="outline" className="text-destructive hover:text-destructive"
                onClick={() => act(() => api.voidInvoice(invoice.id))} disabled={busy}>
                <Ban className="h-4 w-4" /> Void
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
