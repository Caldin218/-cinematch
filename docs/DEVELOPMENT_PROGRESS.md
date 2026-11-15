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

## Phase 5 movie catalog - 2026-11-15

Implemented public movie listing/detail/title-prefix search, genre reads, ADMIN movie create/patch/soft-delete and genre create/rename/delete. Filters cover genre, exact release year and inclusive average-rating range; sorting covers actual view count, average rating and year with deterministic ID ties. Pagination uses the existing page envelope, max 100 items and max page 1,000,000. Schema/index review reuses existing prefix/year/genre and aggregate-source indexes; no migration needed.

Files created: app/modules/movies/{__init__,router,schemas,repository,service}.py, app/modules/genres/{__init__,router,schemas,repository,service}.py and tests/test_catalog.py. Modified app/main.py to register routers, README.md, docs/API.md, ARCHITECTURE.md, DATABASE.md, DECISIONS.md, EVENT_FLOW.md and this progress checklist. No frontend, dependencies or unrelated modules changed.

Architecture: async DI and repository SQL; services own transactions and cache policy. Movie writes lock rows, increment versions and commit outbox events atomically. Ratings/views are aggregated independently; one batched genre query prevents N+1. Genre assignments lock referenced genre rows; missing genres reject writes. Genre uniqueness/reference conflicts return 409. Redis caches only genre lists for 60 seconds with validated payloads, best-effort invalidation and fail-open PostgreSQL fallback.

Verification commands (PowerShell, repository root):
- `$env:RUN_INTEGRATION='1'; .\backend\.venv\Scripts\python -m pytest -q backend/tests/test_catalog.py`: initial 5 passed.
- `$env:RUN_INTEGRATION='1'; .\backend\.venv\Scripts\python -m pytest -q backend/tests`: **77 passed**, one upstream TestClient/httpx deprecation warning, 113.86 seconds. Real PostgreSQL/Redis; disposable migrated databases. Includes authorization on every admin route, filter/sort/pagination, invalid IDs/bodies, soft-delete visibility, genre conflicts, persisted movie event versions, cache hit/corruption/outage, and exactly three listing SQL statements with multiple movies.
- `.\backend\.venv\Scripts\python -m compileall -q backend/app backend/tests`: passed.
- `.\backend\.venv\Scripts\python -m pip check`: no broken requirements.
- Final targeted rerun after adding a page upper bound: result recorded below.

Acceptance checklist:
- [x] Public catalog reads and admin movie/genre management implemented.
- [x] Filters, stable sorting, pagination, validation and authorization tested.
- [x] Independent aggregates and batched genres prevent join multiplication/N+1.
- [x] Redis caching and degraded-cache behavior tested.
- [x] Existing schema/indexes reviewed; outbox state persisted with movie writes.
- [x] API, architecture, data/event decisions and README updated.
- [ ] User phase acceptance.

Limitations: prefix search rather than substring/fuzzy search; aggregate sorts are computed live and have no production-volume benchmark; count/page use READ COMMITTED and can differ during concurrent writes. Genre-list invalidation/read-fill races or Redis outages permit bounded stale data until TTL after fill. Movie reads always query PostgreSQL. No restore endpoint, catalog UI, interaction writes, publisher or worker is implemented in this phase. Pending outbox rows are intentionally retained. Existing Phase 1 audit and Phase 4 Docker packaging limitations remain open; no updated Linux image/startup claim. No configured lint/static type checker exists; compilation is not a substitute for static checking. Frontend unchanged, so its build was not rerun.

Final page-bound/catalog rerun: **5 passed**, one upstream warning, 36.48 seconds. Includes the added oversized-page rejection and the real SQL statement-count assertion. Final source compilation also passed.

## Phase 6 user interactions - 2026-11-15

Implemented all requested /api/v1/interactions routes: view, rating create/update, grouped history, favorites and watchlist add/remove/list. Every route requires current_user; client-controlled user identity is rejected in bodies and never used for queries. Private responses are no-store. Existing models remain canonical; the new module separates router/schemas/service/repository without unmanaged connections or SQL in routers.

Created: app/modules/interactions/{__init__,router,schemas,service,repository}.py, alembic/versions/0002_interactions.py, tests/test_interactions.py and tests/test_interaction_migration.py. Modified: app/main.py, app/models/{users,interactions,recommendations}.py and tests/test_database_schema.py for the new head/check. Documentation updated: README, API, DATABASE (including ERD), ARCHITECTURE, REQUIREMENTS, PROJECT_OVERVIEW, USER_FLOWS, DECISIONS, EVENT_FLOW, RECOMMENDATION, DEPLOYMENT and this checklist. No frontend or dependencies changed.

