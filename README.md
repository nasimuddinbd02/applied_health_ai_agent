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
| Realtime | **WebSocket** chat gateway (`/ws/chat`) with heartbeat, resume and reconnect; **Redis** for distributed connection metadata, chat sessions, idempotency keys and rate limits |
| Eventing | **Redis Streams** consumer groups (the Kafka / Azure Event Hubs stand-in) behind an `EventBus` interface, with retry + dead-letter |
| AI agent | **LangGraph** ReAct agent, tools served by a **FastMCP** server (loaded via `langchain-mcp-adapters`), **LiteLLM** model routing with automatic provider fallback (OpenAI → Anthropic → Gemini) |
| Testing | `pytest` (111 backend tests, incl. a live-Redis multi-instance suite), Node built-in test runner, `ruff` linting |

## Architecture

Both projects follow a strict **n-tier, class-based (OOP) design wired through
a dependency-injection container** — every layer is a class, composed once at
startup. Chat is **realtime and horizontally scalable**: the WebSocket is the
transport, the agent runs on a worker behind an event bus, and Redis is what
lets any instance find the socket that belongs to a given conversation.

```
                  Next.js frontend (src/app routes)
     src/lib/api/services/chat.ts     src/lib/api/services/*.ts
     src/lib/api/realtimeClient.ts    src/lib/api/httpClient.ts
              | WSS  /ws/chat                 | REST (bearer JWT)
              v                               v
  +-------------------- FastAPI instance (chat gateway) -----------------+
  |  api/ws/chat.py       authenticate -> accept -> read/write frames    |
  |  api/routes/*.py      thin REST controllers                          |
  |  realtime/            ConnectionManager (the live sockets, local)    |
  |                       SessionRegistry   (who owns what - in Redis)   |
  |                       RealtimeDispatcher(route a reply to its owner) |
  |  services/chat.py     validate . rate-limit . de-dupe . persist      |
  +-------------------------------+--------------------------------------+
                                  |  publish  chat.user_message
                                  v
                    Redis Streams  (durable, consumer groups, DLQ)
                                  |
                                  v
  +----------- workers/agent_worker.py (inline in dev, or its own pod) --+
  |  load durable history -> LangGraph ReAct agent -> tools via MCP      |
  |  stream agent_status . bind identity . lift slot options             |
  +-------------------------------+--------------------------------------+
                                  |  dispatch(conversation_id, event)
                                  v
                Redis Pub/Sub  ws:node:{server_id}  -->  the instance that
                                                         owns the socket
                                                         --> the customer

  Durable state (survives the socket, the pod and the restart):
      SQLite/SQLModel - conversations, transcripts, appointments, audit
  Coordination state (short-lived, shared, disposable):
      Redis - connection routing, chat sessions, idempotency, rate limits
```

**Backend layout** (standard FastAPI) —

```
backend/app/
  main.py             bootstrap: middleware, router, realtime lifespan
  api/
    deps.py           FastAPI dependencies (bearer token -> User, require_role)
    router.py         builds the one router main.py mounts, from the container
    routes/           REST controllers: auth, patients, doctors, appointments,
                      agent, admin, reception, billing, pharmacy, ops
    ws/chat.py        the WebSocket chat gateway
  core/               config, container (DI composition root), errors,
                      prompts, safety, coordination (idempotency + rate limits)
  services/           business logic: appointment, auth, admin, reception,
                      billing, pharmacy, conversation, chat, agent,
                      ai_gateway, llm
  repositories/       data access — the ONLY place SQL runs (+ the Redis
                      conversation cache)
  db/                 session.py (engine, sessions, additive migrations),
                      seed.py
  models/             SQLModel tables, one module per area
  schemas/            Pydantic request/response DTOs
  realtime/           connection manager, session registry, dispatcher,
                      wire protocol, handshake auth, tool-result reader
  messaging/          Redis client, EventBus + Redis Streams implementation
  workers/            the agent worker
  mcp/                FastMCP tool server + tool implementations
```

Dependency direction is one way: `api → services → repositories → models`, with
`core` available to every layer. Controllers contain no `select()`.

### How the realtime design holds up

The blueprint this implements is [Design.md](docs/Design.md) (a Markdown rendering of
`AI_Agent_Realtime_WebSocket_Architecture.docx`); its Appendix A maps each
section to the code and lists the deliberate differences.

