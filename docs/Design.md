# AI Customer Service Agent — Real-Time WebSocket & Multi-Server Architecture

**Architecture Blueprint for Scheduling, Rescheduling, Medication Refill & Customer Email**

> **Purpose:** Provide a production-oriented reference architecture that can be
> used to renovate an existing customer-facing healthcare application with
> real-time AI chat and horizontally scalable WebSocket services.

*Markdown rendering of `AI_Agent_Realtime_WebSocket_Architecture.docx`. Sections
1–26 are the design document as written. [Appendix A](#appendix-a--implementation-status-in-this-repository)
is an addition: it records how far this repository implements the blueprint and
where it deliberately differs.*

---

## 1. Executive Summary

The proposed architecture separates real-time customer communication from AI
orchestration and business operations. WebSocket provides the persistent
customer-to-chat connection. A load balancer selects the backend when the
WebSocket connection is established; subsequent messages travel over that
existing connection and are not independently load-balanced. Redis maintains
distributed connection/session metadata, while an event bus such as Kafka or
Azure Event Hubs handles asynchronous events and long-running work. LangGraph
orchestrates specialized agents, and deterministic APIs perform scheduling,
rescheduling, refill, customer lookup, and email operations.

## 2. Target Architecture

```
Customer Web / Mobile App
        |
        | WebSocket over WSS
        v
+-------------------------+
| Load Balancer / Ingress  |
+------------+------------+
             |
     +-------+-------+----------------+
     |               |                |
     v               v                v
+---------+     +---------+      +---------+
| Chat 1  |     | Chat 2  |      | Chat 3  |
| FastAPI |     | FastAPI |      | FastAPI |
+----+----+     +----+----+      +----+----+
     |               |                |
     +---------------+----------------+
                     |
                  +--v--+
                  |Redis |
                  +--+--+
                     |
             Connection / Session
                Coordination
                     |
                  +--v------------------+
                  | Event Bus            |
                  | Kafka / Azure EH     |
                  +--+------------------+
                     |
          +----------+-----------+
          |                      |
          v                      v
   +-------------+        +-------------+
   | Agent       |        | Background  |
   | Service     |        | Workers     |
   | LangGraph   |        |             |
   +------+------+        +------+------+
          |                      |
    +-----+------+---------+-----+------+
    |            |         |            |
    v            v         v            v
Scheduling    Refill   Customer     Email
API           API      API           API
    |            |         |            |
    +------------+---------+------------+
                         |
                   +-----v------+
                   | PostgreSQL |
                   | Durable    |
                   | State      |
                   +------------+
```

## 3. Core Design Principles

- WebSocket is the transport for real-time bidirectional customer communication.
- The WebSocket connection is owned by the FastAPI/Chat server that accepted it.
- The load balancer chooses a backend when a new connection is established; it
  does not select a new backend for every WebSocket message.
- Redis is not the WebSocket server. It stores distributed metadata such as
  customer-to-chat-server mapping, session data, presence, and coordination
  information.
- Conversation and workflow state must not live only in process memory; persist
  important state in PostgreSQL and/or Redis.
- The LLM interprets and orchestrates; deterministic APIs validate authorization
  and perform real business operations.
- Long-running operations should use an event bus/background workers rather than
  blocking the WebSocket handler.
- Sensitive actions such as medication refill should have explicit business
  rules, authorization, audit logging, and human review where required.

## 4. Why WebSocket?

WebSocket is appropriate when the application needs a continuously open,
bidirectional channel. The server can push agent tokens, progress events,
appointment options, confirmations, errors, and notifications without polling.

Client:

```
wss://api.company.com/ws/chat
```

Example client message:

```json
{
  "type": "user_message",
  "conversation_id": "conv-123",
  "message": "Reschedule my appointment"
}
```

Example server event:

```json
{
  "type": "agent_message",
  "conversation_id": "conv-123",
  "message": "I found your appointment. Let me check availability."
}
```

**Alternative:** Server-Sent Events (SSE) can be used when the primary
requirement is server-to-client streaming. WebSocket is preferable for a full
interactive chat experience with bidirectional events.

## 5. WebSocket Connection Lifecycle

### 5.1 Initial Connection

```
1. Browser opens:
   wss://api.company.com/ws/chat

2. TCP/TLS connection reaches the load balancer.

3. Load balancer selects Chat Server 2.

4. WebSocket upgrade/handshake succeeds.

5. Chat Server 2 now owns the live WebSocket connection.

Customer  =======================  Chat Server 2
              persistent WSS
```

### 5.2 Subsequent Customer Messages

This is the most important behavior for the multi-server design: the browser
does not create a new load-balancing request for each WebSocket message. The
message is written to the already-established TCP/WebSocket connection.

```
Customer
   |
   | existing WebSocket connection
   v
Chat Server 2
   |
   +--> Agent Service

NOT:
Customer -> Load Balancer -> random server -> every message
```

### 5.3 Load Balancer Role

A reverse-proxy load balancer may remain physically in the network path, but it
maintains the established frontend/backend connection mapping. It does not
perform a fresh backend selection for every WebSocket frame.

```
Browser
   |
   | frontend TCP connection
   v
Load Balancer
   |
   | backend TCP connection
   v
Chat Server 2

The load balancer maintains the association:
frontend connection <-> backend Server 2
```

## 6. Multi-Server Connection Management

```
Redis:
customer-123 -> chat-server-2
customer-456 -> chat-server-1

Chat Server 2 process memory:
connections["customer-123"] = websocket_object

Important:
Redis stores metadata.
The actual WebSocket object remains inside Chat Server 2.
```

If an agent worker on another server needs to notify customer-123, it uses the
connection mapping and a distributed messaging mechanism to deliver the event to
Chat Server 2. Chat Server 2 then writes the message to the customer's existing
WebSocket.

## 7. End-to-End Request Trace: Reschedule

```
Customer
  |
  | "Please reschedule my appointment"
  v
Existing WebSocket
  |
  v
Chat Server 2
  |
  v
Agent Service / LangGraph
  |
  +--> Identify customer
  +--> Retrieve appointment
  +--> Check availability
  +--> Validate business rules
  +--> Reschedule Appointment API
  |
  v
Result: SUCCESS
  |
  v
Agent generates response
  |
  v
Chat Server 2
  |
  | existing WebSocket
  v
Customer
```

## 8. Long-Running Refill Trace

```
Customer
  |
  | "Refill my medication"
  v
Chat Server 2
  |
  v
LangGraph / Refill Agent
  |
  +--> Customer lookup
  +--> Medication/prescription lookup
  +--> Eligibility/business-rule check
  |
  v
Event Bus / Worker
  |
  v
Pharmacy API
  |
  v
REFILL_COMPLETED event
  |
  v
Notification / Chat routing
  |
  v
Chat Server 2
  |
  | existing WebSocket
  v
Customer
```

For medication workflows, the agent should not independently make clinical
judgments. Eligibility, authorization, prescription status, and other controlled
decisions should be enforced by trusted services/business rules and escalated
when required.

## 9. Agent Architecture

```
                    Supervisor Agent
                          |
             +------------+-------------+
             |            |             |
             v            v             v
        Scheduling      Refill       Customer
          Agent          Agent       Service Agent
             |            |             |
             v            v             v
       Scheduling     Pharmacy      Customer APIs
          APIs           APIs
             |
             +------------------------------+
                                            |
                                            v
                                       Email Agent
                                            |
                                            v
                                        Email API
```

Use LangGraph or an equivalent workflow orchestrator to represent state,
conditional routing, retries, human approval, and multi-step operations.

## 10. Tool/API Contract

| Capability | Example Tools | LLM Role | Execution Owner |
|---|---|---|---|
| Customer | `get_customer()`, `get_patient()` | Identify/extract | Customer Service |
| Scheduling | `check_availability()`, `reschedule()` | Select workflow | Scheduling API |
| Refill | `get_prescription()`, `check_eligibility()`, `submit_refill()` | Route/extract | Pharmacy API |
| Email | `send_email()` | Generate wording | Email Service |
| Audit | `record_audit_event()` | Provide context | Audit Service |

## 11. WebSocket Message Model

Client → Server

```json
{
  "type": "user_message",
  "message_id": "msg-1001",
  "conversation_id": "conv-123",
  "message": "Can I move my appointment to Monday?"
}
```

Server → Client

```json
{
  "type": "agent_status",
  "message_id": "msg-1001",
  "status": "checking_availability"
}
```

Server → Client

```json
{
  "type": "appointment_options",
  "options": [
    {"id": "slot-1", "start": "2026-09-14T14:30:00"},
    {"id": "slot-2", "start": "2026-09-14T16:00:00"}
  ]
}
```

Server → Client

```json
{
  "type": "agent_message",
  "message": "I found two available times."
}
```

## 12. Conversation State

Keep transport state and business state separate.

```
WebSocket / Transport State
- connection_id
- server_id
- connected/disconnected
- heartbeat
- last_seen

Conversation / Business State
- conversation_id
- customer_id
- messages
- current workflow
- workflow status
- tool results
- pending approval
- correlation_id

Recommended:
Redis -> short-lived/session/coordination state
PostgreSQL -> durable conversation and business state
```

## 13. Reconnection and Server Failure

```
Normal:
Customer ================= Server 2

Server 2 crashes:
Customer ======== X ====== Server 2

Frontend reconnects:
Customer -> Load Balancer -> Server 3

Redis is updated:
customer-123 -> server-3

Server 3 loads conversation/workflow state
from PostgreSQL/Redis and continues the session.
```

The WebSocket connection is disposable transport state. The conversation and
business workflow must survive connection loss.

## 14. Sticky Sessions

Sticky sessions can simplify connection affinity, but they should not be the
only resilience mechanism. If the owning server fails, the WebSocket is lost and
the client must reconnect. Durable conversation state and idempotent business
operations are therefore essential.

## 15. Idempotency and Duplicate Protection

Reconnects, retries, browser refreshes, and event redelivery can cause duplicate
operations. Use a client `message_id`/`correlation_id` and an idempotency key
for state-changing APIs.

```http
POST /appointments/reschedule
Idempotency-Key: req-abc-123

POST /refills
Idempotency-Key: refill-xyz-789
```

## 16. Security

- Use WSS (TLS) for WebSocket connections.
- Authenticate the WebSocket during connection establishment and authorize every
  sensitive operation.
- Do not trust `customer_id` supplied only by the client; derive identity from
  the authenticated session/token.
- Validate tool arguments server-side before calling business APIs.
- Apply least-privilege service identities.
- Keep secrets out of agent prompts and logs.
- Redact sensitive data from application logs and traces.
- Maintain immutable audit records for medication and appointment actions.
- Add rate limiting, connection limits, message-size limits, and abuse detection.

## 17. Reliability

- Heartbeat/ping-pong to detect dead WebSocket connections.
- Automatic client reconnect with exponential backoff and jitter.
- Persist important messages/events before acknowledging critical operations.
- Use correlation IDs across WebSocket, agent, API, and event-bus logs.
- Use retries only for transient failures and use idempotency keys for
  state-changing operations.
- Use dead-letter handling for failed asynchronous events.
- Use timeouts and circuit breakers for downstream services.

## 18. Observability

```
correlation_id
   |
   +--> WebSocket message
   +--> Agent workflow
   +--> Tool call
   +--> Appointment/Pharmacy API
   +--> Event Bus event
   +--> Email
   |
   v
Distributed tracing / logs / metrics
```

Track connection count, active connections per pod, reconnect rate, message
latency, agent latency, tool latency, workflow failures, event lag, API errors,
and refill/scheduling success rates.

## 19. Kubernetes / Cloud Deployment

```
                 Cloud Load Balancer
                         |
                  Ingress / Gateway
                         |
        +----------------+----------------+
        |                |                |
        v                v                v
   FastAPI Pod 1    FastAPI Pod 2    FastAPI Pod 3
        |                |                |
        +----------------+----------------+
                         |
                       Redis
                         |
                  Kafka / Event Hub
                         |
             +-----------+-----------+
             |                       |
             v                       v
        Agent Workers          Background Workers
             |
             v
        Business APIs
             |
             v
         PostgreSQL
```

Use readiness/liveness probes, horizontal pod autoscaling, graceful shutdown,
connection draining, and appropriate idle/read timeouts for the load
balancer/ingress.

## 20. FastAPI Reference Structure

```
app/
  main.py
  api/
    websocket.py
    health.py
  websocket/
    connection_manager.py
    auth.py
    events.py
  agents/
    graph.py
    supervisor.py
    scheduling_agent.py
    refill_agent.py
    email_agent.py
  tools/
    customer.py
    scheduling.py
    pharmacy.py
    email.py
  messaging/
    redis_pubsub.py
    event_bus.py
  repositories/
    conversation.py
    audit.py
  models/
    messages.py
    conversations.py
```

## 21. Connection Manager Concept

```python
class ConnectionManager:
    def __init__(self):
        self.connections = {}

    async def connect(self, customer_id, websocket):
        await websocket.accept()
        self.connections[customer_id] = websocket

    async def send(self, customer_id, event):
        ws = self.connections.get(customer_id)
        if ws:
            await ws.send_json(event)

    def disconnect(self, customer_id):
        self.connections.pop(customer_id, None)
```

In production, this in-memory map is local to one pod. Redis should hold
distributed metadata, while cross-pod notifications use Redis Pub/Sub or the
event bus. Do not treat Redis as a replacement for the actual WebSocket object.

## 22. Recommended Technology Choices

| Layer | Recommended Choice | Purpose |
|---|---|---|
| Frontend | Next.js / React | Customer chat UI |
| Realtime | WebSocket / WSS | Bidirectional realtime communication |
| API | FastAPI | Chat gateway and service APIs |
| Agent | LangGraph | Stateful agent workflows |
| Agent tools | MCP and/or function/tool calling | Controlled capability access |
| Cache/session | Redis | Connection metadata, short-lived state, coordination |
| Eventing | Kafka / Azure Event Hubs | Async workflows and events |
| Database | PostgreSQL | Durable conversation/audit/business state |
| Observability | OpenTelemetry | Distributed tracing and metrics |
| Deployment | Kubernetes | Horizontal scaling and resilience |

## 23. Renovation Plan for an Existing Project

- Inventory current chat, API, authentication, database, scheduling, pharmacy,
  and email components.
- Introduce a dedicated Chat Gateway/WebSocket endpoint without moving business
  logic into the WebSocket handler.
- Add conversation IDs, message IDs, correlation IDs, and durable conversation
  persistence.
- Introduce a local connection manager and Redis-based distributed connection
  metadata.
- Add an event bus for long-running operations and cross-server notifications.
- Refactor scheduling/refill operations behind deterministic service APIs with
  authorization and idempotency.
- Introduce LangGraph as the orchestration layer and specialized agents only
  where they add value.
- Add reconnect/resume behavior to the frontend.
- Add audit logging, tracing, security controls, and operational metrics.
- Load-test WebSocket concurrency, reconnect storms, server failure, event lag,
  and downstream API failures before production rollout.

## 24. Critical Failure Scenarios

| Scenario | Expected Behavior | Recovery |
|---|---|---|
| Chat pod crashes | WebSocket disconnects | Client reconnects; new pod restores state |
| Agent worker crashes | Workflow may be interrupted | Durable workflow/event state enables retry |
| Redis unavailable | Distributed coordination degraded | Fail safely; reconnect/recover according to HA design |
| Pharmacy API timeout | No false success | Timeout + retry/escalation; do not claim refill completed |
| Duplicate refill request | Potential duplicate operation | Idempotency key prevents duplicate submission |
| Customer disconnects | Transport lost | Workflow can continue if business operation is already submitted |
| Event delivered twice | Duplicate notification possible | Event ID/idempotent consumer prevents duplicate effects |

## 25. Final Mental Model

```
1. Customer opens WebSocket.
2. Load balancer selects Chat Server 2.
3. WebSocket remains connected to Chat Server 2.
4. Customer messages use that existing connection.
5. Chat Server 2 sends the request to Agent/LangGraph.
6. Agent calls deterministic tools/APIs.
7. If the agent runs elsewhere, an event/message is routed back
   to the Chat Server that owns the customer's connection.
8. That Chat Server sends the response over the existing WebSocket.
9. If Chat Server 2 dies, the client reconnects through the load balancer.
10. The new Chat Server restores conversation/workflow state from
    durable storage.

KEY:
WebSocket = realtime customer transport
Load Balancer = connection establishment / proxy
Redis = distributed connection/session metadata
Kafka/Event Hub = asynchronous events
LangGraph = agent orchestration
REST/gRPC/MCP tools = controlled capabilities
PostgreSQL = durable state
```

## 26. Architecture Decision Summary

**Recommended baseline:** Next.js/React + WSS WebSocket + FastAPI Chat Gateway +
Redis + Kafka/Azure Event Hubs + LangGraph + deterministic
scheduling/pharmacy/customer/email APIs + PostgreSQL. Keep WebSocket transport,
agent orchestration, and business operations as separate layers. This design
allows horizontal scaling while preserving real-time chat behavior and recovery
from individual server failures.

---

# Appendix A — Implementation status in this repository

*Not part of the source document.* This records where each section of the
blueprint lives in the City Hospital codebase, and where the implementation
deliberately differs.

## A.1 Where each section is implemented

| § | Concern | Implementation |
|---|---|---|
| 4, 5, 11 | WebSocket transport and message model | [`app/api/ws/chat.py`](../backend/)app/api/ws/chat.py), [`app/realtime/protocol.py`](../backend/)app/realtime/protocol.py) |
| 6 | Multi-server connection management | [`app/realtime/session_registry.py`](../backend/)app/realtime/session_registry.py) (Redis metadata), [`app/realtime/dispatcher.py`](../backend/)app/realtime/dispatcher.py) (Redis Pub/Sub routing) |
| 3, 8 | Agent work off the socket handler | [`app/services/chat.py`](../backend/)app/services/chat.py) publishes; [`app/workers/agent_worker.py`](../backend/)app/workers/agent_worker.py) consumes |
| 9 | Agent orchestration | [`app/services/agent.py`](../backend/)app/services/agent.py) — LangGraph `create_react_agent` |
| 10 | Tool/API contract | [`app/mcp/server.py`](../backend/)app/mcp/server.py) (MCP surface) → [`app/mcp/tools.py`](../backend/)app/mcp/tools.py) → the service layer |
| 12 | Transport vs business state | Transport in Redis (`session_registry`); business in [`app/models/chat.py`](../backend/)app/models/chat.py) + [`app/services/conversation.py`](../backend/)app/services/conversation.py), with a Redis hot cache in [`app/repositories/conversation_cache.py`](../backend/)app/repositories/conversation_cache.py) |
| 13, 14 | Reconnect and server failure | Client reconnect + resume in [`src/lib/api/realtimeClient.ts`](../frontend/)src/lib/api/realtimeClient.ts); transcript replay on `ready` in `ws/chat.py`; registry TTLs expire a dead pod's routing entries |
| 15 | Idempotency | [`app/core/coordination.py`](../backend/)app/core/coordination.py) `IdempotencyGuard`, plus a database-level `message_id` check in [`app/repositories/conversation.py`](../backend/)app/repositories/conversation.py) |
| 16 | Security | Handshake auth + server-minted guest sessions in [`app/realtime/ws_auth.py`](../backend/)app/realtime/ws_auth.py); server-side identity resolution in [`app/realtime/tool_results.py`](../backend/)app/realtime/tool_results.py); redaction in [`app/core/safety.py`](../backend/)app/core/safety.py); role gates in [`app/api/deps.py`](../backend/)app/api/deps.py); rate/size/connection limits in `core/coordination.py` and `ws/chat.py` |
| 17 | Reliability | Server heartbeat in `ws/chat.py`, client watchdog + full-jitter backoff in [`src/lib/backoff.ts`](../frontend/)src/lib/backoff.ts); dead-letter stream in [`app/messaging/redis_event_bus.py`](../backend/)app/messaging/redis_event_bus.py); turns persisted before they are acknowledged |
| 18 | Observability | `correlation_id` on every event ([`app/messaging/events.py`](../backend/)app/messaging/events.py)); per-run audit with model, tokens, cost and latency in [`app/services/ai_gateway.py`](../backend/)app/services/ai_gateway.py) |
| 19 | Deployment | `/health`, `/health/live`, `/health/ready` and connection draining in [`app/main.py`](../backend/)app/main.py) |
| 21 | Connection manager | [`app/realtime/connection_manager.py`](../backend/)app/realtime/connection_manager.py) |
| 24 | Failure scenarios | Covered by [`tests/test_redis_integration.py`](../backend/)tests/test_redis_integration.py) and [`tests/test_chat_gateway.py`](../backend/)tests/test_chat_gateway.py) |

