"use client";
import { LayoutDashboard, Stethoscope, Pill } from "lucide-react";
import StaffShell, { type NavItem } from "../_components/StaffShell";

const NAV: NavItem[] = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/admin/doctors", label: "Doctors & schedules", icon: Stethoscope },
  { href: "/admin/pharmacy", label: "Pharmacy", icon: Pill },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <StaffShell badge="Admin" nav={NAV} allowedRoles={["admin"]}>
      {children}
    </StaffShell>
  );
}