Design: NUMERIC(3,2) supports exact 0.50-5.00 input with at most two decimal places. POST rating returns 409 for an existing pair; PUT preserves created_at and updates atomically, with equal-value PUT a no-op. View request UUIDs deduplicate per user; conflicting reuse returns 409. Favorites/watchlist insert/remove are idempotent and independent. History groups view observations rather than duplicating watched state. Inactive summaries remain available in private lists and removable from collections; new writes require active movies. Services lock users and active movies, increment a durable per-user sequence only for actual changes, and append outbox events in the same transaction. No stream publishing/workers were added.

Verification commands/evidence:
- `$env:RUN_INTEGRATION='1'; .\backend\.venv\Scripts\python -m pytest -q backend/tests/test_interactions.py -x`: first run 21 passed, 1 failed. Concurrent writes were consistent, but the assertion exposed decimal event formatting 2.5 versus 2.50. Event strings were standardized to exactly two places.
- `$env:RUN_INTEGRATION='1'; .\backend\.venv\Scripts\python -m pytest -q backend/tests`: next run 100 passed, 1 failed during rating creation. Inspection found separate clock_timestamp() expressions could violate initial timestamp ordering. Initial rating timestamps now both use stable statement_timestamp(); an equality assertion covers this correction.
- `$env:RUN_INTEGRATION='1'; .\backend\.venv\Scripts\python -m pytest -q backend/tests/test_interactions.py backend/tests/test_interaction_migration.py -x`: **23 passed**, one upstream TestClient/httpx warning, 139.51 seconds. Covers duplicate/create/update, decimal boundaries, no-ops, repeated views/conflicting UUIDs, history/pagination, inactive movies, both collections, own-user isolation, unauthorized access, malformed input, outbox insertion failures, pre-commit failures and concurrent requests. Migration tests preserve legacy integer data, exercise compatible downgrade/re-upgrade and reject fractional/live-sequence data loss.
- `.\backend\.venv\Scripts\python -m compileall -q backend/app backend/alembic backend/tests`: passed.
- `.\backend\.venv\Scripts\python -m pip check`: no broken requirements.
- Source parsing and local documentation link/fence checks: passed.
- Configured development database inspected without exposing secrets: revision 0001, zero users/ratings/views/favorites/watchlists/outbox rows. From backend, `.\.venv\Scripts\python -m alembic upgrade head`, `... -m alembic current`, `... -m alembic check` succeeded: **0002_interactions (head)**; no new upgrade operations detected. No retained interaction data was changed. Startup still does not auto-migrate.
- Final full regression outcome is recorded below when it finishes.

Acceptance checklist:
- [x] Requested authenticated routes and own-user scoping implemented.
- [x] Exact decimal scale and a real Alembic migration implemented and verified.
- [x] Atomic rating updates, view retry identity and idempotent collection state tested.
- [x] Business state, durable sequence and pending outbox commit/rollback together.
- [x] Concurrent repeats and injected transaction failures covered against PostgreSQL.
- [x] API/data/architecture/event/deployment docs and product scale updated.
- [ ] Final full backend regression recorded.
- [ ] User phase acceptance.

Limitations: watched history is recorded views, not playback completion; no independent watched/unwatch or rating delete/list endpoint was requested here. API precision is at most two decimal places, with no half-step restriction. Same-user writes serialize under a row lock and may hit the existing statement timeout under contention; no throughput guarantee is claimed. READ COMMITTED count/page reads are not snapshots. Transport disconnects around COMMIT can have ambiguous outcomes; view clients must retry the same UUID. Pending events are retained for a future publisher; delivery/consumer recovery is not implemented. Existing Phase 1 audit and Linux-image packaging limitations remain open. No configured lint/static type checker exists; compilation and integration tests do not substitute for static analysis. Frontend is untouched and its build was not rerun.

## Phase 6 independent quality audit — 2026-11-15

Status: **changes required; phase completion withheld**. See [Phase 6 audit report](PHASE_6_AUDIT.md) for severity, source locations, reproductions, acceptance criteria and execution limits. No critical issue identified; two high-priority and four medium-priority issues remain.

