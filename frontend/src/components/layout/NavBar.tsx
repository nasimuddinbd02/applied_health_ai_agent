"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  HeartPulse, LogOut, LayoutDashboard, ClipboardList, UserRound,
  CalendarDays, MessageSquare, ChevronDown, Stethoscope, Receipt,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import type { AuthUser } from "@/types";
import { InitialsAvatar } from "@/components/common/ui";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const PUBLIC_LINKS = [
  { href: "/", label: "Home", exact: true },
  { href: "/doctors", label: "Find a doctor", exact: false },
];

interface MenuItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

/** Role-aware entries for the user menu. */
function menuItemsFor(user: AuthUser): MenuItem[] {
  switch (user.role) {
    case "patient":
      return [
        { href: `/patients/${user.patient_id}`, label: "My profile", icon: UserRound },
        { href: `/patients/${user.patient_id}`, label: "My appointments & invoices", icon: Receipt },
        { href: "/doctors", label: "Book an appointment", icon: CalendarDays },
        { href: "/agent", label: "Chat assistant", icon: MessageSquare },
      ];
    case "doctor":
      return [
        { href: `/doctors/${user.doctor_id}`, label: "My public profile", icon: Stethoscope },
        { href: "/reception", label: "Today's queue", icon: ClipboardList },
      ];
    case "receptionist":
      return [{ href: "/reception", label: "Front desk", icon: ClipboardList }];
    case "admin":
      return [
        { href: "/admin", label: "Admin console", icon: LayoutDashboard },
        { href: "/reception", label: "Front desk", icon: ClipboardList },
        { href: "/audit", label: "AI audit log", icon: Receipt },
      ];
    default:
      return [];
  }
}

export default function NavBar() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  // The staff consoles render their own full-screen shell — hide this header there.
  if (pathname.startsWith("/admin") || pathname.startsWith("/reception")) return null;

  const consoleLink =
    user?.role === "admin"
      ? { href: "/admin", label: "Admin console", icon: LayoutDashboard }
      : user?.role === "receptionist"
        ? { href: "/reception", label: "Front desk", icon: ClipboardList }
        : null;

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/80 backdrop-blur supports-[backdrop-filter]:bg-white/70">
      <nav className="mx-auto max-w-6xl px-4 sm:px-6 h-14 flex items-center gap-1">
        <Link href="/" className="flex items-center gap-2 font-bold text-slate-900 mr-4">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-white">
            <HeartPulse className="h-5 w-5" />
          </span>
          <span className="hidden sm:inline">City Hospital</span>
        </Link>

        <div className="flex items-center gap-1">
          {PUBLIC_LINKS.map((l) => {
            const active = l.exact ? pathname === l.href : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  active ? "bg-brand/10 text-brand" : "text-slate-600 hover:bg-slate-100",
                )}
              >
                {l.label}
              </Link>
            );
          })}
          {consoleLink && (
            <Link
              href={consoleLink.href}
              className={cn(
                "hidden sm:flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                pathname.startsWith(consoleLink.href) ? "bg-brand/10 text-brand" : "text-slate-600 hover:bg-slate-100",
              )}
            >
              <consoleLink.icon className="h-4 w-4" />
              {consoleLink.label}
            </Link>
          )}
        </div>

        <div className="flex-1" />

        {user ? (
          <UserMenu
            user={user}
            onLogout={() => {
              logout();
              router.push("/login");
            }}
          />
        ) : (
          <div className="flex items-center gap-2">
            <Link href="/login" className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}>
              Sign in
            </Link>
            <Link href="/register" className={cn(buttonVariants({ size: "sm" }))}>
              Register
            </Link>
          </div>
        )}
      </nav>
    </header>
  );
}

/** Avatar + name trigger opening a dropdown of profile actions. Closes on
 * outside click and Escape. */
function UserMenu({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const displayName = user.name || user.email;

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2 transition hover:bg-slate-100"
      >
        <InitialsAvatar name={displayName} className="h-8 w-8 text-xs" />
        <span className="hidden sm:block max-w-[10rem] truncate text-sm font-medium text-slate-800">
          {displayName}
        </span>
        <ChevronDown className={cn("h-4 w-4 text-slate-400 transition", open && "rotate-180")} />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-2 w-64 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg"
        >
          <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-3">
            <InitialsAvatar name={displayName} className="h-10 w-10 text-sm" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-900">{displayName}</p>
              <p className="truncate text-xs text-slate-400">{user.email}</p>
              <p className="text-[11px] capitalize text-brand">{user.role}</p>
            </div>
          </div>
          <div className="py-1.5">
            {menuItemsFor(user).map((item) => (
              <Link
                key={item.label}
                href={item.href}
                role="menuitem"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 hover:text-brand"
              >
                <item.icon className="h-4 w-4 text-slate-400" />
                {item.label}
              </Link>
            ))}
          </div>
          <div className="border-t border-slate-100 py-1.5">
            <button
              role="menuitem"
              onClick={onLogout}
              className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-slate-700 hover:bg-red-50 hover:text-red-600"
            >
              <LogOut className="h-4 w-4 text-slate-400" />
              Log out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
