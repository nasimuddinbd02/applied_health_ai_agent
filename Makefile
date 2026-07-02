# City Hospital — dev workflow
# Full local stack: `make run-backend` + `make run-mcp` + `make run-frontend`

.PHONY: install seed run-backend run-mcp run-frontend test test-frontend lint

install:
	cd backend && python -m pip install -r requirements.txt
	cd frontend && npm install

seed:
	cd backend && python -m app.seed

run-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

run-mcp:
	cd backend && python -m app.mcp.server

run-frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest -q

test-frontend:
	cd frontend && npm test

lint:
	cd backend && ruff check app tests