## A.2 Deliberate differences from the blueprint

| Blueprint | This repository | Why |
|---|---|---|
| Kafka / Azure Event Hubs | **Redis Streams** — consumer groups, explicit ack, pending-entry reclaim, dead-letter | Same guarantees the design relies on, one fewer piece of infrastructure. Hidden behind the `EventBus` interface in [`app/messaging/event_bus.py`](../backend/)app/messaging/event_bus.py): a Kafka implementation plus one line in [`app/core/container.py`](../backend/)app/core/container.py) swaps it. |
| PostgreSQL | **SQLite** via SQLModel | It fills the same durable-state role for this deployment. Swapping is a `DATABASE_URL` change plus a real migration tool. |
| Supervisor + specialised sub-agents (§9) | **One LangGraph ReAct agent** with the full tool set | Specialised agents are worth it "only where they add value" (§23). At this tool count the routing overhead exceeds the benefit. |
| Email agent + Email API | **Not implemented** | Out of scope for the clinic application; no email capability exists to wrap. |
| `reschedule()` tool (§7, §10) | **Not implemented** | The agent books and the clinic cancels; there is no single reschedule operation yet. |
| OpenTelemetry | **Structured logging + a database audit trail** | Correlation ids are threaded end to end and are ready for a tracer; no exporter is wired. |
| Kubernetes | **No manifests** | Probes, graceful shutdown and connection draining are implemented; the deployment itself is not in this repository. |
| Reference layout (§20) | Standard FastAPI layout (`api/routes`, `api/ws`, `core`, `services`, `repositories`, `db`, `models`, `schemas`, `realtime`, `messaging`, `workers`) | Same separation of concerns, expressed in the conventional FastAPI structure. See [backend/README.md](../backend/)README.md). |

## A.3 Degraded mode

Redis is required for multi-instance operation but optional for one instance.
Without it the application falls back to an in-process event bus, a local
connection registry and process-local idempotency and rate limits — everything
keeps working on a single node, and `/health` reports `"redis": false`. This is
the design document's "fail safely" row (§24) made explicit.
