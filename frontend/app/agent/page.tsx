import { MessageSquare } from "lucide-react";
import AppointmentChat from "./AppointmentChat";

// The dedicated, full-page assistant. The floating bubble is intentionally
// hidden on this route (see FloatingChatWidget) so there's only one chat here.
export default function AgentPage() {
  return (
    <div className="space-y-5">
      <header className="mx-auto max-w-3xl text-center">
        <span className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-brand text-white">
          <MessageSquare className="h-6 w-6" />
        </span>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Appointment Assistant</h1>
        <p className="text-slate-500">
          Tell the assistant what you need — a specialty, a doctor, or your reason for the
          visit — and it finds availability and books it for you.
        </p>
      </header>
      <AppointmentChat />
    </div>
  );
}