- [x] Full backend regression freshly executed: **101 passed**, one upstream warning, 252.87 seconds, with real PostgreSQL/Redis integration.
- [x] Default backend run: **11 passed, 90 skipped**, one warning. Compilation and pip dependency consistency passed.
- [x] Frontend application TypeScript/production build passed; existing Playwright health suite **2 passed**.
- [x] Confirmed missing interaction limiting (61 views accepted in 1.62 seconds), 500 on unavailable DB/lock timeout, missing private error no-store headers and runtime DB superuser privileges.
- [ ] H-01: interaction abuse limits and bounded admission implemented and verified.
- [ ] H-02: separate least-privilege runtime database role provisioned and verified.
- [ ] M-01 through M-04: error classification, private headers, static gates and safe diagnostics resolved or explicitly dispositioned.
- [ ] Load/race/packaging checks and deferred product requirements accepted with accurate scope.
- [ ] Quality acceptance after remediation and re-review.

Only audit documentation is retained from this review. Temporary diagnostic tests were removed; application source, dependencies and existing implementation changes were preserved. The fresh 101-test result above supersedes the earlier pending full-regression placeholder; passing tests do not grant unconditional phase approval.

## Phase 7 remediation — 2026-11-15

Implemented producer-side contract validation, strict schema version checking, operator replay preserving event identity, supervised Compose worker services, corrected migration-head assertions, required Mermaid flow/recovery diagrams and operational instructions. New regressions exercise publisher crash after XADD, Redis failure, restart, duplicate publication, replay after stream loss, handler rollback, pending recovery, competing consumers, ACK failure, schema validation and graceful stop admission/cleanup.

Verification is recorded below after the full regression run. Earlier Phase 6 statements that workers are future work describe the historical Phase 6 boundary and are superseded by Phase 7. Phase 6 abuse limits/runtime database privilege findings remain separate unresolved work; this phase does not claim to resolve them.

Remaining operational limitations: operator-triggered recovery after Redis data loss, unbounded stream retention, poison entries retained pending manual remediation, no automated backlog metrics, no throughput/shutdown latency guarantee, and only PostgreSQL transactional handler effects covered by deduplication. Mypy is scoped to event modules with silent imported-module following; unannotated function bodies are not a complete strict typing guarantee. Graceful signal control is unit-tested; OS process termination during an actual network stall remains untested.

Final event-only verification: **15 passed in 49.79 seconds**, with real PostgreSQL and Redis. Scoped Ruff checks, mypy with the Pydantic plugin, compileall, pip check and Compose workers configuration validation pass. Frontend `npm run build` passes (TypeScript and Vite, 146 modules). Initial full suite: 111 passed / 1 failed due to the now-corrected second stale migration-head assertion. Fresh full-suite result follows when finished.

Changed in remediation: event schema/factory, publisher replay, CLI replay, handler annotations, producer factory calls in movie/interaction services, test_events.py, both migration-head assertions, pyproject tooling, Compose worker profile, EVENT_FLOW.md, DEPLOYMENT.md, PHASE_7_AUDIT.md and this progress record. Pre-existing unrelated changes remain preserved.

Full backend integration regression after fixes: **114 passed, 1 upstream Starlette/httpx deprecation warning, 303.08 seconds**. Two subsequently added tests (signal cleanup and ambiguous XADD confirmation) are included in the final **15/15** event suite above. No application behavior changed after the full run beyond type annotations/producer factory cleanup, which the final event suite covers; interaction/catalog functional tests also completed successfully in the full run. All collected full-suite tests passed; no skipped integration tests in that run.

Acceptance: **Phase 7 functional acceptance criteria verified with documented operational limitations**. No next-phase work started. Production throughput, OS kill under a stalled connection, automated quarantine and strict whole-backend typing remain outside this verification. Phase 6 audit findings remain open independently.

## Phase 8 � reliable background workers � 2026-11-15

Implemented consumer group recreation, XREADGROUP/commit-before-ACK, bounded PEL cursor recovery, active-message heartbeat, durable configurable exponential retry policies, dead-letter stream with atomic quarantine/ACK, transactional event-id deduplication, signal shutdown, HTTP health and Prometheus-compatible consumer metrics. Added failure-injection integration coverage and EVENT_FLOW recovery procedures. No database schema changes or new dependencies.

Files: consumer.py, new reliability.py/health.py, worker.py, config.py, test_events.py, .env.example, docker-compose.yml, README and event/decision/progress docs. Existing Phase 6 audit findings remain open.

Validation: initial existing event suite 15 passed; expanded failure suite 21 passed with real PostgreSQL/Redis. Scoped Ruff, backend-configured mypy (8 modules) and compilation passed. A root-directory mypy invocation initially missed the backend Pydantic plugin settings and reported four Settings constructor errors; rerun from backend passed. Final expanded event and full regression results follow.

