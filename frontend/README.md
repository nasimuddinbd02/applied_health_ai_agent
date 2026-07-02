# City Hospital — Frontend

Next.js (App Router) + TypeScript + Tailwind, organised as an **n-tier,
object-oriented** architecture. Talks to the FastAPI backend only over REST
(base URL from `NEXT_PUBLIC_API_BASE`).

## Tiers (object-oriented)

```
app/                 PRESENTATION — Next.js routes + components (App Router)
models/types.ts      DATA STRUCTURES — domain + DTO interfaces
providers/           BUSINESS LOGIC — service classes + ApiProvider facade
  baseService.ts       BaseService (holds the HttpClient)
  domainService.ts     DomainService (patients + doctors)
  appointmentService.ts AppointmentService (book + lifecycle)
  agentService.ts      AgentService (appointment-agent chat)
  opsService.ts        OpsService (health + audit)
  apiProvider.ts       ApiProvider composes the services; exports `api` singleton
dbacces/             DATA ACCESS — HttpClient class (the single fetch wrapper)
common/config.ts     CROSS-CUTTING CONFIG — AppConfig (API base URL)
lib/format.ts        UTILITIES — Formatter (currency, datetime, status badges)
test/                unit tests (Node built-in test runner)
```

**OOP + DI:** `HttpClient` is injected into each `*Service` (which extend
`BaseService`); `ApiProvider` is the composition root that wires them and is
exported as the `api` singleton. React components stay functional (idiomatic)
and call through the `api` facade.

## Run

```bash
npm install
echo "NEXT_PUBLIC_API_BASE=http://localhost:8000" > .env.local
npm run dev          # http://localhost:3000
npm run build        # production build / type-check
npm test             # unit tests (test/)
```

## Pages

| Route | What it does |
|-------|--------------|
| `/` | Dashboard: doctor cards, recent patients, AI agent activity |
| `/register` | Patient self-registration form |
| `/doctors` | Doctor directory |
| `/doctors/[id]` | Doctor profile + availability + **book an appointment** |
| `/patients/[id]` | Patient profile + appointments + **treatment history** |
| `/appointments/[id]` | Appointment detail + **check-in → treatment → checkout** |
| `/agent` | **Appointment agent** chat that gathers info and books |
| `/audit` | Audit & cost of every agent run |

Reads use Server Components; the registration, booking, lifecycle and chat
widgets are Client Components (`"use client"`).
