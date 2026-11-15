CINEMATCH DEVELOPMENT PROGRESS

Project Status



Phase Checklist

Phase 0: Product Definition

Phase 1: Project Foundation

Phase 2: Database Design

Phase 3: Backend Core

Phase 4: Authentication

Phase 5: Movie Catalog

Phase 6: User Interactions

Phase 7: Event-Driven Architecture

Phase 8: Reliable Workers

Phase 9: Recommendation Engine

Phase 10: Recommendation Integration

Phase 11: Frontend Foundation

Phase 12: User Portal Core

Phase 13: User Personalization

Phase 14: Admin Portal

Phase 15: Monitoring

Phase 16: External Movie Data

Phase 17: Comprehensive Testing

Phase 18: Performance Optimization

Phase 19: Production Deployment

Phase 20: Final Audit

Current Implementation



Record completed modules and features.



Known Issues



Record unresolved defects.



Technical Decisions



Record important architectural decisions.



Test Status



Record actual test results.



Last Updated



Record the last update date.



Next Action



Describe the next exact implementation task.



IMPORTANT:



Only mark a phase complete after acceptance.

Never mark tests as passing without running them.

Never delete historical technical decisions.

Keep this document synchronized with actual repository state.



## Phase 1 quality audit — 2026-11-15



Status: core foundation checks pass; quality approval remains open. See [full audit report](PHASE_1_AUDIT.md). The existing phase checklist template above is preserved.



- [x] Reviewed Phase 1 source, tests, configuration and implementation documentation.

- [x] Default backend tests: 7 passed, 1 integration test skipped.

- [x] Container suite with real PostgreSQL/Redis: 8 passed.

- [x] Frontend production build and configured TypeScript check passed.

- [x] Playwright suite: 2 passed; HTTP smoke and all four container health checks passed.

- [x] npm advisory scan: 0 known vulnerabilities; Python/container advisory scans not run.

- [x] Confirmed blank page on unexpected HTTP 503 and stale success after failed refresh through browser probes.

- [x] Confirmed superuser runtime database role and partial structured logging.

- [ ] H-01 corrected and regression-tested.

- [ ] M-01 through M-06 resolved or explicitly dispositioned with verification.

- [ ] Lint and backend static type gates configured and passing; currently unavailable.

- [ ] Quality approval after remediation and targeted re-review.



No application code, dependencies or business features changed in this audit. Report contains severity, locations, evidence, exact executed check commands, passing/failing criteria and remaining untested risks. Core functionality is verified; unconditional phase completion is not granted by this review.



## Phase 2 — database design and implementation — 2026-11-15



Status: schema deliverables implemented and verified; awaiting phase acceptance. No business APIs or workers were added. Phase 1 audit findings remain open and are not marked resolved by this phase.



### Acceptance checklist



- [x] All twelve required tables implemented: users, movies, genres, movie_genres, ratings, movie_views, user_favorites, watchlists, outbox_events, processed_events, recommendations and refresh_tokens.

- [x] UUID user IDs, BIGINT movie IDs, compatible FKs and TIMESTAMPTZ verified against PostgreSQL.

- [x] Named PK/unique/check/FK constraints and query-driven indexes defined; JSONB restricted to object event payloads.

- [x] Ratings update in place, retry-safe view/receipt uniqueness and transactional recommendation replacement verified.

- [x] Initial Alembic migration generated/reviewed and tested from empty databases; no create_all or automatic startup migrations.

- [x] Upgrade/no-op upgrade/check/downgrade/re-upgrade verified in disposable databases only.

- [x] Development database confirmed empty, migrated to 0001_initial_schema, and verified with alembic current/check.

- [x] Independent live inventory: 12 application tables, 37 application indexes (21 explicit +12 PK +4 UNIQUE), 14 foreign keys and 30 CHECK constraints. Alembic bookkeeping excluded.

- [x] Model/schema comparison, index validity/predicates/operator class, constraint rejection, cascade/restrict behavior, timezone roundtrip, rollback and ORM persistence tests pass.

- [x] Windows/Python 3.10 and rebuilt Linux/Python 3.12 backend tests pass; disposable test databases cleaned up.

- [x] DATABASE.md/ERD, README, architecture amendments, decisions and related implementation docs updated.

- [ ] User accepts the Phase 2 deliverables.



### Files and decisions



