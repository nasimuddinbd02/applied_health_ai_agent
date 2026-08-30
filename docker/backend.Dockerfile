# City Hospital backend — one image, three roles.
#
# The chat gateway, the agent worker and the MCP tool server all run the same
# code from the same container; only the command differs. That is deliberate:
# the worker imports the services and repositories the gateway uses, so
# splitting them into separate images would mean shipping the same layers twice
# and letting them drift.
#
#   gateway  uvicorn app.main:app --host 0.0.0.0 --port 8000   (the default)
#   worker   python -m app.workers.agent_worker
#   mcp      python -m app.mcp.server
#
# Build from the repository root:
#   docker build -f docker/backend.Dockerfile -t cityhospital-backend .

# --------------------------------------------------------------------------- #
# Stage 1 — build the dependency tree into a virtualenv
# --------------------------------------------------------------------------- #
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Build-only toolchain. Nothing here reaches the runtime image.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copied on its own so the (slow) dependency layer is cached until this file
# actually changes — application edits rebuild in seconds.
COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# --------------------------------------------------------------------------- #
# Stage 2 — runtime
# --------------------------------------------------------------------------- #
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# curl is here for the container-level HEALTHCHECK below. Kubernetes uses its
# own HTTP probes and does not need it.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --gid 10001 app \
 && useradd --uid 10001 --gid app --create-home app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app backend/app ./app
COPY --chown=app:app backend/pyproject.toml ./

# Only used when DATABASE_URL points at a SQLite file. Declared so a plain
# `docker run` has somewhere writable; in Kubernetes this is a PostgreSQL
# deployment and the directory stays empty.
RUN mkdir -p /app/database && chown app:app /app/database
VOLUME ["/app/database"]

USER app
EXPOSE 8000

# Deliberately the liveness endpoint, not /health: /health/live has no
# dependencies, so a Redis blip cannot get a container killed while it is
# holding live WebSocket connections.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health/live || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
