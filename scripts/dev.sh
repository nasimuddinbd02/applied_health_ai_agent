#!/usr/bin/env bash
#
# Run the whole City Hospital stack in one shot.
#
# Starts Redis, the FastMCP tool server, the FastAPI chat gateway and the
# Next.js frontend, prefixes their output into this one terminal, and shuts all
# of them down together on Ctrl+C.
#
# Usage:
#   ./scripts/dev.sh                    everything on the default ports
#   ./scripts/dev.sh --separate-worker  agent worker as its own process
#   ./scripts/dev.sh --no-frontend      backend only
#   BACKEND_PORT=8001 ./scripts/dev.sh  override a port
#
# The Windows-native equivalent is scripts/dev.ps1.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
LOG_DIR="$ROOT/.dev-logs"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
MCP_PORT="${MCP_PORT:-8077}"
REDIS_PORT="${REDIS_PORT:-6379}"

START_REDIS=1
START_MCP=1
START_FRONTEND=1
SEPARATE_WORKER=0
FORCE_SEED=0

while [ $# -gt 0 ]; do
  case "$1" in
    --no-redis)         START_REDIS=0 ;;
    --no-mcp)           START_MCP=0 ;;
    --no-frontend)      START_FRONTEND=0 ;;
    --separate-worker)  SEPARATE_WORKER=1 ;;
    --seed)             FORCE_SEED=1 ;;
    -h|--help)          sed -n '3,17p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
step() { printf '\033[36m==> %s\033[0m\n' "$1"; }
warn() { printf '\033[33m  ! %s\033[0m\n' "$1"; }

port_open() {
  # No netcat guarantee across Git Bash / macOS / Linux, so ask the language
  # every one of these boxes already has.
  "$PYTHON" - "$1" <<'PY' 2>/dev/null
import socket, sys
s = socket.socket(); s.settimeout(0.3)
try:
    s.connect(("127.0.0.1", int(sys.argv[1])))
except Exception:
    sys.exit(1)
finally:
    s.close()
PY
}

resolve_python() {
  for candidate in "$ROOT/.venv/Scripts/python.exe" "$ROOT/.venv/bin/python" \
                   "$BACKEND/.venv/Scripts/python.exe" "$BACKEND/.venv/bin/python"; do
    if [ -x "$candidate" ]; then echo "$candidate"; return; fi
  done
  if command -v python3 >/dev/null 2>&1; then command -v python3; return; fi
  if command -v python  >/dev/null 2>&1; then command -v python;  return; fi
  echo "No Python found. Create a virtualenv at .venv and run 'make install'." >&2
  exit 1
}

resolve_redis() {
  if command -v redis-server >/dev/null 2>&1; then command -v redis-server; return; fi
  # Windows distributions do not put themselves on PATH.
  for base in "${LOCALAPPDATA:-}/Programs/Redis" "/c/Program Files/Redis"; do
    [ -d "$base" ] || continue
    found="$(find "$base" -name 'redis-server.exe' -print -quit 2>/dev/null || true)"
    if [ -n "$found" ]; then echo "$found"; return; fi
  done
  echo ""
}

PIDS=()
NAMES=()

start_service() {
  local name="$1" color="$2" dir="$3"; shift 3
  local log="$LOG_DIR/$name.log"
  ( cd "$dir" && "$@" >"$log" 2>&1 ) &
  local pid=$!
  PIDS+=("$pid")
  NAMES+=("$name")
  # Tail the log into this terminal with a coloured prefix. -u keeps sed from
  # buffering, otherwise nothing appears until the buffer fills.
  ( tail -n +1 -f "$log" 2>/dev/null | sed -u "s/^/$(printf '\033[%sm[%s]\033[0m ' "$color" "$name")/" ) &
  PIDS+=("$!")
  NAMES+=("$name-tail")
}

wait_for_port() {
  local port="$1" what="$2" timeout="${3:-60}" waited=0
  while [ "$waited" -lt "$timeout" ]; do
    if port_open "$port"; then return 0; fi
    sleep 1
    waited=$((waited + 1))
  done
  warn "$what did not come up on port $port within ${timeout}s."
  return 0
}

cleanup() {
  echo
  step 'Shutting down...'
  # Kill the whole process group so npm's and uvicorn's children go too.
  for pid in "${PIDS[@]:-}"; do
    kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  printf '\033[36mStopped.\033[0m\n'
}
trap cleanup EXIT INT TERM