Created backend/app/models/{__init__,common,users,catalog,interactions,events,recommendations,auth}.py, initial migration 0001_initial_schema_initial_cinematch_schema.py, and tests/test_database_schema.py plus test_model_registry.py. Modified core/database.py only to add stable metadata naming; registered models and injectable test connections in alembic/env.py; added Alembic path_separator configuration. No API/router/frontend/dependency changes.



Updated docs/DATABASE.md with field contracts, Mermaid ERD, all index purposes, cascade rules, transaction protocols and limitations. Updated README and docs/ARCHITECTURE.md, DECISIONS.md, DEPLOYMENT.md, EVENT_FLOW.md, RECOMMENDATION.md and this progress record. Phase 2's explicit required entity names and ID types override the earlier Phase 0 physical-table sketch. Current recommendations use per-user transactional replacement, not historical run tables.



### Commands and actual evidence



Commands below run from backend/ unless otherwise indicated. Fresh tests use the existing configured PostgreSQL cluster; schema fixtures create their own databases and require CREATEDB. They never migrate, truncate or drop the configured development database.



| Command/operation | Actual result |

| --- | --- |

| Repository/docs/model/Alembic inspection | Phase 1 had no models or schema revision; original blueprint conflicts identified and documented. |

| Docker health inspection | Initial sandbox Docker permission denial; authorized elevated retry succeeded with all four services healthy. |

| Python Alembic command.revision(..., autogenerate=True, rev_id='0001_initial_schema') against an isolated empty database | Generated migration, but reported SyntaxError because partial-index ORM boolean predicates rendered as object reprs. Corrected predicates to explicit SQL text in models and migration; reviewed all generated operations. The failed generation's temporary database was cleaned up. |

| `.venv/Scripts/python -m alembic history` | Pass: base → 0001_initial_schema (head). |

| `.venv/Scripts/python -m compileall -q app alembic tests` | Pass. |

| First `$env:RUN_INTEGRATION='1'; .venv/Scripts/python -m pytest -q` | 58 passed; upstream TestClient warning and Alembic legacy path-separator warnings. Added receipt/effect rollback test and corrected path_separator configuration. |

| Final `$env:RUN_INTEGRATION='1'; .venv/Scripts/python -m pytest -q` | **59 passed**, 1 upstream TestClient/httpx deprecation warning. |

| `.venv/Scripts/python -m pytest -q` without integration flag | **8 passed, 51 skipped**, 1 warning; real-service checks intentionally gated. |

| Read-only development schema inspection | Confirmed configured application database had no tables before migration. |

| `.venv/Scripts/python -m alembic upgrade head` | Pass against the confirmed-empty configured development database. |

| `.venv/Scripts/python -m alembic current` | 0001_initial_schema (head). |

| `.venv/Scripts/python -m alembic check` | Pass: No new upgrade operations detected. Tests also compare server defaults and independently inventory constraints/indexes. |

| Read-only schema/cleanup inventory | 12 tables, 37 indexes, 14 FKs, 30 checks; 0 remaining cinematch_schema_* databases after host tests. |

| `docker compose --progress plain build backend` (root) | Pass; new models/migration included in backend wheel/image. |

| `docker compose run --rm --no-deps -e RUN_INTEGRATION=1 backend python -m pytest -q -o cache_dir=/tmp/pytest-phase2` (root) | **59 passed** on Linux/Python 3.12, 1 upstream warning; ephemeral runner removed. |



### Limits and next gate



The schema enables, but does not implement, event delivery/idempotent worker handlers, refresh rotation, account authorization, watched state or recommendations. Aggregate revisions, session family ownership and per-user replacement locking are future service responsibilities. Timestamp onupdate applies to SQLAlchemy updates; raw SQL/upserts set updated_at explicitly. Prefix title indexing does not accelerate arbitrary substring search. No load benchmark, backup restore or production privilege remediation was performed. Existing Phase 1 high/medium findings remain open, including superuser runtime DB credentials. No new dependency/lint/type tooling was introduced in this database-only phase.



Wait for phase acceptance and the next phase-specific instruction; do not implement APIs automatically.



## Phase 3 backend core — 2026-11-15



Implemented async request database/Redis dependencies, explicit rollback-on-exit sessions, managed resource shutdown, error handling, response/pagination schemas, correlation middleware, structured application/server logging, configured CORS methods/headers and versioned health aliases. Health module layout is introduced with compatibility facades over existing core probes. Database schema and frontend are unchanged.



