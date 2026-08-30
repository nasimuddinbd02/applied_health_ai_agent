# Deployment — Docker and Azure Kubernetes Service

Three ways to run the stack, sharing one set of images:

| Target | Command | Database / Redis |
|---|---|---|
| Local processes | `./scripts/dev.sh` | SQLite + local Redis |
| Docker Compose | `docker compose up --build` | Containers |
| AKS | `./deploy/azure/deploy.sh` | Azure managed services |

Compose and Kubernetes both run the **split topology** — the gateway holds
sockets, a separate worker runs the agent — so what you exercise locally is the
shape that ships.

## What had to change to make this deployable

Four things, all in the code rather than the manifests:

| Change | Why |
|---|---|
| `Database` is dialect-aware ([db/session.py](../backend/app/db/session.py)) | SQLite's `check_same_thread` is invalid on PostgreSQL, and the additive `migrate()` reads `sqlite_master`, so it is now skipped off SQLite |
| Row locks on the booking and dispensing transactions | On SQLite, writes serialise and the read-then-write was safe. Under PostgreSQL READ COMMITTED, two pods could both read `is_booked=False` and both insert. `with_for_update` closes it; SQLite ignores `FOR UPDATE`, so nothing changes locally |
| `python -m app.db.session` | Creates the schema without touching data. `python -m app.db.seed` **deletes every row** first, so it must never be the container's start-up step |
| `AppConfig` splits browser and server API bases ([lib/config.ts](../frontend/src/lib/config.ts)) | `NEXT_PUBLIC_*` is inlined at build time; baking a hostname in would make the image environment-specific. Empty means "same origin", and `INTERNAL_API_BASE` is read at runtime for Server Components |

**SQLite is not an option once more than one pod writes.** It is a file, and a
file on a shared volume does not give you cross-node locking. Compose and the
Kubernetes manifests both use PostgreSQL.

## Docker

One backend image runs all three backend roles — the gateway, the worker and
the MCP tool server import the same services, so splitting them would ship the
same layers twice and let them drift.

```bash
docker build -f docker/backend.Dockerfile  -t cityhospital-backend .
docker build -f docker/frontend.Dockerfile -t cityhospital-web .
```

Both are multi-stage: the backend builds its virtualenv with a compiler
toolchain that never reaches the runtime layer, and the frontend uses Next's
`output: "standalone"` so only the imported `node_modules` ship. Both run as
UID 10001, non-root, with a read-only root filesystem in Kubernetes.

### Compose

```bash
cp .env.example .env          # optional: OPENAI_API_KEY, JWT_SECRET, POSTGRES_PASSWORD
docker compose up --build
docker compose --profile seed run --rm seed   # demo data — WIPES the database
open http://localhost:3000
```

`migrate` creates the schema on every start (safe, idempotent). Seeding is
behind a profile precisely because it is destructive.

## Kubernetes

```
deploy/k8s/
  base/                 gateway · agent-worker · mcp · web · ingress · HPA · PDB · schema Job
  overlays/local/       adds in-cluster Redis + PostgreSQL, 1 replica each  (kind/minikube)
  overlays/aks/         ACR images, AKS ingress class, workload identity     (Azure)
```

```bash
kubectl apply -k deploy/k8s/overlays/local   # self-contained, no Azure
kubectl apply -k deploy/k8s/overlays/aks     # after the Azure steps below
```

### The decisions worth knowing

**`SERVER_ID` is the pod name**, via `fieldRef: metadata.name`. Redis maps each
conversation to its owning instance using that id, so a static value would send
replies to the wrong pod.

**No session affinity on the ingress.** Redis already knows which pod holds
each socket, so sticky sessions would only mask bugs in that routing
([Design.md §14](Design.md)). The annotation is deliberately absent and there
is a comment saying so.

**Ingress timeouts are the WebSocket-critical setting.** A default ingress
closes an idle upstream after ~60s, which would kill every socket waiting for
the customer to type. `proxy-read-timeout` and `proxy-send-timeout` are set to
3600; the app's own 25s heartbeat keeps healthy connections far inside it.
ingress-nginx handles the `Upgrade` handshake itself — there is nothing to
configure for that part.

**Liveness is `/health/live`, not `/health`.** The liveness endpoint touches no
dependencies on purpose: a Redis blip must not get pods killed while they are
holding live connections. Readiness uses `/health/ready`, which does check
Redis, so a struggling pod stops receiving *new* connections without losing the
ones it has.

**Draining takes three cooperating parts.** `preStop: sleep 15` lets the
ingress stop routing new connections first; then the app's lifespan calls
`ConnectionManager.drain()` to close each socket with 1001 Going Away; and
`terminationGracePeriodSeconds: 60` is long enough for both. Clients then
reconnect with jittered backoff onto a healthy pod and replay their transcript.

**`maxUnavailable: 0`** on the gateway and web rollouts: never drop below
current capacity while replacing pods.

**The schema Job is not the seed.** `db-schema` runs `python -m app.db.session`.
Nothing in the deploy path runs `app.db.seed`.

### Autoscaling is on CPU, and that is a compromise