Limits: standalone Redis only; process-local metrics reset on restart; Redis persistence loss requires retained-outbox replay; no automatic retention; arbitrary non-database Python handlers have no hard shutdown bound; external effects need their own idempotency. Service outages are injected at client boundaries while using real services for recovery, without stopping shared services.

Final targeted verification: `$env:RUN_INTEGRATION='1'; backend/.venv/Scripts/python -m pytest -q backend/tests/test_events.py` � **23 passed in 118.43 seconds**, including consumer commit-failure and live HTTP health/metrics tests. `backend/.venv/Scripts/python -m ruff check backend/app/events backend/tests/test_events.py` and `... -m compileall -q backend/app backend/tests` passed; from backend, `.venv/Scripts/python -m mypy app/events` passed (8 source files). `docker compose --profile workers config --quiet` succeeded with Docker-config access warnings; no image rebuild or live worker deployment is claimed.

Full backend regression: `$env:RUN_INTEGRATION='1'; backend/.venv/Scripts/python -m pytest -q backend/tests` � **124 passed, 1 existing Starlette/httpx deprecation warning in 367.34 seconds**. The final targeted event run additionally verifies the final infrastructure-backoff metadata change made while the full run was underway.

Phase 8 acceptance checklist:
- [x] Group management, commit-before-ACK and transactionally idempotent handlers.
- [x] PEL monitoring, stale recovery and long-running heartbeat.
- [x] Configurable bounded handler retries, exponential backoff and atomic dead-letter quarantine.
- [x] Graceful admission stop, internal worker health and all six requested metrics.
- [x] Failure-injection integration tests, full backend regression and recovery documentation.
- [ ] User phase acceptance; no Phase 9 work started.


## Phase 9 — recommendation engine — 2026-11-15

Status: implementation and local verification complete; awaiting phase acceptance.

- [x] Bayesian popularity from rating count, average and log-normalized views.
- [x] Sparse user-item indexes, centered/shrunk cosine, lazy cached Top-K neighbors and weighted predictions.
- [x] Normalized hybrid weights, rated-item exclusions, user/movie cold starts and popularity fallback.
- [x] Separate data adapters, pure algorithm modules and offline evaluation; no complex ML or added dependencies.
- [x] Deterministic metrics, global temporal split, leakage rejection and MovieLens 100K CLI.
- [x] 19 deterministic engine tests passed; backend default suite: 42 passed, 101 skipped, one existing Starlette deprecation warning.
- [x] Ruff passed for new engine/tests; mypy with backend/pyproject.toml passed for all nine engine files.
- [x] Real MovieLens 100K run: MAE 0.837879, RMSE 1.041161, Precision@10 0.172414, Recall@10 0.049412; CF coverage 12.4%. Full details in RECOMMENDATION.md.
- [x] README, architecture, decisions and algorithm documentation updated.
- [ ] User accepts Phase 9 deliverables.

Created backend/app/recommendation_engine/{__init__,config,data,loading,popularity,similarity,user_based_cf,hybrid,evaluation}.py and backend/tests/test_recommendation_engine.py.
Updated README.md and docs/{RECOMMENDATION,ARCHITECTURE,DECISIONS,DEVELOPMENT_PROGRESS}.md.

Commands run from repository root: `.\backend\.venv\Scripts\python -m pytest -q backend/tests`,
`.\backend\.venv\Scripts\python -m pytest -q backend/tests/test_recommendation_engine.py`,
`.\backend\.venv\Scripts\python -m ruff check backend/app/recommendation_engine backend/tests/test_recommendation_engine.py`,
`.\backend\.venv\Scripts\python -m mypy --config-file backend/pyproject.toml backend/app/recommendation_engine`.
MovieLens command from backend: `.\.venv\Scripts\python -m app.recommendation_engine.evaluation "$env:TEMP/cinematch-ml-100k-u.data"`.
An initial mypy invocation without the backend config reported settings/plugin errors; the configured invocation passed.
Integration tests requiring RUN_INTEGRATION=1 were not run; SQL adapter mapping was tested using a mocked session.

Limitations: cold/sparse profiles reduce CF coverage; no production quality claim or tuned baseline comparison.
Neighbor cache belongs to a snapshot and requires engine replacement after updates. No historical database replay.
Next: Phase 10 API/worker integration and an explicit migration for hybrid persistence; no such schema/API changes in Phase 9.

