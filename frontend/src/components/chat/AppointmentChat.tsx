"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Stethoscope, MessageCircle, X, Send, CalendarClock, WifiOff } from "lucide-react";
import { api } from "@/lib/api/client";
import { ChatService, type ChatTurn } from "@/lib/api/services/chat";
import type { ConnectionState } from "@/lib/api/realtimeClient";
import type { AppointmentOption, ChatIdentity, ToolCall } from "@/types";

const TOKEN_KEY = "ch_token";

interface AppointmentChatProps {
  /** Render as a compact panel that fills its parent (used by the floating
   * widget) instead of a standalone, centered full-page card. */
  floating?: boolean;
  /** Shown as a ✕ button in the header — lets the floating widget collapse
   * itself back down to a bubble. */
  onClose?: () => void;
}

/**
 * Chat over the realtime gateway.
 *
 * The component holds no identity of its own: the server tells it who the
 * visitor turned out to be (an `identity` event, once the assistant has
 * resolved or registered them). Before the realtime renovation this file
 * scraped `"patient_id": N` out of the agent's transcript and believed it —
 * which let the browser assert whose record it was looking at.
 */
export default function AppointmentChat({ floating = false, onClose }: AppointmentChatProps) {
  const [identity, setIdentity] = useState<ChatIdentity | null>(null);
  const [showIdentify, setShowIdentify] = useState(false);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [options, setOptions] = useState<AppointmentOption[]>([]);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const chatRef = useRef<ChatService | null>(null);

  const getAuthToken = useCallback(
    () => (typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY)),
    [],
  );

  // One ChatService for the lifetime of the component; it owns the socket,
  // the reconnect policy and the REST fallback.
  useEffect(() => {
    const chat = new ChatService(
      {
        onTurn: (turn) => setTurns((t) => [...t, turn]),
        onHistory: (history) => setTurns(history),
        onStatus: setStatus,
        onOptions: setOptions,
        onIdentity: setIdentity,
        onError: (message) =>
          setTurns((t) => [...t, { role: "agent", text: `⚠️ ${message}` }]),
        onState: setConnection,
      },
      api.agentSvc,
      getAuthToken,
    );
    chatRef.current = chat;
    chat.start();
    return () => {
      chat.stop();
      chatRef.current = null;
    };
  }, [getAuthToken]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, status, options]);

  const offline = connection === "reconnecting" || connection === "closed";

  function send() {
    const message = input.trim();
    if (!message) return;
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setOptions([]);
    chatRef.current?.send(message);
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

  const initial = identity?.name ? identity.name.charAt(0).toUpperCase() : "?";

  return (
    <div className={
      floating
        ? "flex flex-col h-full bg-white overflow-hidden"
        : "max-w-3xl mx-auto flex flex-col h-[75vh] bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden"
    }>
      <header className="border-b px-5 py-3 flex items-center gap-3 bg-slate-50/80 shrink-0">
        <div className="w-8 h-8 rounded-full bg-brand text-white flex items-center justify-center text-sm font-semibold shrink-0">
          {identity ? initial : <Stethoscope className="h-4 w-4" />}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">
            {identity?.name || (identity ? `Patient #${identity.patient_id}` : "Appointment Assistant")}
          </p>
          <p className="text-xs text-slate-400 flex items-center gap-1">
            {offline && <WifiOff className="h-3 w-3" />}
            {offline
              ? "Reconnecting…"
              : identity
                ? "Identified patient"
                : "Chatting as a guest"}
          </p>
        </div>
        {!identity && (
          <button
            onClick={() => setShowIdentify((s) => !s)}
            className="text-xs text-slate-500 hover:text-brand hover:underline whitespace-nowrap"
          >
            Already a patient?
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

      {showIdentify && !identity && (
        <IdentityPanel
          onSubmit={(name) => {
            setShowIdentify(false);
            chatRef.current?.send(`I'm an existing patient — my name is ${name}.`);
          }}
          onClose={() => setShowIdentify(false)}
        />
      )}

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-6 space-y-5">
        {turns.length === 0 && (
          <div className="text-center text-slate-400 text-sm mt-10 space-y-1">
            <MessageCircle className="h-8 w-8 mx-auto mb-2 text-slate-300" />
            <p>Hi, I&apos;m the appointment assistant — how can I help today?</p>
            <p className="text-xs">
              Book a visit, register as a new patient, or request a prescription refill —
              just tell me what you need.
            </p>
          </div>
        )}
        {turns.map((t, i) => (
          <MessageRow key={i} turn={t} initial={identity ? initial : "?"} />
        ))}
        {options.length > 0 && (
          <SlotOptions
            options={options}
            onPick={(option) => chatRef.current?.selectOption(option)}
          />
        )}
        {status && <TypingIndicator label={status} />}
      </div>

      <div className="border-t p-3 bg-white">
        <div className="flex items-end gap-2 bg-slate-100 rounded-2xl px-3 py-2 focus-within:ring-2 focus-within:ring-brand/40">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => { setInput(e.target.value); autoGrow(e.target); }}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder={offline ? "Reconnecting — your message will send" : "Message the appointment assistant…"}
            className="flex-1 bg-transparent resize-none outline-none text-sm py-1.5 max-h-40"
          />
          <button
            onClick={send}
            disabled={!input.trim()}
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

function MessageRow({ turn, initial }: { turn: ChatTurn; initial: string }) {
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

/** Slots the server offered, as tappable chips. Tapping one sends an ordinary
 * turn — the agent still validates and books it, so the shortcut cannot skip
 * a business rule. */
function SlotOptions({ options, onPick }: {
  options: AppointmentOption[];
  onPick: (option: AppointmentOption) => void;
}) {
  const formatter = useMemo(
    () => new Intl.DateTimeFormat(undefined, {
      weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
    }),
    [],
  );
  return (
    <div className="flex flex-wrap gap-2 pl-10">
      {options.map((option) => (
        <button
          key={option.id}
          onClick={() => onPick(option)}
          className="flex items-center gap-1.5 text-xs border border-teal-200 bg-teal-50 text-brand rounded-full px-3 py-1.5 hover:bg-teal-100 transition"
        >
          <CalendarClock className="h-3.5 w-3.5" />
          {option.start ? formatter.format(new Date(option.start)) : option.id}
        </button>
      ))}
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

/** Live progress from the server (`agent_status`) rather than a generic
 * spinner — the customer can see the assistant is checking availability. */
function TypingIndicator({ label }: { label: string }) {
  return (
    <div className="flex gap-3">
      <div className="w-7 h-7 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center shrink-0"><Stethoscope className="h-3.5 w-3.5" /></div>
      <div className="bg-slate-100 rounded-2xl rounded-tl-sm px-4 py-3 flex gap-2 items-center">
        <span className="flex gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:-0.3s]" />
          <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:-0.15s]" />
          <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" />
        </span>
        <span className="text-xs text-slate-500">{label}</span>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- #
// Optional fast-path identification — never required to start chatting.
//
// It now just *says the name to the assistant*, which looks the patient up with
// its tools and lets the server bind the identity. It used to call the patient
// lookup directly and set identity in the browser, which meant anyone could
// claim any patient id.
// --------------------------------------------------------------------------- #
function IdentityPanel({ onSubmit, onClose }: {
  onSubmit: (name: string) => void;
  onClose: () => void;
}) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit(`${firstName.trim()} ${lastName.trim()}`.trim());
  }

  return (
    <div className="border-b bg-teal-50/40 px-5 py-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-700">Quick identify (optional)</p>
        <button onClick={onClose} aria-label="Close" className="text-slate-400 hover:text-slate-600"><X className="h-4 w-4" /></button>
      </div>

      <form onSubmit={submit} className="flex flex-wrap gap-2">
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
          disabled={!firstName.trim() || !lastName.trim()}
          className="bg-brand text-white rounded-lg px-4 py-1.5 text-sm font-medium disabled:opacity-50"
        >
          Tell the assistant
        </button>
      </form>

      <p className="text-xs text-slate-400">
        The assistant will look you up and confirm before doing anything with your record.
        New here? Just say so in the chat and it&apos;ll register you — or{" "}
        <Link href="/register" className="text-brand hover:underline">register here</Link>.
      </p>
    </div>
  );
}