Targeted command: backend/.venv/Scripts/python -m pytest -q backend/tests/test_backend_core.py backend/tests/test_health.py — 10 passed, one upstream httpx deprecation warning. Tests exercise response/errors, correlation, pagination, async request rollback and Redis/engine shutdown in addition to existing dependency health cases. Full integration results are recorded after execution below.



Remaining limits: health adapters remain synchronous in FastAPI worker threads; existing Phase 1 UI/proxy/privilege findings are not resolved. No business modules or APIs, streaming response recovery, load measurements or production deployment claimed.


Full regression command: RUN_INTEGRATION=1 backend/.venv/Scripts/python -m pytest -q backend/tests — 62 passed, one upstream TestClient/httpx warning. Includes real PostgreSQL/Redis readiness and isolated migration tests. Async lifecycle tests use mocks; real async transaction and concurrent-request tests remain a coverage limitation.


## Phase 4 authentication - 2026-11-15

Implemented registration, login, logout, JWT access, opaque refresh rotation/reuse detection, Argon2id hashing, /users/me, current-user/admin dependencies and atomic Redis limiting. Auth module separates transport, schemas, service, repository, cryptography helpers and limiting. Uses existing users/refresh_tokens without schema changes. Admin authorization is exercised with a test-only route; no admin business feature was added.

Files: created app/modules/auth/{router,schemas,service,repository,security,dependencies,limiter}.py and package initializer, modules/users/router.py and initializer, app/run.py and tests/test_auth.py. Modified main.py/config.py, pyproject.toml/requirements.lock, docker-compose.yml and .env.example; generated local signing key in ignored .env. Updated API/architecture/database/decision docs and README. Maintained Argon2/JWT/email packages avoid custom cryptography.

Security contracts: USER-only registration; 12-128 character passwords; normalized validated email; opaque tokens stored as hashes; absolute family expiry; serialized refresh/logout; reused consumed hashes revoke families in a committed transaction. Protected requests query active user/current role/live token family. No sensitive fields in output. Refresh uses JSON bodies, not cookies; HTTPS and memory-only client storage are required beyond local development. Current proxy shares peer-IP limiter buckets. No email recovery, frontend auth or role management API is implemented.

Commands/evidence:
- Installed argon2-cffi, PyJWT and email-validator in the virtual environment and pinned resolved dependencies in requirements.lock.
- Existing core/health targeted tests: 10 passed.
- First real auth integration run failed because psycopg async cannot run on Windows ProactorEventLoop. Diagnosed in a temporary test setup, restored middleware, configured selector event loop for auth tests and provided local app.run launcher.
- Authentication suite after correction: 8 passed. Added unknown-user and expired-refresh/absolute-expiry tests afterward.
- RUN_INTEGRATION=1 backend/.venv/Scripts/python -m pytest -q backend/tests: **72 passed**, one upstream TestClient/httpx deprecation warning. Uses real PostgreSQL/Redis and disposable schema databases; includes all prior backend tests.
- Docker backend rebuild and Linux verification results follow after execution.

Acceptance checklist:
- [x] Requested auth routes, password hashing, rotation, logout and live authorization implemented.
- [x] Required auth tests plus reuse/concurrent rotation/status/rate-limit outage cases pass on Windows.
- [x] API contracts, configuration and token-storage decisions documented.
- [ ] Linux packaged-image verification recorded.
- [ ] User phase acceptance.

Existing Phase 1 audit findings remain open. Performance/Argon2 production hardware tuning, trusted proxy-aware client identity and browser persistence are not claimed. Tokens are not sent in cookies and token responses are no-store. No automatic ADMIN provisioning or new database schema was added.

Phase 4 additional verification: compileall passed; pip check reported no broken requirements; documentation link/fence checks passed; generated signing key absent from scanned source/example/docs. Linux backend rebuild was attempted twice with `docker compose --progress plain build backend`; container PyPI access timed out and reported no available Mako==1.4.3 candidates while reinstalling the existing lockfile. This does not establish a dependency incompatibility. No Linux auth test or updated-container startup is claimed. Re-run the exact build command when container registry access is restored, then `docker compose run --rm --no-deps -e RUN_INTEGRATION=1 backend python -m pytest -q -o cache_dir=/tmp/pytest-phase4`. Existing running containers were not replaced by failed builds; use the updated local launcher for the new endpoints meanwhile. Packaging validation remains open; Windows real-service authentication behavior is verified by 72 passing tests.
