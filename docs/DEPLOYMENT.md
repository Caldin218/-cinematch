# Local deployment — Phase 1

Phase 2 schema update: after building the backend and starting PostgreSQL, run `docker compose exec backend python -m alembic upgrade head` once as an operator. Verify with `docker compose exec backend python -m alembic current` and `docker compose exec backend python -m alembic check`. Application startup never migrates automatically; readiness still checks connectivity only. The initial revision creates twelve tables and must be applied before future schema-dependent services. Back up retained data before schema changes. Downgrade base is destructive and intended only for disposable test databases in this phase.

README.md contains setup and test commands. Compose runs PostgreSQL 17, Redis 7.4, Python 3.12 backend and a multi-stage Node 24 to Nginx frontend build. Health-gated dependencies start database/cache before backend, then frontend. Database/cache use named volumes; Redis enables AOF and no-eviction. Backend clients initialize during lifespan and close at shutdown.

Root `.env` supplies host configuration. Compose explicitly overrides database hostname/port and Redis URL to internal service addresses. Changing POSTGRES_PORT affects only the published host port. The initial Windows host blocked 5432; its local `.env` uses 55432. Set a different free port if needed. Backend/frontend ports are configurable; Redis uses loopback port 6379.

This is local-only: no TLS, authenticated Redis, HA, backup drills, metrics or workers. Ports bind to loopback. Use `docker compose logs backend frontend` for diagnostics and `docker compose ps` for health. Avoid publishing resolved `docker compose config` output containing secrets; validate with `--quiet`.

Restart policies restart stopped processes, not containers solely marked unhealthy. Dependency outages appear in readiness while liveness remains independent. Do not use `docker compose down -v` unless intentionally destroying data. Future operational policies remain in ARCHITECTURE.md.
