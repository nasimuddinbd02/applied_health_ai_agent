# City Hospital — Frontend

Next.js (App Router) + TypeScript + Tailwind, in the standard `src/` layout.
Talks to the FastAPI backend over REST (`NEXT_PUBLIC_API_BASE`) and over a
WebSocket for the chat gateway (`NEXT_PUBLIC_WS_BASE`, defaulting to the API
origin with `http` → `ws`).

## Layout

```
src/
  app/                   ROUTES ONLY — pages, layouts, loading/error/not-found
    api/session/route.ts   route handler that mirrors the JWT into a cookie
                           so Server Components can make authenticated calls

  components/            REACT COMPONENTS, grouped by feature
    ui/                    owned shadcn-style primitives (button, card, table…)
    common/ui.tsx          small shared building blocks
    layout/                NavBar, StaffShell
    chat/                  AppointmentChat, FloatingChatWidget
    booking/               BookPanel, IdentityPicker
    appointments/          LifecyclePanel
    patients/              PatientInvoices
    auth/                  RegisterForm

  context/AuthContext.tsx  the auth React context (login, signup, logout, user)

  lib/
    api/
      client.ts            ApiClient — composes the services, exports `api`
      httpClient.ts        the single REST fetch wrapper (bearer JWT)
      realtimeClient.ts    the WebSocket transport: reconnect with exponential
                           backoff + jitter, session resume, an outbound queue
      services/
        base.ts            BaseService (holds the injected HttpClient)
        domain.ts appointment.ts auth.ts admin.ts reception.ts
        billing.ts pharmacy.ts ops.ts agent.ts
        chat.ts            realtime chat over realtimeClient, REST fallback
    config.ts              AppConfig (API + WebSocket base URLs)
    format.ts              Formatter (currency, datetime, status badges)
    session.ts  utils.ts  backoff.ts

  types/index.ts           wire types mirroring the backend schemas

test/                      unit tests (Node built-in test runner)
```

`@/*` resolves to `src/*`, so nothing imports across directories by relative
path. Components live under `src/components` grouped by feature rather than
colocated with a route, because most are used by more than one page.

**OOP + DI:** `HttpClient` is injected into each `*Service` (all extending
`BaseService`); `ApiClient` is the composition root that wires them and is
exported as the `api` singleton. React components stay functional and call
through that facade.

## Run

```bash
npm install
cp .env.local.example .env.local     # NEXT_PUBLIC_API_BASE / NEXT_PUBLIC_WS_BASE
npm run dev          # http://localhost:3000
npm run build        # production build / type-check
npm test             # unit tests (test/)
```

## Pages

| Route | What it does |
|-------|--------------|
| `/` | Dashboard: doctor cards, recent patients, AI agent activity |
| `/register` | Patient self-registration form |
| `/login` | Sign in (patient, doctor, receptionist, admin) |
| `/doctors` | Doctor directory |
| `/doctors/[id]` | Doctor profile + availability + **book an appointment** |
| `/patients/[id]` | Patient profile + appointments + **treatment history** + invoices |
| `/appointments/[id]` | Appointment detail + **check-in → treatment → checkout** |
| `/invoices/[id]` | Invoice detail + payment |
| `/reception` | Front-desk queue console |
| `/admin` | KPIs, doctor onboarding, schedule builder, pharmacy stock |
| `/agent` | **Appointment agent** chat (also a floating widget on public pages) |
| `/audit` | Audit & cost of every agent run |

Reads use Server Components; the registration, booking, lifecycle and chat
widgets are Client Components (`"use client"`).

## The chat client

`lib/api/realtimeClient.ts` owns the socket and nothing else: it reconnects with
full-jitter backoff, remembers the guest session token and conversation id (so a
refresh resumes the same conversation), answers server pings, and queues
outbound messages while offline — each keeping its original `message_id`, which
the server uses to reject a duplicate rather than run the workflow twice.

`lib/api/services/chat.ts` turns the wire protocol into the callbacks the UI
wants (`onTurn`, `onStatus`, `onOptions`, `onIdentity`) and falls back to the
REST endpoint when a WebSocket cannot be established.

The browser never asserts a patient identity — the server resolves it from the
session and announces it in an `identity` event.
