"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/providers/apiProvider";
import type { PatientMatch } from "@/models/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface PatientIdentity {
  id: number;
  label: string;
}

/** Find-your-profile form: name lookup first (people know their name, not
 * their database id), patient-ID entry as a fallback. Shared by the booking
 * panel and anywhere else that must resolve "which patient is this?". */
export default function IdentityPicker({ onIdentified }: { onIdentified: (i: PatientIdentity) => void }) {
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
        setError("No matching patient found. Check the spelling, or register below if you're new.");
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
    <div className="space-y-3">
      <div className="flex rounded-lg bg-slate-100 p-1 text-sm max-w-xs">
        <button
          type="button"
          onClick={() => { setMode("name"); setError(""); }}
          className={`flex-1 py-1.5 rounded-md transition ${mode === "name" ? "bg-white shadow text-brand font-medium" : "text-slate-500"}`}
        >
          By name
        </button>
        <button
          type="button"
          onClick={() => { setMode("id"); setError(""); }}
          className={`flex-1 py-1.5 rounded-md transition ${mode === "id" ? "bg-white shadow text-brand font-medium" : "text-slate-500"}`}
        >
          By patient ID
        </button>
      </div>

      {mode === "name" ? (
        <form onSubmit={findByName} className="flex flex-wrap gap-2">
          <Input
            value={firstName} onChange={(e) => setFirstName(e.target.value)}
            placeholder="First name" required className="flex-1 min-w-[9rem] h-9"
          />
          <Input
            value={lastName} onChange={(e) => setLastName(e.target.value)}
            placeholder="Last name" required className="flex-1 min-w-[9rem] h-9"
          />
          <Button size="sm" disabled={loading || !firstName.trim() || !lastName.trim()}>
            {loading ? "Checking…" : "Find me"}
          </Button>
        </form>
      ) : (
        <form onSubmit={useId} className="flex gap-2">
          <Input
            type="number" value={patientIdInput} onChange={(e) => setPatientIdInput(e.target.value)}
            placeholder="Patient ID" required className="flex-1 h-9"
          />
          <Button size="sm" disabled={loading || !patientIdInput}>
            {loading ? "Checking…" : "Continue"}
          </Button>
        </form>
      )}

      {matches && (
        <div className="space-y-1.5">
          <p className="text-xs text-slate-500">We found more than one match — which one is you?</p>
          {matches.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => onIdentified({ id: m.id, label: m.name })}
              className="w-full text-left border rounded-lg px-3 py-2 text-sm bg-white hover:border-brand hover:bg-teal-50/40"
            >
              <span className="font-medium">{m.name}</span>
              <span className="text-slate-400 text-xs ml-2">DOB {m.date_of_birth || "—"}</span>
            </button>
          ))}
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      <p className="text-xs text-slate-400">
        New patient? <Link href="/register" className="text-brand hover:underline">Register</Link> ·
        Already have an account? <Link href="/login" className="text-brand hover:underline">Sign in</Link>
      </p>
    </div>
  );
}