## Phase 10 - recommendation integration - 2026-11-15

Implemented PostgreSQL-backed per-user scheduling from Redis Stream events and
manual refresh, bounded configurable batching, lease/revision fencing, retry with
previous-generation preservation, hybrid persistence, generation duration/version,
and validated namespaced Redis cache-aside. API reads exclude currently rated and
inactive movies even before the event consumer catches up. Cold-start and missing
recommendation data have explicit fallback behavior.

Acceptance checklist:
- [x] Interaction actor identification and catalog fanout; scheduling shares event receipt transaction.
- [x] Durable batched refresh returns 202 without engine execution.
- [x] Concurrent upserts, exclusive expiring claims, stale-worker and revision fencing.
- [x] Batching also spaces superseded calculations under continuous interactions.
- [x] Atomic result/metadata replacement; empty generations; failure preservation/retries.
- [x] Cache hit/miss, TTL, explicit and logical invalidation, corruption validation and outage fallback.
- [x] Top-N, current rated/inactive exclusions, popularity cold start and labeled catalog fallback.
- [x] Eventual consistency, freshness expectations, score scales, deployment and limits documented.
- [ ] User phase acceptance.

Created: app/modules/recommendations/{scheduling,worker,cache,schemas,repository,service,router,__init__}.py,
alembic/versions/0004_recommendation_jobs.py and tests/test_recommendations.py.
Updated: models/registry, settings, event handlers/worker CLI, application routers,
schema/model/migration regression expectations, .env.example and Compose; README,
API, architecture, database, deployment, events, recommendations, decisions,
project overview and this progress checklist. No new dependencies.

Verification commands from repository root:
- RUN_INTEGRATION=1 backend/.venv/Scripts/python -m pytest -q backend/tests --tb=short:
  156 passed in 431.44 seconds. This full run preceded the last added lease/batching
  edge tests and the batching refinement; final targeted verification follows below.
- RUN_INTEGRATION=1 backend/.venv/Scripts/python -m pytest -q backend/tests/test_recommendations.py
  backend/tests/test_database_schema.py backend/tests/test_interaction_migration.py:
  65 passed in 86.83 seconds at the initial integration checkpoint.
- backend/.venv/Scripts/python -m pytest -q backend/tests: final default run
  49 passed, 110 skipped in 5.37 seconds (real-service tests intentionally skipped).
- Scoped Ruff, configured mypy (nine new/modified recommendation modules), compileall,
  git diff --check and docker compose --profile workers config --quiet passed.
- One existing Starlette/httpx deprecation warning remains.

An early in-flight verification failed while migration/check expectations were still
being edited (Alembic constraint naming and head revision); these were corrected and
subsequent schema/integration and full regression runs passed.

Limits: full sparse snapshot per user job, catalog fanout O(active users), no periodic
global rebuild or hard calculation timeout. Peer interactions affect another user's
next refresh rather than eagerly refreshing every user. Lease size should exceed
normal compute time. Metrics are process-local. Development database and live Docker
services were not migrated/rebuilt automatically; apply head before deployment.

Final post-refinement verification: RUN_INTEGRATION=1 backend/.venv/Scripts/python
-m pytest -q backend/tests/test_recommendations.py
backend/tests/test_events.py::test_worker_signal_finishes_and_closes --tb=short:
**17 passed in 92.01 seconds**, including continuous-interaction batch spacing,
Redis-outage refresh, event invalidation, concurrent scheduling, lease replacement,
calculation failures, true hybrid persistence and API cache/rating behavior. Scoped
Ruff and mypy were rerun after the batching refinement and passed; final compileall
and diff whitespace verification passed. Phase 10 implementation is complete;
no next-phase work was started.

## Phase 11 - frontend foundation

Added cinematic theme tokens, responsive discovery preview, reusable movie rows,
half-star poster ratings, refresh CTA, expandable local comment threads, UI states,
focused auth layout, user layout and shadcn-compatible Button primitive. Added
Lucide, Radix Slot, CVA, clsx and tailwind-merge. Axios attaches an in-memory JWT
and clears authentication on 401; TanStack Query has shared freshness/retry defaults.

Verification: npm run build (tsc -b and vite build) passed. No browser visual QA
claimed. Discovery data and poster artwork are deliberate design placeholders;
comments, favorites and vault state are session-local. Auth/social submission and
personalized refresh are explicitly unavailable in this foundation preview.
No community feed is present on auth pages. Backend integration, refresh-token
rotation and durable discussion APIs remain outside this foundation implementation.
