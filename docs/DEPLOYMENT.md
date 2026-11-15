# Local deployment — Phase 1

README.md contains setup and test commands. Compose runs PostgreSQL 17, Redis 7.4, Python 3.12 backend and a multi-stage Node 24 to Nginx frontend build. Health-gated dependencies start database/cache before backend, then frontend. Database/cache use named volumes; Redis enables AOF and no-eviction. Backend clients initialize during lifespan and close at shutdown.

Root `.env` supplies host configuration. Compose explicitly overrides database hostname/port and Redis URL to internal service addresses. Changing POSTGRES_PORT affects only the published host port. The initial Windows host blocked 5432; its local `.env` uses 55432. Set a different free port if needed. Backend/frontend ports are configurable; Redis uses loopback port 6379.

This is local-only: no TLS, authenticated Redis, HA, backup drills, metrics or workers. Ports bind to loopback. Use `docker compose logs backend frontend` for diagnostics and `docker compose ps` for health. Avoid publishing resolved `docker compose config` output containing secrets; validate with `--quiet`.

Restart policies restart stopped processes, not containers solely marked unhealthy. Dependency outages appear in readiness while liveness remains independent. Do not use `docker compose down -v` unless intentionally destroying data. Future operational policies remain in ARCHITECTURE.md.
