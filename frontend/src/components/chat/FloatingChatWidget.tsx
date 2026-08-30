"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { MessageCircle, X } from "lucide-react";
import AppointmentChat from "@/components/chat/AppointmentChat";

const AUTO_OPEN_KEY = "chat_auto_opened";

/** Messenger-style floating chat: a bubble in the bottom-right corner that
 * expands into a chat panel. Auto-opens once per browser session when a
 * visitor lands on the homepage; otherwise stays a bubble until clicked. */
export default function FloatingChatWidget() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [greeted, setGreeted] = useState(false);

  useEffect(() => {
    if (pathname !== "/") return;
    if (sessionStorage.getItem(AUTO_OPEN_KEY)) return;
    // Note: the flag is set only once the timeout actually fires (not here,
    // synchronously) — React Strict Mode double-invokes effects in dev, and
    // setting it up front would make the real (second) mount see it already
    // set and skip scheduling entirely.
    const t = setTimeout(() => {
      sessionStorage.setItem(AUTO_OPEN_KEY, "1");
      setOpen(true);
      setGreeted(true);
    }, 900);
    return () => clearTimeout(t);
  }, [pathname]);

  // Hidden on staff/admin screens, and on /agent — which is the dedicated
  // full-page chat, so the floating bubble there would be a duplicate.
  if (pathname.startsWith("/admin") || pathname.startsWith("/reception") || pathname === "/agent") {
    return null;
  }

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-3">
      {open && (
        <div className="w-[22rem] max-w-[calc(100vw-2.5rem)] h-[32rem] max-h-[calc(100vh-8rem)] bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden">
          <AppointmentChat floating onClose={() => setOpen(false)} />
        </div>
      )}

      {!open && greeted && (
        <button
          onClick={() => setOpen(true)}
          className="bg-white border border-slate-200 shadow-lg rounded-2xl rounded-br-sm px-4 py-2.5 text-sm text-slate-700 hover:shadow-xl transition max-w-[16rem] text-left"
        >
          Hi! Need to book an appointment or have a question? Chat with us.
        </button>
      )}

      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Close chat" : "Open chat"}
        className="w-14 h-14 rounded-full bg-brand text-white shadow-xl flex items-center justify-center hover:scale-105 active:scale-95 transition"
      >
        {open ? <X className="h-6 w-6" /> : <MessageCircle className="h-6 w-6" />}
      </button>
    </div>
  );
}
