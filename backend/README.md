# City Hospital — Backend

FastAPI + SQLModel (SQLite) + a realtime chat gateway, a LangGraph appointment
agent and a FastMCP tool server. Layered the standard FastAPI way, with a DI
container as the composition root.

## Layout

```
app/
  main.py                bootstrap: middleware, router, realtime lifespan, /health

  api/                   PRESENTATION — no DB or business code lives here
    deps.py              FastAPI dependencies: bearer token -> User, require_role(...)
    router.py            builds the single router main.py mounts, from the container
    routes/
      auth.py            login, signup, /me
      patients.py        register, profile, appointments, treatment history
      doctors.py         directory, profile, availability, appointments
      appointments.py    book + lifecycle (check-in / treatment / checkout / cancel)
      agent.py           chat REST fallback + transcript
      admin.py           KPIs, doctor onboarding, schedule generation
      reception.py       front-desk queue and console
      billing.py         invoices
      pharmacy.py        medicines and prescriptions
      ops.py             audit log, refill-request queue
    ws/
      chat.py            the WebSocket chat gateway (/ws/chat)

  services/              BUSINESS LOGIC
    appointment.py       registration, booking, lifecycle, treatments
    auth.py              password hashing + JWT issue/verify
    admin.py  reception.py  billing.py  pharmacy.py
    conversation.py      durable conversation state, history, workflow
    chat.py              gateway rules: validate, rate-limit, de-duplicate, publish
    agent.py             the LangGraph ReAct agent (stateless between turns)
    ai_gateway.py        the single entry point for every LLM call (+ audit)
    llm.py               the only class that builds a ChatLiteLLM client

  repositories/          DATA ACCESS — the only place SQL runs
    base.py              BaseRepository (holds the Database, hands out sessions)
    domain.py            patients, doctors, slots, appointments, treatments
    conversation.py      conversations + chat messages
    conversation_cache.py  recent turns in Redis (a cache, never the truth)
    ai.py  user.py  billing.py  pharmacy.py

  db/
    session.py           Database: engine, sessions, create_all + additive migrations
    seed.py              synthetic doctors / availability / patients / history

  models/                SQLModel TABLES, one module per area
    base.py people.py scheduling.py clinical.py billing.py
    pharmacy.py chat.py auth.py audit.py
  schemas/               PYDANTIC DTOs (the API contract)
    patient.py doctor.py appointment.py pharmacy.py auth.py agent.py results.py

  realtime/              WEBSOCKET TRANSPORT
    connection_manager.py  the live sockets this process owns (local, in memory)
    session_registry.py    which instance owns which conversation (Redis)
    dispatcher.py          route a reply to the instance holding the socket
    protocol.py            the wire protocol (client and server frames)
    ws_auth.py             handshake auth + server-minted guest sessions
    tool_results.py        read identity/slots out of tool output, server-side

  messaging/             EVENT TRANSPORT
    redis_client.py      the shared async Redis connection (degrades if absent)
    event_bus.py         the EventBus interface + an in-process implementation
    redis_event_bus.py   Redis Streams: consumer groups, retry, dead-letter
    events.py            the event envelope and the topic catalogue

  workers/agent_worker.py  consumes chat events, runs the agent, routes the reply
  mcp/                     FastMCP tool server (server.py) + implementations (tools.py)
  core/                    config, container (DI), errors, prompts, safety, coordination

database/                  SQLite files (hospital.db, gitignored)
tests/                     lifecycle, agent tools, gateway, realtime, migrations
```

**Dependency direction:** `api → services → repositories → models`, with `core`
available to every layer. Controllers contain no `select()`; all persistence is
funnelled through `repositories/`, and the no-double-booking guarantee is a
single transaction in `DomainRepository`.

`core/container.py` instantiates every class exactly once and wires it. Import
the singleton (`from app.core.container import container`) in controllers, the
MCP server, the worker and tests.

## Run

```bash
pip install -r requirements.txt
python -m app.db.seed                     # build database/hospital.db
redis-server --port 6379                  # optional for one instance, required for many
uvicorn app.main:app --reload --port 8000 # REST + /ws/chat
python -m app.mcp.server                  # FastMCP tools on :8077 (live agent)
python -m app.workers.agent_worker        # only when INLINE_AGENT_WORKER=false
pytest -q
```

## Realtime chat

See [../docs/Processes.md](../docs/Processes.md) for per-process call chains
(booking, the visit lifecycle, refills, billing, auth) with sequence diagrams
naming the exact methods in each layer.

`/ws/chat` is the primary transport; `POST /api/agent/appointment` is a REST
fallback that runs the identical turn without streaming. The socket handler does
transport only — validation, idempotency, persistence and dispatch belong to
`services/chat.py` and `workers/agent_worker.py`. See the root README for the
full architecture and the failure-mode table.

Redis is optional on a single instance: without it the app falls back to an
in-process event bus and a local connection registry, and `/health` reports
`"redis": false`.

## Model access

`LLMFactory` (the only class that builds an LLM) reads `PROVIDER_PRIORITY`
(default `openai,anthropic,gemini`). The first provider with a key is the
primary `ChatLiteLLM` model; the remaining providers with keys become LiteLLM
fallbacks, so one client transparently fails over. `ChatLiteLLM` comes from the
maintained **`langchain-litellm`** package.

Without any provider key the agent cannot run: a turn ends in a reported
`agent_failed` error rather than a fabricated answer.
