"use client";
import { ClipboardList } from "lucide-react";
import StaffShell, { type NavItem } from "@/components/layout/StaffShell";

const NAV: NavItem[] = [
  { href: "/reception", label: "Today's queue", icon: ClipboardList, exact: true },
];

export default function ReceptionLayout({ children }: { children: React.ReactNode }) {
  return (
    <StaffShell badge="Front desk" nav={NAV} allowedRoles={["receptionist", "admin", "doctor"]}>
      {children}
    </StaffShell>
  );
}
