"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Stethoscope, MessageCircle, X, Send } from "lucide-react";
import { api } from "@/providers/apiProvider";
import { useAuth } from "../_auth/AuthContext";
import type { PatientMatch, ToolCall, TranscriptEntry } from "@/models/types";

interface Turn {
  role: "patient" | "agent";
  text: string;
  tools?: ToolCall[];
}

interface Identity {
  id: number;
  label: string;
}

/** Scan the agent's tool-call transcript for a patient_id it resolved (via
 * find_patient_by_name / register_patient / get_patient) so the UI can pick
 * up on identity the agent discovered through conversation, without a
 * separate blocking form. */
function extractIdentity(transcript: TranscriptEntry[]): Identity | null {
  for (const entry of transcript ?? []) {
    if (!entry?.content) continue;
    const raw = typeof entry.content === "string" ? entry.content : JSON.stringify(entry.content);
    // Tool results can arrive as nested, escaped JSON (e.g. a list of content
    // blocks whose "text" field is itself a JSON string) — strip the escaping
    // so the quote-anchored regexes below match regardless of nesting depth.
    const content = raw.replace(/\\/g, "");
    const idMatch = content.match(/"patient_id"\s*:\s*(\d+)/);
    if (idMatch) {
      const nameMatch = content.match(/"name"\s*:\s*"([^"]+)"/);
      return { id: Number(idMatch[1]), label: nameMatch ? nameMatch[1] : `Patient #${idMatch[1]}` };
    }
  }
  return null;
}

interface AppointmentChatProps {
  /** Render as a compact panel that fills its parent (used by the floating
   * widget) instead of a standalone, centered full-page card. */
  floating?: boolean;
  /** Shown as a ✕ button in the header — lets the floating widget collapse
   * itself back down to a bubble. */
  onClose?: () => void;
}

