# CineMatch

CineMatch is a movie discovery graduation project focused on backend engineering and reliable event processing. Phase 1 provides the monorepo foundation: a React health page, FastAPI, PostgreSQL, Redis, Alembic scaffolding and tests. Business modules and workers are not implemented.

## Layout

```text
cinematch/                 # Repository root; no additional nested cinematch directory
  frontend/               # React, TypeScript, Vite, Tailwind, Router, Axios, Query, Zustand
  backend/                # FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Redis, Pytest
  infrastructure/         # Infrastructure notes
  docs/                   # Blueprint and implementation documentation
  scripts/                # Smoke checks
  docker-compose.yml
  .env.example
```

## Docker setup

Requirements: running Docker Desktop/Engine with Compose v2+, free ports 5173, 8000, 5432 and 6379. This Windows development machine uses PostgreSQL port **55432** in its ignored `.env` because Windows blocked 5432.

```powershell
Copy-Item .env.example .env  # First setup only; preserve an existing .env
# Edit .env: replace POSTGRES_PASSWORD with a unique local password.
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
./scripts/smoke.ps1
```

Open [frontend health](http://localhost:5173/health), [backend health](http://localhost:8000/health), [readiness](http://localhost:8000/health/ready), or [OpenAPI](http://localhost:8000/docs). Nginx forwards `/api/health/ready` to the backend, keeping browser calls same-origin. Nginx is an ancillary static server/proxy, not another application framework.

Stop with `docker compose down`; named volumes retain data. Changing POSTGRES_PASSWORD after database initialization does not change the existing database role password; rotate it explicitly. Never commit `.env`. The example contains placeholders only. Initial verification generated a random local password without printing it.

## Local development

Use Python 3.10+ (Docker uses 3.12), Node 22.12+ or Node 24 LTS, and npm. Settings load the root `.env` regardless of working directory; environment variables take precedence. Stop Compose app containers first if sharing ports: `docker compose stop backend frontend`.

```powershell
docker compose up -d postgres redis --wait
cd backend
python -m venv .venv
./.venv/Scripts/python -m pip install --upgrade pip
./.venv/Scripts/python -m pip install -r requirements.lock
./.venv/Scripts/python -m pip install --no-deps -e .
./.venv/Scripts/python -m uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

On POSIX use `.venv/bin/python`. Vite forwards `/api/*` to API_PROXY_TARGET from the root `.env`. Never put credentials in browser configuration or VITE_* variables.

## Verification

From `backend/`:

```powershell
./.venv/Scripts/python -m pytest -q
$env:RUN_INTEGRATION='1'
./.venv/Scripts/python -m pytest -q
Remove-Item Env:RUN_INTEGRATION
./.venv/Scripts/python -m alembic history
```

The default test run isolates health/failure tests and skips the real-services test. The integration flag uses configured PostgreSQL/Redis and exercises SQL SELECT 1 and Redis PING through readiness.

From `frontend/`, with the full stack running:

```powershell
npm ci
npm run build
npx playwright install chromium
npm run test:e2e
```

From repository root, `./scripts/smoke.ps1` checks liveness, dependency readiness, SPA entry and the frontend proxy. See [actual results](docs/DEVELOPMENT_PROGRESS.md).

## Contracts and limitations

GET `/health` (alias `/health/live`) is dependency-independent liveness. GET `/health/ready` returns 200 only when PostgreSQL and Redis respond; otherwise it returns 503 with safe per-dependency statuses. Phase 1 uses strict readiness. No application schema exists; Alembic is initialized without revisions. Future schema changes require migrations; startup never calls create_all.

The local stack has no TLS, authentication, Redis password, workers or production monitoring. Ports bind to loopback and the backend runs as non-root. Python dependencies are pinned in requirements.lock (including test tools for foundation verification); npm uses package-lock.json. Base images use version tags rather than immutable digest pins. TestClient emits an upstream httpx deprecation warning; tests remain functional.

Blueprint: [overview](docs/PROJECT_OVERVIEW.md), [requirements](docs/REQUIREMENTS.md), [architecture](docs/ARCHITECTURE.md), [user flows](docs/USER_FLOWS.md), [decisions](docs/DECISIONS.md). Implementation: [API](docs/API.md), [database](docs/DATABASE.md), [deployment](docs/DEPLOYMENT.md), [events](docs/EVENT_FLOW.md), [recommendations](docs/RECOMMENDATION.md).