| Concern | How it is handled |
|---|---|
| **Scale-out** | The load balancer picks an instance at *connection* time only; that instance owns the socket. Redis maps `conversation → owning instance`, so a worker anywhere in the cluster can reach any customer. |
| **Server failure** | The WebSocket is disposable. The client reconnects with backoff + jitter, lands on a healthy instance, and that instance replays the conversation from the database. Registry entries carry a TTL, so a dead pod stops being advertised as an owner. |
| **Long-running work** | The gateway never blocks on the agent. It persists the turn, publishes to the bus, and acks; the worker answers asynchronously. |
| **Duplicates** | Every client message carries a `message_id`, claimed once in Redis and again in the database. A reconnect-and-resend is acked as a duplicate and never re-books. Bus events are idempotent on `event_id`. |
| **Identity** | Derived from the JWT, or from a **server-minted** signed guest session. The agent's tool results are read server-side; when it resolves or registers a patient the server binds it to the session and *tells* the browser. The browser never asserts a `patient_id`. |
| **Redis down** | Degrades rather than fails: an in-process event bus, a local connection registry and local idempotency/rate limits keep a single instance fully working. `/health` reports which mode it is in. |
| **Failed turn** | Reported to the customer as a retryable error — never a fabricated success. A *crashed* worker is different: its unacked stream entries are reclaimed and retried. |
| **Abuse** | Per-session rate limit, message-size cap, connection cap per session, heartbeat eviction of dead sockets. |

Swapping Redis Streams for Kafka or Azure Event Hubs means implementing
`app/messaging/event_bus.py:EventBus` and one line in `core/container.py`; nothing
above that line changes. The same is true of SQLite → PostgreSQL, which is the
production database [Design.md](docs/Design.md) calls for.

Key guarantees still live in the **data layer**, not the UI: slot booking and
prescription dispensing are single atomic transactions (no double-booking, no
negative stock), and appointment lifecycle transitions
(`booked → checked_in → in_treatment → completed | cancelled`) are validated
in the service layer.

**Frontend layout** (standard Next.js App Router with `src/`) —

```
frontend/src/
  app/                routes only — pages, layouts, loading/error/not-found,
                      and the /api/session route handler
  components/
    ui/               owned shadcn-style primitives
    chat/             AppointmentChat, FloatingChatWidget
    booking/          BookPanel, IdentityPicker
    layout/           NavBar, StaffShell
    appointments/ auth/ patients/ common/
  context/            AuthContext (the React auth provider)
  lib/
    api/
      client.ts       ApiClient facade + the `api` singleton
      httpClient.ts   REST transport
      realtimeClient.ts  WebSocket transport (backoff + jitter, resume, queue)
      services/       one class per backend area, incl. chat.ts for realtime
    config.ts  format.ts  session.ts  utils.ts  backoff.ts
  types/              wire types mirroring the backend schemas
```

`@/*` resolves to `src/*`, so nothing imports across directories by relative
path. Components live under `src/components` grouped by feature rather than
colocated with a route, since most of them are used by more than one page.

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
audit-logged with model/tokens/cost/latency per run, PII-redacted summaries).
It chats with **anonymous visitors** — no login needed — and can: identify a
returning patient by name, **register a brand-new patient** conversationally,
ground every answer in MCP tool results (doctors, live availability), **book
the appointment**, and file **prescription refill requests** for staff review.
Emergency-sounding messages are deflected to urgent care instead of booking.

The agent holds **no state between turns**: its conversation history is loaded
from Redis (hot) or SQLite (durable) on every run, which is what lets any
worker on any instance continue any conversation after a restart. As it works
it streams `agent_status` events (*checking availability…*), and the slots it
looked at come back as tappable chips rather than something the browser has to
parse out of the reply. The UI is a Messenger-style floating chat on every
public page (with Markdown rendering) plus a dedicated `/agent` page.

## Documentation

Everything beyond this file lives in [`docs/`](docs/).

| Document | What it is |
|---|---|
| [docs/Design.md](docs/Design.md) | The architecture blueprint (the source `.docx` rendered to Markdown), plus an appendix mapping every section to the code and listing the deliberate differences |
| [docs/Processes.md](docs/Processes.md) | Index of the technical process documents, the layering rules they all follow, and the open issues they surfaced |
| [docs/deployment.md](docs/deployment.md) | Docker, Docker Compose and Azure Kubernetes Service — the manifests, the decisions behind them, and the known limitations |

The process documents trace one business task each, end to end — component →
controller → service → repository → database — with sequence diagrams naming the
actual methods:

[book by chatting](docs/process-chat-booking.md) ·
[book from the doctor page](docs/process-direct-booking.md) ·
[reschedule](docs/process-reschedule.md) ·
[register a patient](docs/process-patient-registration.md) ·
[the visit lifecycle](docs/process-visit-lifecycle.md) ·
[refill request](docs/process-refill-request.md) ·
[billing](docs/process-billing.md) ·
[doctor onboarding](docs/process-doctor-onboarding.md) ·
[authentication](docs/process-authentication.md) ·
[reconnect & resume](docs/process-reconnect-resume.md)

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