export default function AppointmentChat({ floating = false, onClose }: AppointmentChatProps) {
  const { user } = useAuth();
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [showIdentify, setShowIdentify] = useState(false);
  const [threadId, setThreadId] = useState<string | undefined>(undefined);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // If the visitor is already logged in as a patient, identify them automatically.
  useEffect(() => {
    if (user?.role === "patient" && user.patient_id) {
      setIdentity({ id: user.patient_id, label: user.name || `Patient #${user.patient_id}` });
    }
  }, [user]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, loading]);

  async function send() {
    const message = input.trim();
    if (!message) return;
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setTurns((t) => [...t, { role: "patient", text: message }]);
    setLoading(true);
    try {
      const res = await api.agent({ patient_id: identity?.id ?? null, message, thread_id: threadId });
      setThreadId(res.thread_id);
      if (!identity) {
        const found = extractIdentity(res.transcript);
        if (found) setIdentity(found);
      }
      setTurns((t) => [...t, { role: "agent", text: res.final_text, tools: res.tool_calls }]);
    } catch (err: any) {
      setTurns((t) => [...t, { role: "agent", text: `Sorry — something went wrong: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function autoGrow(el: HTMLTextAreaElement) {
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  return (
    <div className={
      floating
        ? "flex flex-col h-full bg-white overflow-hidden"
        : "max-w-3xl mx-auto flex flex-col h-[75vh] bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden"
    }>
      <header className="border-b px-5 py-3 flex items-center gap-3 bg-slate-50/80 shrink-0">
        <div className="w-8 h-8 rounded-full bg-brand text-white flex items-center justify-center text-sm font-semibold shrink-0">
          {identity ? identity.label.charAt(0).toUpperCase() : <Stethoscope className="h-4 w-4" />}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{identity ? identity.label : "Appointment Assistant"}</p>
          <p className="text-xs text-slate-400">{identity ? "Identified patient" : "Chatting as a guest"}</p>
        </div>
        {!user && (
          <button
            onClick={() => setShowIdentify((s) => !s)}
            className="text-xs text-slate-500 hover:text-brand hover:underline whitespace-nowrap"
          >
            {identity ? "Not you? Switch" : "Already a patient?"}
          </button>
        )}
        {onClose && (
          <button
            onClick={onClose}
            aria-label="Close chat"
            className="text-slate-400 hover:text-slate-600 shrink-0 w-6 h-6 flex items-center justify-center rounded-full hover:bg-slate-200/70"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </header>

      {showIdentify && !user && (
        <IdentityPanel
          onIdentified={(i) => { setIdentity(i); setShowIdentify(false); }}
          onClose={() => setShowIdentify(false)}
        />
      )}

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-6 space-y-5">
        {turns.length === 0 && (
          <div className="text-center text-slate-400 text-sm mt-10 space-y-1">
            <MessageCircle className="h-8 w-8 mx-auto mb-2 text-slate-300" />
            <p>Hi, I'm the appointment assistant — how can I help today?</p>
            <p className="text-xs">
              Book a visit, register as a new patient, or request a prescription refill —
              just tell me what you need.
            </p>
          </div>
        )}
        {turns.map((t, i) => (
          <MessageRow key={i} turn={t} initial={identity ? identity.label.charAt(0).toUpperCase() : "?"} />
        ))}
        {loading && <TypingIndicator />}
      </div>

      <div className="border-t p-3 bg-white">
        <div className="flex items-end gap-2 bg-slate-100 rounded-2xl px-3 py-2 focus-within:ring-2 focus-within:ring-brand/40">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => { setInput(e.target.value); autoGrow(e.target); }}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Message the appointment assistant…"
            className="flex-1 bg-transparent resize-none outline-none text-sm py-1.5 max-h-40"
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            aria-label="Send"
            className="shrink-0 w-9 h-9 rounded-full bg-brand text-white flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed hover:bg-brand/90 transition"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
        <p className="text-[11px] text-slate-400 mt-1.5 px-1">Press Enter to send · Shift+Enter for a new line</p>
      </div>
    </div>
  );
}

function MessageRow({ turn, initial }: { turn: Turn; initial: string }) {
  const isPatient = turn.role === "patient";
  return (
    <div className={`flex gap-3 ${isPatient ? "flex-row-reverse" : ""}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 ${
        isPatient ? "bg-brand text-white" : "bg-slate-200 text-slate-600"
      }`}>
        {isPatient ? initial : <Stethoscope className="h-3.5 w-3.5" />}
      </div>
      <div className={`max-w-[75%] ${isPatient ? "items-end" : "items-start"} flex flex-col gap-1`}>
        <div className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isPatient
            ? "bg-brand text-white rounded-tr-sm whitespace-pre-wrap"
            : "bg-slate-100 text-slate-800 rounded-tl-sm"
        }`}>
          {isPatient ? turn.text : <MarkdownMessage text={turn.text} />}
        </div>
        {turn.tools && turn.tools.length > 0 && <ToolCallDetails tools={turn.tools} />}
      </div>
    </div>
  );
}

function MarkdownMessage({ text }: { text: string }) {
  return (
    <div className="space-y-2 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="leading-relaxed">{children}</p>,
          ul: ({ children }) => <ul className="list-disc pl-5 space-y-0.5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 space-y-0.5">{children}</ol>,
          li: ({ children }) => <li>{children}</li>,
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noreferrer" className="text-brand underline">
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="bg-slate-200/70 rounded px-1 py-0.5 text-xs font-mono">{children}</code>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

function ToolCallDetails({ tools }: { tools: ToolCall[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="text-xs">
      <button onClick={() => setOpen((o) => !o)} className="text-slate-400 hover:text-brand">
        {open ? "▾" : "▸"} used {tools.length} tool{tools.length > 1 ? "s" : ""}
      </button>
      {open && (
        <div className="mt-1 flex flex-wrap gap-1">
          {tools.map((tc, j) => (
            <span key={j} className="font-mono text-[10px] bg-teal-50 text-brand border border-teal-200 rounded px-1.5 py-0.5">
              {tc.tool}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="w-7 h-7 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center shrink-0"><Stethoscope className="h-3.5 w-3.5" /></div>
      <div className="bg-slate-100 rounded-2xl rounded-tl-sm px-4 py-3 flex gap-1 items-center">
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:-0.3s]" />
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:-0.15s]" />
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" />
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- #
// Optional fast-path identification — never required to start chatting.
// The agent can also identify or register the patient conversationally.
// --------------------------------------------------------------------------- #
function IdentityPanel({ onIdentified, onClose }: { onIdentified: (i: Identity) => void; onClose: () => void }) {
  const [mode, setMode] = useState<"name" | "id">("name");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [patientIdInput, setPatientIdInput] = useState("");
  const [matches, setMatches] = useState<PatientMatch[] | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function findByName(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setMatches(null);
    setLoading(true);
    try {
      const found = await api.lookupPatient(firstName.trim(), lastName.trim());
      if (found.length === 0) {
        setError("No matching patient found — you can also just tell the assistant you're new.");
      } else if (found.length === 1) {
        onIdentified({ id: found[0].id, label: found[0].name });
      } else {
        setMatches(found);
      }
    } catch (err: any) {
      setError(err.message || "Lookup failed");
    } finally {
      setLoading(false);
    }
  }

  async function useId(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const id = Number(patientIdInput);
    if (!id) return;
    setLoading(true);
    try {
      const p = await api.patient(id);
      onIdentified({ id: p.id, label: p.name });
    } catch {
      setError(`No patient found with id #${id}.`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border-b bg-teal-50/40 px-5 py-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-700">Quick identify (optional)</p>
        <button onClick={onClose} aria-label="Close" className="text-slate-400 hover:text-slate-600"><X className="h-4 w-4" /></button>
      </div>

      <div className="flex rounded-lg bg-white border p-1 text-sm max-w-xs">
        <button
          onClick={() => { setMode("name"); setError(""); }}
          className={`flex-1 py-1 rounded-md transition ${mode === "name" ? "bg-brand text-white" : "text-slate-500"}`}
        >
          By name
        </button>
        <button
          onClick={() => { setMode("id"); setError(""); }}
          className={`flex-1 py-1 rounded-md transition ${mode === "id" ? "bg-brand text-white" : "text-slate-500"}`}
        >
          By ID
        </button>
      </div>

      {mode === "name" ? (
        <form onSubmit={findByName} className="flex flex-wrap gap-2">
          <input
            value={firstName} onChange={(e) => setFirstName(e.target.value)}
            placeholder="First name" required
            className="border rounded-lg px-3 py-1.5 text-sm flex-1 min-w-[8rem]"
          />
          <input
            value={lastName} onChange={(e) => setLastName(e.target.value)}
            placeholder="Last name" required
            className="border rounded-lg px-3 py-1.5 text-sm flex-1 min-w-[8rem]"
          />
          <button
            disabled={loading || !firstName.trim() || !lastName.trim()}
            className="bg-brand text-white rounded-lg px-4 py-1.5 text-sm font-medium disabled:opacity-50"
          >
            {loading ? "Checking…" : "Find me"}
          </button>
        </form>
      ) : (
        <form onSubmit={useId} className="flex gap-2">
          <input
            type="number" value={patientIdInput} onChange={(e) => setPatientIdInput(e.target.value)}
            placeholder="Patient ID"
            className="border rounded-lg px-3 py-1.5 text-sm flex-1"
          />
          <button
            disabled={loading || !patientIdInput}
            className="bg-brand text-white rounded-lg px-4 py-1.5 text-sm font-medium disabled:opacity-50"
          >
            {loading ? "Checking…" : "Continue"}
          </button>
        </form>
      )}

      {matches && (
        <div className="space-y-1.5">
          <p className="text-xs text-slate-500">Multiple matches — which one is you?</p>
          {matches.map((m) => (
            <button
              key={m.id}
              onClick={() => onIdentified({ id: m.id, label: m.name })}
              className="w-full text-left border rounded-lg px-3 py-1.5 text-sm bg-white hover:border-brand"
            >
              <span className="font-medium">{m.name}</span>
              <span className="text-slate-400 text-xs ml-2">DOB {m.date_of_birth || "—"}</span>
            </button>
          ))}
        </div>
      )}

      {error && <p className="text-red-600 text-xs">{error}</p>}

      <p className="text-xs text-slate-400">
        New here? No need — just tell the assistant your name in the chat and it'll register you.
        Prefer a form instead? <Link href="/register" className="text-brand hover:underline">Register here</Link>.
      </p>
    </div>
  );
}
