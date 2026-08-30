// Shared, server-safe presentational building blocks used across the app so
// every page speaks the same visual language. Pure (no hooks) — importable from
// server or client components.
import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { AppointmentStatus } from "@/types";

// --- Page header ---------------------------------------------------------- #
export function PageHeader({
  title, subtitle, icon: Icon, actions,
}: {
  title: string;
  subtitle?: string;
  icon?: LucideIcon;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 flex-wrap">
      <div className="flex items-start gap-3">
        {Icon && (
          <span className="mt-0.5 grid h-10 w-10 place-items-center rounded-xl bg-brand/10 text-brand">
            <Icon className="h-5 w-5" />
          </span>
        )}
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
          {subtitle && <p className="text-slate-500">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

// --- Status badge --------------------------------------------------------- #
const STATUS: Record<AppointmentStatus, { label: string; variant: React.ComponentProps<typeof Badge>["variant"] }> = {
  booked: { label: "Scheduled", variant: "info" },
  checked_in: { label: "Checked in", variant: "default" },
  in_treatment: { label: "In treatment", variant: "warning" },
  completed: { label: "Completed", variant: "success" },
  cancelled: { label: "Cancelled", variant: "outline" },
};

export function StatusBadge({ status }: { status: AppointmentStatus | string }) {
  const s = STATUS[status as AppointmentStatus] ?? { label: status, variant: "secondary" as const };
  return <Badge variant={s.variant}>{s.label}</Badge>;
}

const INVOICE_STATUS: Record<string, { label: string; variant: React.ComponentProps<typeof Badge>["variant"] }> = {
  draft: { label: "Draft", variant: "secondary" },
  issued: { label: "Unpaid", variant: "warning" },
  paid: { label: "Paid", variant: "success" },
  void: { label: "Void", variant: "outline" },
};

export function InvoiceStatusBadge({ status }: { status: string }) {
  const s = INVOICE_STATUS[status] ?? { label: status, variant: "secondary" as const };
  return <Badge variant={s.variant}>{s.label}</Badge>;
}

// --- Initials avatar ------------------------------------------------------ #
const AVATAR_TONES = [
  "bg-teal-100 text-teal-700", "bg-blue-100 text-blue-700", "bg-violet-100 text-violet-700",
  "bg-amber-100 text-amber-700", "bg-rose-100 text-rose-700", "bg-emerald-100 text-emerald-700",
];

function initials(name: string) {
  const parts = name.replace(/^Dr\.?\s+/i, "").trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

export function InitialsAvatar({ name, className }: { name: string; className?: string }) {
  const tone = AVATAR_TONES[[...name].reduce((a, c) => a + c.charCodeAt(0), 0) % AVATAR_TONES.length];
  return (
    <span className={cn("grid place-items-center rounded-full font-semibold shrink-0", tone, className)}>
      {initials(name) || "?"}
    </span>
  );
}

// --- Empty state ---------------------------------------------------------- #
export function EmptyState({
  icon: Icon, title, description,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 py-10 text-center">
      {Icon && <Icon className="h-8 w-8 text-slate-300 mb-1" />}
      <p className="text-sm font-medium text-slate-600">{title}</p>
      {description && <p className="text-sm text-slate-400">{description}</p>}
    </div>
  );
}

// --- Definition / meta row ------------------------------------------------ #
export function MetaItem({ icon: Icon, children }: { icon: LucideIcon; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-600">
      <Icon className="h-4 w-4 text-slate-400 shrink-0" />
      <span>{children}</span>
    </div>
  );
}
