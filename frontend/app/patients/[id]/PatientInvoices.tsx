"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Receipt, ChevronRight } from "lucide-react";
import { api } from "@/providers/apiProvider";
import { useAuth } from "../../_auth/AuthContext";
import type { Invoice } from "@/models/types";
import { Formatter } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InvoiceStatusBadge, EmptyState } from "../../_components/ui";

// Invoices are auth-gated, so fetch client-side (the api singleton carries the
// logged-in user's token). If the viewer isn't signed in the call 401s and we
// simply hide the section.
export default function PatientInvoices({ patientId }: { patientId: number }) {
  const { user, loading } = useAuth();
  const [invoices, setInvoices] = useState<Invoice[] | null>(null);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    if (loading) return; // wait until the auth token is restored
    if (!user) { setDenied(true); return; } // guests don't see invoices
    api.patientInvoices(patientId).then(setInvoices).catch(() => setDenied(true));
  }, [patientId, loading, user]);

  if (denied) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Receipt className="h-5 w-5 text-brand" /> Invoices
        </CardTitle>
      </CardHeader>
      <CardContent>
        {invoices === null ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : invoices.length === 0 ? (
          <EmptyState icon={Receipt} title="No invoices yet" description="Invoices are created when a visit is completed." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {invoices.map((inv) => (
              <li key={inv.id}>
                <Link href={`/invoices/${inv.id}`} className="flex items-center gap-3 py-3 group">
                  <span className="grid h-9 w-9 place-items-center rounded-lg bg-slate-100 text-slate-500">
                    <Receipt className="h-4 w-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-slate-800 group-hover:text-brand">Invoice #{inv.id}</p>
                    <p className="text-xs text-slate-400">{Formatter.dateTime(inv.created_at)}</p>
                  </div>
                  <span className="font-semibold text-slate-800">{Formatter.usd(inv.total, 2)}</span>
                  <InvoiceStatusBadge status={inv.status} />
                  <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-slate-400" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