A gateway pod is nearly idle while holding thousands of sockets, so CPU is a
poor proxy. The honest signals are `active_connections` from `/health` for the
gateway and stream depth (`XLEN` on `events:chat.user_message`) for the worker.
Both want KEDA or the Prometheus adapter. Until then the HPAs use CPU with a
floor of 2 replicas and a slow (300s) scale-down, because scaling in drops
sockets.

## AKS, end to end

### 1. Infrastructure

```bash
az group create -n cityhospital-rg -l westeurope
az deployment group create -g cityhospital-rg \
  -f deploy/azure/main.bicep \
  -p namePrefix=cityhosp postgresAdminPassword='<strong-password>'
```

[`main.bicep`](../deploy/azure/main.bicep) creates ACR, AKS (OIDC issuer +
workload identity + the managed ingress-nginx add-on + Key Vault CSI driver),
Azure Cache for Redis, PostgreSQL Flexible Server, Key Vault, Log Analytics,
and a user-assigned managed identity federated to the
`cityhospital:cityhospital` service account. It also grants `AcrPull` to the
kubelet identity — the omission that otherwise shows up as an unexplained
`ImagePullBackOff`.

Two choices in there are deliberate:

- **Redis `maxmemory-policy: noeviction`.** The stream and the idempotency keys
  are correctness state, not a cache. Silently evicting them would double-book.
- **Redis Standard, not Basic.** Basic has no SLA and no replica, and losing
  Redis costs every guest their resolved identity.

### 2. Secrets

The manifests never contain credentials, and `deploy.sh` refuses to run without
the Secret. Create it from the Bicep outputs:

```bash
RG=cityhospital-rg
PG=$(az deployment group show -g $RG -n main --query properties.outputs.postgresFqdn.value -o tsv)
REDIS=$(az deployment group show -g $RG -n main --query properties.outputs.redisHostName.value -o tsv)
REDIS_KEY=$(az redis list-keys -g $RG -n "${REDIS%%.*}" --query primaryKey -o tsv)

kubectl create namespace cityhospital
kubectl -n cityhospital create secret generic backend-secrets \
  --from-literal=DATABASE_URL="postgresql+psycopg://cityhospital:<password>@$PG:5432/cityhospital?sslmode=require" \
  --from-literal=REDIS_URL="rediss://:$REDIS_KEY@$REDIS:6380/0" \
  --from-literal=JWT_SECRET="$(openssl rand -hex 32)" \
  --from-literal=OPENAI_API_KEY='sk-...'
```

Note `rediss://` on port **6380** — the template disables the non-TLS port.

For anything beyond a starter environment, use the Key Vault CSI driver (the
add-on is already enabled) so secrets are projected from Key Vault instead of
living in etcd. The workload identity already has `Key Vault Secrets User`.

Rotating `JWT_SECRET` logs every user out and invalidates in-flight guest chat
sessions.

### 3. Deploy

```bash
./deploy/azure/deploy.sh -g cityhospital-rg -p cityhosp -t 0.1.0 -H clinic.example.com
```

It builds both images with `az acr build` (no local Docker daemon needed),
points the overlay at the new tag, stamps the managed-identity client id into
the service account, applies the manifests, waits for the schema Job, and waits
for each rollout.

### 4. Verify

```bash
kubectl -n cityhospital get pods
kubectl -n cityhospital exec deploy/gateway -- \
  python -c "import urllib.request,json;print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/health')))"
```

Expect `"redis": true` and `"event_bus": "RedisStreamEventBus"`. If you see
`"redis": false` the app has silently degraded to single-instance mode — it
will still serve, but replies will not reach sockets on other pods.

Then check the routing actually works across pods: open the chat in a browser,
watch which gateway accepted it, and confirm the reply arrives even though the
worker ran elsewhere.

```bash
kubectl -n cityhospital logs -l app.kubernetes.io/component=gateway --tail=50
kubectl -n cityhospital logs -l app.kubernetes.io/component=agent-worker --tail=50
```

## Known limitations

| Limitation | Detail |
|---|---|
| **Untested against a live cluster** | Every manifest renders through kustomize and validates against the Kubernetes 1.29 schemas, and the Bicep compiles — but nothing here has been applied to a real cluster or built into an image. Treat the first deploy as a smoke test. |
| **No schema migrations beyond `create_all`** | The additive migrator is SQLite-only. On PostgreSQL, `create_all` covers a fresh database; anything after that needs Alembic. |
| **PostgreSQL is public-with-firewall** | The Bicep allows Azure services. Production wants VNet integration and a private endpoint. |
| **PostgreSQL has no HA** | The Burstable tier cannot do it. Move to GeneralPurpose with `ZoneRedundant` before real patient data. |
| **Autoscaling signal** | CPU, not connections or queue depth — see above. |
| **No OpenTelemetry exporter** | Correlation ids are threaded end to end and ready for a tracer; only Log Analytics via the AKS add-on is wired. |
| **`/docs` and `/health` are not routed publicly** | Deliberate. They are reachable in-cluster for probes and debugging. |

## Related

- [Design.md §19](Design.md) — the deployment section of the blueprint
- [Processes.md](Processes.md) — what each service actually does
- [../README.md](../README.md) — running it locally
