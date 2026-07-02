"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Building2, LogOut, type LucideIcon } from "lucide-react";
import { useAuth } from "../_auth/AuthContext";
import { Toaster } from "@/components/ui/sonner";
import type { UserRole } from "@/models/types";
import { cn } from "@/lib/utils";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  exact?: boolean;
}

interface StaffShellProps {
  badge: string; // short label shown next to the logo, e.g. "Admin"
  nav: NavItem[];
  allowedRoles: UserRole[];
  children: React.ReactNode;
}

/** Role-guarded, full-bleed staff console shell (sidebar + top bar + toaster).
 * Shared by the admin and reception sections so they get the same chrome. */
export default function StaffShell({ badge, nav, allowedRoles, children }: StaffShellProps) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  // Client guard; the API also enforces the same roles via require_role.
  useEffect(() => {
    if (!loading && (!user || !allowedRoles.includes(user.role))) {
      router.replace("/login");
    }
  }, [loading, user, router, allowedRoles]);

  if (loading || !user || !allowedRoles.includes(user.role)) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-400 text-sm">
        Checking access…
      </div>
    );
  }

  return (
    // Full-bleed: break out of the root layout's centered, max-w container so
    // the console spans the whole viewport.
    <div className="relative left-1/2 right-1/2 -mx-[50vw] -mt-6 -mb-6 w-screen min-h-[calc(100vh-3.25rem)] flex bg-slate-100">
      <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="h-14 flex items-center gap-2 px-5 border-b border-slate-200">
          <Building2 className="h-5 w-5 text-brand" />
          <span className="font-semibold">City Hospital</span>
          <span className="ml-auto text-[10px] uppercase tracking-wide text-slate-400">{badge}</span>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {nav.map((item) => {
            const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active ? "bg-brand text-white" : "text-slate-600 hover:bg-slate-100",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-slate-200 p-3">
          <div className="px-2 pb-2">
            <p className="text-sm font-medium truncate">{user.name || user.email}</p>
            <p className="text-xs text-slate-400 capitalize truncate">
              {user.role}{user.name ? ` · ${user.email}` : ""}
            </p>
          </div>
          <button
            onClick={() => { logout(); router.push("/login"); }}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
          >
            <LogOut className="h-4 w-4" /> Log out
          </button>
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        {/* Mobile top bar (sidebar is desktop-first this pass) */}
        <div className="md:hidden h-14 flex items-center gap-3 px-4 border-b border-slate-200 bg-white">
          <Building2 className="h-5 w-5 text-brand" />
          <span className="font-semibold">{badge}</span>
          <nav className="ml-auto flex gap-3 text-sm">
            {nav.map((item) => (
              <Link key={item.href} href={item.href} className="text-slate-600 hover:text-brand">
                {item.label.split(" ")[0]}
              </Link>
            ))}
          </nav>
        </div>

        <main className="flex-1 p-6 md:p-8 overflow-x-hidden">{children}</main>
      </div>

      <Toaster />
    </div>
  );
}