# --------------------------------------------------------------------------- #
# Preflight
# --------------------------------------------------------------------------- #
step 'Checking the workspace'
PYTHON="$(resolve_python)"
echo "    python:   $PYTHON"

mkdir -p "$LOG_DIR"
rm -f "$LOG_DIR"/*.log

if [ ! -f "$BACKEND/.env" ]; then
  cp "$ROOT/.env.example" "$BACKEND/.env"
  warn 'Created backend/.env from .env.example. Add a provider API key to use the live agent.'
fi

if [ "$START_FRONTEND" -eq 1 ] && [ ! -d "$FRONTEND/node_modules" ]; then
  step 'Installing frontend dependencies (first run, this takes a minute)'
  ( cd "$FRONTEND" && npm install )
fi

if [ "$FORCE_SEED" -eq 1 ] || [ ! -f "$BACKEND/database/hospital.db" ]; then
  step 'Seeding the database'
  ( cd "$BACKEND" && "$PYTHON" -m app.db.seed )
fi

# --------------------------------------------------------------------------- #
# Start everything
# --------------------------------------------------------------------------- #
# Both the tool server and the agent that calls it read these, so exporting
# once here is what keeps the two ends pointed at the same place.
export MCP_PORT
export MCP_URL=""

if [ "$START_REDIS" -eq 1 ]; then
  if port_open "$REDIS_PORT"; then
    step "Redis already listening on $REDIS_PORT - leaving it alone"
  else
    REDIS_BIN="$(resolve_redis)"
    if [ -n "$REDIS_BIN" ]; then
      step "Starting Redis on $REDIS_PORT"
      start_service redis '90' "$ROOT" "$REDIS_BIN" --port "$REDIS_PORT"
      wait_for_port "$REDIS_PORT" 'Redis' 20
    else
      warn 'Redis not found. The app will run single-instance with in-process fallbacks.'
    fi
  fi
fi

if [ "$START_MCP" -eq 1 ]; then
  if port_open "$MCP_PORT"; then
    step "MCP already listening on $MCP_PORT - leaving it alone"
  else
    step "Starting the MCP tool server on $MCP_PORT"
    start_service mcp '35' "$BACKEND" "$PYTHON" -m app.mcp.server
    wait_for_port "$MCP_PORT" 'The MCP server' 40
  fi
fi

step "Starting the API + chat gateway on $BACKEND_PORT"
if [ "$SEPARATE_WORKER" -eq 1 ]; then
  export INLINE_AGENT_WORKER=false
else
  export INLINE_AGENT_WORKER=true
fi
SERVER_ID=gateway-1 start_service backend '32' "$BACKEND" \
  "$PYTHON" -m uvicorn app.main:app --reload --port "$BACKEND_PORT"
wait_for_port "$BACKEND_PORT" 'The backend' 60

if [ "$SEPARATE_WORKER" -eq 1 ]; then
  step 'Starting the agent worker as its own process'
  SERVER_ID=worker-1 start_service worker '33' "$BACKEND" \
    "$PYTHON" -m app.workers.agent_worker
fi

if [ "$START_FRONTEND" -eq 1 ]; then
  step "Starting the frontend on $FRONTEND_PORT"
  # A real environment variable beats .env.local in Next, so the two halves
  # agree even when .env.local names a different port.
  export NEXT_PUBLIC_API_BASE="http://localhost:$BACKEND_PORT"
  export NEXT_PUBLIC_WS_BASE="ws://localhost:$BACKEND_PORT"
  start_service frontend '34' "$FRONTEND" npm run dev -- --port "$FRONTEND_PORT"
fi

echo
printf '\033[32m  City Hospital is up\033[0m\n'
[ "$START_FRONTEND" -eq 1 ] && echo "    web       http://localhost:$FRONTEND_PORT"
echo "    api       http://localhost:$BACKEND_PORT/docs"
echo "    health    http://localhost:$BACKEND_PORT/health"
echo "    chat ws   ws://localhost:$BACKEND_PORT/ws/chat"
echo "    logs      .dev-logs/"
echo
printf '\033[90m  Ctrl+C stops everything.\033[0m\n'
echo

wait
