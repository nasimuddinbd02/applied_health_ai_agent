# City Hospital — Clinic Management System with an AI Appointment Agent

A full-stack clinic management application for a small hospital or clinic:
patients register and book against doctors' live schedules (on the site or by
simply *chatting* with an AI assistant), the front desk runs the day from a
check-in queue, doctors record treatments and dispense medicines from tracked
pharmacy stock, checkout generates an invoice automatically, and an admin
console onboards doctors and builds their schedules from a weekly template.

## Technology

| Layer | Stack |
|---|---|
| Frontend | **Next.js 14** (App Router, React 18, TypeScript), **Tailwind CSS** with a shadcn/ui-style component library (Radix primitives, CVA, lucide-react icons, sonner toasts), Inter via `next/font` |
| Backend | **Python / FastAPI**, SQLModel ORM over **SQLite**, JWT auth (`python-jose` + `bcrypt`) |
| AI agent | **LangGraph** ReAct agent, tools served by a **FastMCP** server (loaded via `langchain-mcp-adapters`), **LiteLLM** model routing with automatic provider fallback (OpenAI → Anthropic → Gemini) |
| Testing | `pytest` (47 backend tests), Node built-in test runner, `ruff` linting |

## Architecture

Both projects follow a strict **n-tier, class-based (OOP) design wired through
a dependency-injection container** — every layer is a class, composed once at
startup:

```
                       Next.js frontend (app/ pages)
                    providers/*Service.ts  →  ApiProvider facade
                          dbacces/httpClient.ts (bearer JWT)
                                    │ REST
                                    ▼
   FastAPI  ── controllers (app/api/*Controller, thin routes)
                  │  domain errors → global DomainErrorRegistrar (JSON 4xx)
                  ▼
      providers (business logic):
      Appointment · Auth · Admin · Reception · Billing · Pharmacy
                  │                        │
                  ▼                        ▼
      repositories (app/dbacces/*)   AI GATEWAY (GatewayProvider)
      SQLModel → SQLite              async run_agent + audit log
      · atomic no-double-booking          │
      · atomic stock-checked dispensing   ▼
      · lifecycle state machine     LangGraph ReAct agent
                                          │ tools via MCP
                                          ▼
                                    FastMCP server (:8077)
                                    find/register patient · doctors ·
                                    availability · book · refill
                                          │
                                          ▼
                                    LiteLLM → OpenAI / Anthropic / Gemini
```

**Backend layout** — `models/` (SQLModel entities + Pydantic DTOs) ·
`dbacces/` (repositories; the *only* place SQL runs) · `providers/` (business
rules) · `api/` (controller classes exposing `APIRouter`s) · `lib/` (authz
dependencies, global error handlers, safety/redaction) · `common/` (settings,
prompt registry) · `container.py` (composition root — every class is
instantiated and wired exactly once).

Key guarantees live in the **data layer**, not the UI: slot booking and
prescription dispensing are single atomic transactions (no double-booking, no
negative stock), and appointment lifecycle transitions
(`booked → checked_in → in_treatment → completed | cancelled`) are validated
in the provider.

**Frontend layout** mirrors it — `models/types.ts` · `dbacces/httpClient.ts` ·
`providers/*Service.ts` composed into one `ApiProvider` facade · `app/` pages
(Server Components for initial data, client components for interactivity, with
`loading.tsx` / `error.tsx` / `not-found.tsx` route conventions) ·
`components/ui/` (owned shadcn-style primitives) · shared building blocks in
`app/_components/`.

### Roles & security

JWT-based auth with four roles enforced **server-side** via a declarative
`require_role(...)` FastAPI dependency (the UI additionally adapts per role):

| Role | Can do |
|---|---|
| **Patient** | Self-register, book (by name — no login required), see own appointments, treatments, prescriptions, invoices |
| **Doctor** | Own login (auto-provisioned by admin), record treatments + dispense medicines, work the day's queue |
| **Receptionist** | Front-desk console: today's queue, check-in / checkout / cancel, take invoice payments |
| **Admin** | Console: KPIs, onboard/edit doctors (creates their login), generate schedules from a weekly template, pharmacy stock, AI audit log |

### The AI appointment agent

A LangGraph ReAct agent behind a single **AI Gateway** entry point (async,
audit-logged with model/tokens/cost per run, PII-redacted summaries). It chats
with **anonymous visitors** — no login needed — and can: identify a returning
patient by name, **register a brand-new patient** conversationally, ground
every answer in MCP tool results (doctors, live availability), **book the
appointment**, and file **prescription refill requests** for staff review.
Emergency-sounding messages are deflected to urgent care instead of booking.
The UI is a Messenger-style floating chat on every public page (with Markdown
rendering) plus a dedicated `/agent` page.

## Feature highlights

- **Booking without friction** — patients pick a day on a date strip and a
  time chip; identity is resolved from the login session or by first/last
  name lookup (no "patient ID" required anywhere).
- **Front-desk queue** — today's appointments with live status counters and
  one-click check-in → treatment → checkout.
- **Treatment + pharmacy** — diagnosis/notes plus structured prescriptions
  that atomically decrement tracked medicine stock; low-stock alerts.
- **Billing** — checkout auto-drafts an invoice from the doctor's consultation
  fee; receptionists mark paid / void; patients see their invoices.
- **Admin schedule builder** — weekly template (days × hours × slot length ×
  weeks) expanded idempotently into concrete slots; booked slots protected.
- **Observability** — every agent run recorded (feature, model, tokens,
  latency, estimated cost) in an admin audit view.

## Quickstart

```bash
make install                 # backend pip + frontend npm
make seed                    # sample doctors/patients/medicines + logins

make run-backend             # FastAPI on :8000  (/docs for OpenAPI)
make run-mcp                 # FastMCP tools on :8077 (needed for the live agent)
make run-frontend            # Next.js on :3000

make test                    # backend pytest
make test-frontend           # frontend unit tests
make lint                    # ruff
```

Copy `.env.example` → `backend/.env` and set an `OPENAI_API_KEY` (and/or
Anthropic/Gemini — the first configured provider wins, the rest are
fallbacks). Without a key the app still runs; only the live agent needs one.

**Seeded logins** (password `clinic123`): `admin@clinic.test` ·
`reception@clinic.test` · any doctor (`chen@cityhospital.example`, …) · any
patient (`olivia@example.com`, …).

## Try these flows

1. **Chat-book as a stranger** — open the site, the assistant pops up; say
   *"I'm new here, I need a cardiology appointment"* and let it register you
   and book.
2. **Run the front desk** — log in as `reception@clinic.test`: check a
   patient in, open the appointment, record treatment with medicines, check
   out, take payment on the generated invoice.
3. **Onboard a doctor** — log in as `admin@clinic.test`: add a doctor (login
   auto-created), generate two weeks of slots, then book them from the public
   site.

---
Developed by **Nasim Uddin**.