One command brings up the whole stack — Redis, the MCP tool server, the API +
chat gateway and the frontend — in a single terminal, with each service's output
prefixed and colour-coded. Ctrl+C stops all of them.

```powershell
.\scripts\dev.ps1          # Windows (PowerShell)
```

```bash
./scripts/dev.sh           # macOS / Linux / Git Bash   (or: make dev)
```

```
==> Checking the workspace
==> Redis already listening on 6379 - leaving it alone
==> Starting the MCP tool server on 8077
==> Starting the API + chat gateway on 8000
==> Starting the frontend on 3000

  City Hospital is up
    web       http://localhost:3000
    api       http://localhost:8000/docs
    health    http://localhost:8000/health
    chat ws   ws://localhost:8000/ws/chat
    logs      .dev-logs/
```

On a fresh clone it also does the first-run setup for you: creates
`backend/.env` from `.env.example`, installs frontend dependencies, and seeds
the database. It skips any service that is already listening, so an existing
Redis or a backend you are debugging in your IDE is left alone. Per-service
logs are also written to `.dev-logs/`.

| Flag (PowerShell / bash) | Effect |
|---|---|
| `-NoFrontend` / `--no-frontend` | Backend only |
| `-NoRedis` / `--no-redis` | Skip Redis and use the in-process fallbacks |
| `-NoMcp` / `--no-mcp` | Skip the tool server (the agent then has no tools) |
| `-SeparateWorker` / `--separate-worker` | Run the agent worker as its own process — the production topology |
| `-Seed` / `--seed` | Re-seed the database |
| `-BackendPort` / `BACKEND_PORT=` | Also `-FrontendPort`, `-McpPort`, `-RedisPort` |

The script passes `NEXT_PUBLIC_API_BASE` / `NEXT_PUBLIC_WS_BASE` to the frontend
from whatever `-BackendPort` you chose, and a real environment variable beats a
`.env.local` entry in Next — so the two halves always agree, even on a
non-default port.

### Running the pieces yourself

```bash
make install                 # backend pip + frontend npm
make seed                    # sample doctors/patients/medicines + logins

make run-redis               # Redis on :6379 (or your own service/container)
make run-mcp                 # FastMCP tools on :8077 (needed for the live agent)
make run-backend             # FastAPI + chat gateway on :8000  (/docs, /ws/chat)
make run-worker              # agent worker (only when INLINE_AGENT_WORKER=false)
make run-frontend            # Next.js on :3000

make test                    # backend pytest (Redis-free; exercises the fallbacks)
make test-redis              # the distributed paths against a real Redis
make test-frontend           # frontend unit tests
make lint                    # ruff
```

### Containers and Kubernetes

```bash
make compose-up              # the whole stack in the production topology
make k8s-local               # kind/minikube: in-cluster Redis + PostgreSQL
make k8s-render              # render the AKS manifests without applying them
./deploy/azure/deploy.sh -g <rg> -p <prefix> -t 0.1.0 -H clinic.example.com
```

Compose and Kubernetes both run the **split** topology — the gateway holds
sockets, a separate worker runs the agent — so what you exercise locally is the
shape that ships. See [docs/deployment.md](docs/deployment.md); note that it
requires PostgreSQL, because SQLite cannot be shared safely by several writing
pods.

Copy `.env.example` → `backend/.env` and set an `OPENAI_API_KEY` (and/or
Anthropic/Gemini — the first configured provider wins, the rest are
fallbacks). Without a key the app still runs; only the live agent needs one, and
a turn without one ends in a reported error rather than a fabricated answer.

Redis is optional for a single instance — with it stopped the gateway logs
`Redis unavailable … degrading to single-instance mode`, `/health` reports
`"redis": false`, and everything keeps working in-process. It is required as
soon as you run more than one instance.

### Rehearsing the production topology

`.\scripts\dev.ps1 -SeparateWorker` (or `./scripts/dev.sh --separate-worker`)
starts the gateway with `INLINE_AGENT_WORKER=false` and the agent worker as its
own process. To add a second gateway as well:

```bash
SERVER_ID=gateway-2 uvicorn app.main:app --port 8001
```

Connect a browser to either gateway: the turn goes onto the Redis stream, a
worker picks it up, and the reply is routed back over Redis Pub/Sub to
whichever gateway is holding that customer's socket.

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
