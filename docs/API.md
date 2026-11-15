# Implemented API — Phase 1

| Route | Result |
| --- | --- |
| GET `/health` | 200 `{"status":"ok","checks":{}}`; no dependency access |
| GET `/health/live` | Liveness alias for blueprint compatibility |
| GET `/health/ready` | 200 `{"status":"ready","checks":{"postgresql":"up","redis":"up"}}`; 503 `not_ready` if either dependency fails, with up/down checks |
| GET `/docs`, `/openapi.json` | FastAPI-generated API documentation |

Frontend calls `/api/health/ready`; Nginx/Vite strip `/api` before forwarding. Health endpoints remain unversioned. No business routes exist. Dependency errors are sanitized. SQL checks live in core/database.py; readiness orchestration lives in core/health.py and is dependency-injected. Phase 1 requires both dependencies and does not check a schema version. Later Redis-degraded readiness and business error contracts remain planned in ARCHITECTURE.md.
