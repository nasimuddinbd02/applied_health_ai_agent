# City Hospital — Backend

FastAPI + SQLModel (SQLite) + an appointment agent (LangGraph) and a FastMCP
tool server, organised as an n-tier, class-based architecture with a DI
container.

## Tiers

```
app/
  main.py                     app bootstrap (CORS, controllers, /health)

  api/                        PRESENTATION — FastAPI controllers (no DB/business code)
    patient_routes.py         register, profile, appointments, treatment history
    doctor_routes.py          directory, profile, availability, appointments
    appointment_routes.py     book + lifecycle (check-in/treatment/checkout/cancel)
    agent_routes.py           appointment-agent chat + history
    ops_routes.py             audit log

  providers/                  BUSINESS LOGIC
    appointment_provider.py   registration, booking, lifecycle, treatments
    agent_provider.py         conversational agent (offline policy + LangGraph)
    gateway_provider.py       AI Gateway: get_llm / run_agent (+ audit)
    llm_factory.py            single ChatLiteLLM (OpenAI→Anthropic→Gemini fallback)

  dbacces/                    DATA ACCESS — all DB code lives here
    database.py               Database class (engine + sessions + init)
    domain_repository.py      patients, doctors, slots, appointments, treatments
    ai_repository.py          audit events

  models/                     DATA STRUCTURES
    entities.py               SQLModel tables
    schemas.py                API request/response DTOs
    results.py                AgentResult

  common/   config.py (provider routing + settings) · prompts.py (agent prompt)
  lib/      safety.py (PII redaction + emergency detection)
  mcp/      FastMCP tool server (@mcp.tool) → AppointmentProvider
  container.py                DI composition root (wires every class once)
  seed.py                     synthetic doctors / availability / patients / history

database/                     SQLite DB files (hospital.db, gitignored)
tests/                        appointment lifecycle + agent behaviour
```

**Dependency direction:** `api → providers → dbacces → models`, with `common` /
`lib` available to all tiers. Controllers contain no `select()`; all persistence
is funnelled through the `dbacces` repositories, and the no-double-booking
guarantee is a single transaction in `DomainRepository`.

## Run

```bash
pip install -r requirements.txt
python -m app.seed                       # build database/hospital.db
uvicorn app.main:app --reload --port 8000
python -m app.mcp.server                 # FastMCP tools on :8077 (live agent)
pytest -q
```

## Model access

`LLMFactory` (the only class that builds an LLM) reads `PROVIDER_PRIORITY`
(default `openai,anthropic,gemini`). The first provider with a key is the
primary `ChatLiteLLM` model; the remaining providers with keys become LiteLLM
fallbacks, so one client transparently fails over. `ChatLiteLLM` comes from the
maintained **`langchain-litellm`** package.

## Mock mode

`settings.offline` is true when `MOCK_MODE=true` or no provider key is set. Then
the appointment agent runs a deterministic, stateful local policy (same
AppointmentProvider, same guarantees) so the app and tests run with no network.
