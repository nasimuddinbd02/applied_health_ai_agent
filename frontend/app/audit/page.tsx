import Link from "next/link";
import { Activity, Lock, Coins, Hash } from "lucide-react";
import { Formatter } from "@/lib/format";
import { getServerApi, getServerUser } from "@/lib/session";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader, EmptyState } from "../_components/ui";
import { cn } from "@/lib/utils";

export default async function AuditPage() {
  const user = await getServerUser();
  if (!user || user.role !== "admin") {
    return (
      <Card className="mx-auto max-w-md">
        <CardContent className="p-8 text-center space-y-3">
          <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-slate-100 text-slate-400">
            <Lock className="h-6 w-6" />
          </span>
          <div>
            <p className="font-semibold text-slate-900">Admins only</p>
            <p className="text-sm text-slate-500">Sign in with an admin account to view the audit log.</p>
          </div>
          <Link href="/login" className={cn(buttonVariants({ size: "sm" }))}>Sign in</Link>
        </CardContent>
      </Card>
    );
  }

  const audit = await getServerApi().then((a) => a.audit()).catch(() => null);
  if (!audit) return <p className="text-slate-400">Audit log unavailable.</p>;

  const stats = [
    { icon: Hash, label: "AI calls", value: String(audit.count) },
    { icon: Activity, label: "Tokens (in / out)", value: `${audit.total_tokens_in} / ${audit.total_tokens_out}` },
    { icon: Coins, label: "Estimated cost", value: Formatter.usd(audit.total_estimated_cost_usd) },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit & cost"
        subtitle="Every LLM / agent call via the Gateway — model, tokens, latency and estimated cost."
        icon={Activity}
      />

      <div className="grid gap-4 sm:grid-cols-3">
        {stats.map(({ icon: Icon, label, value }) => (
          <Card key={label}>
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-500">{label}</p>
                <Icon className="h-4 w-4 text-brand" />
              </div>
              <p className="mt-1 text-2xl font-bold tracking-tight">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader><CardTitle>Recent activity</CardTitle></CardHeader>
        <CardContent className="p-0">
          {audit.events.length === 0 ? (
            <EmptyState icon={Activity} title="No AI activity recorded yet" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Feature</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>Tokens</TableHead>
                  <TableHead>Latency</TableHead>
                  <TableHead>Cost</TableHead>
                  <TableHead>Outcome</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {audit.events.map((e: any) => (
                  <TableRow key={e.id}>
                    <TableCell className="font-medium">{e.feature}</TableCell>
                    <TableCell className="text-xs text-slate-500">{e.model}</TableCell>
                    <TableCell className="tabular-nums">{e.tokens_in}/{e.tokens_out}</TableCell>
                    <TableCell className="tabular-nums">{e.latency_ms}ms</TableCell>
                    <TableCell className="tabular-nums">{Formatter.usd(e.est_cost_usd, 5)}</TableCell>
                    <TableCell><Badge variant="secondary">{e.outcome}</Badge></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
