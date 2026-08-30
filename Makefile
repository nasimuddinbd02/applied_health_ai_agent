# City Hospital — dev workflow
#
# `make dev` runs the whole stack in one terminal. The individual run-* targets
# below are for when you want a service on its own.
#
# The API process runs the agent worker inline by default, which is what you
# want locally. To rehearse the production topology (chat gateway and agent
# workers as separate deployments), set INLINE_AGENT_WORKER=false and start
# `make run-worker` alongside; you can then run several gateways on different
# ports and watch Redis route replies between them.

.PHONY: install seed dev run-redis run-backend run-mcp run-worker run-frontend \n        test test-frontend test-redis lint \n        docker-build compose-up compose-down k8s-render k8s-local

install:
	cd backend && python -m pip install -r requirements.txt
	cd frontend && npm install

seed:
	cd backend && python -m app.db.seed

# Redis + MCP + API + frontend in one terminal; Ctrl+C stops all of them.
# On Windows, `powershell -File scripts/dev.ps1` is the native equivalent.
dev:
	bash scripts/dev.sh

run-redis:
	redis-server --port 6379

run-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

run-worker:
	cd backend && python -m app.workers.agent_worker

run-mcp:
	cd backend && python -m app.mcp.server

run-frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest -q

# The distributed paths, against a real Redis (skipped if none is listening).
test-redis:
	cd backend && pytest -q tests/test_redis_integration.py

test-frontend:
	cd frontend && npm test

lint:
	cd backend && ruff check app tests

# --------------------------------------------------------------------------- #
# Containers and Kubernetes — see docs/deployment.md
# --------------------------------------------------------------------------- #
docker-build:
	docker build -f docker/backend.Dockerfile  -t cityhospital-backend .
	docker build -f docker/frontend.Dockerfile -t cityhospital-web .

# The full stack in the production topology (split gateway/worker, PostgreSQL).
compose-up:
	docker compose up --build

compose-down:
	docker compose down

# Render the manifests without applying them — the fastest way to review a change.
k8s-render:
	kustomize build deploy/k8s/overlays/aks

# Self-contained cluster deploy: in-cluster Redis + PostgreSQL, 1 replica each.
k8s-local:
	kubectl apply -k deploy/k8s/overlays/local
