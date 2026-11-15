# Phase 6 quality audit — user interactions

Date: 2026-11-15 (Asia/Saigon). Reviewer scope: independent source review and fresh execution against the current working tree.

**Verdict: changes required; Phase 6 is not approved as complete.** No critical defect was identified. Two high-priority issues and four medium-priority issues remain. The full backend suite passes, but it does not enforce every documented requirement.

## Scope and evidence boundaries

The last commit is `264847f` (Phase 5 movie catalog). The uncommitted changes and progress record identify Phase 6 as the current phase. This audit covers that working tree, including untracked interaction source, migration and tests. Existing user changes were preserved.

Inspected all five interaction module files, migration 0002, affected models and schema tests, both new test files, router registration, and the shared authentication, database/session, error, correlation, logging and pagination paths. Reviewed catalog schemas/repository/service for decimal-rating regressions, Alembic configuration, test fixtures, dependency manifests, deployment configuration, frontend source/build/browser-test configuration and relevant documentation changes. Generated files and installed dependencies were not audited as authored source.

Requirements were derived from AGENT.MD, REQUIREMENTS.md, API.md, architecture/decision records and the Phase 6 progress entry. The original phase implementation prompt is not present in this audit chat. Claims that it supersedes product requirements are therefore treated as documented scope decisions, not independently verified user acceptance.

Only this report and an appended audit entry in DEVELOPMENT_PROGRESS.md are retained changes from the audit. Temporary diagnostic tests were removed. Tests created disposable PostgreSQL databases through existing fixtures and used uniquely scoped authentication limiter keys. No configured application data was migrated or modified. One fault probe held a row lock only in a disposable database; another used an unused local port in an isolated app instance. No live service was stopped.

## Critical issues

None identified in the inspected implementation and executed scenarios. This is not evidence that all security, operational or concurrency failures are absent.

## High-priority issues

### H-01 — Interaction abuse limits and admission control are missing

Locations: `backend/app/modules/interactions/router.py:21`, `backend/app/modules/interactions/service.py:24`, `backend/app/core/runtime.py:9`; requirement: `docs/REQUIREMENTS.md:62`.

The security contract requires 60 views/minute/user, 120 mutations/minute/user and bounded API concurrency when Redis is unavailable. The interaction routes apply authentication and response headers, but no limiter or admission control. The only Redis limiter is wired to authentication routes. Per-user row locks serialize writes but neither reject excess requests nor bound the number of waiting requests. The connection pool and statement timeout do not implement the documented per-user limits.

**Reproduced:** a newly authenticated user submitted 61 distinct view UUIDs for one movie in **1.62 seconds**. All 61 returned 200 and wrote observations in a disposable database.

Impact: authenticated clients can inflate popularity and grow view/outbox storage rapidly; waiting writes can consume shared database capacity. No saturation benchmark or denial-of-service exploit was performed.

Required correction: enforce the documented limits and bounded admission policy, including the stated Redis-outage behavior. Add boundary, concurrent-request, user-isolation and recovery tests. Acceptance requires the 61st view within the window to be rejected under the documented policy, with no corresponding view/event/sequence change.

### H-02 — API runtime credentials retain PostgreSQL superuser privileges (inherited)

Locations: `docker-compose.yml:6`, `docker-compose.yml:39`, `backend/app/core/config.py:34`.

Compose reuses the PostgreSQL bootstrap identity for the API. A fresh read-only query through the configured backend database URL returned **`rolsuper = true`** for `current_user`. Migration/test database creation privileges are not separated from runtime privileges.

Impact: an API compromise inherits cluster-wide database authority, including schema/data destruction and access beyond the application. Business and interaction endpoints now make this inherited issue more consequential than during the foundation phase. No SQL injection or credential disclosure was demonstrated. Loopback deployment reduces exposure but does not provide least privilege.

Required correction: provision a non-superuser API identity with only required application grants; separate migration/bootstrap and disposable-test administration credentials. Verify normal auth/catalog/interaction behavior with the restricted role and rejection of privileged database operations. Do not change or revoke the current role without a reviewed provisioning/migration sequence.

## Medium-priority issues

### M-01 — Database unavailability and lock exhaustion return 500

Locations: `backend/app/core/errors.py:11`, `backend/app/core/correlation.py:33`, `backend/app/core/runtime.py:10`, `backend/app/modules/interactions/service.py:24`; requirement: `docs/REQUIREMENTS.md:48` (NFR-04).

There is no handler classifying database connectivity, pool exhaustion or statement-timeout failures. The generic middleware emits `500 internal_error`.

**Reproduced:** an isolated app configured to an unused loopback PostgreSQL port returned **500 internal_error** on authenticated POST /interactions/view. Separately, holding the target user's row lock in a disposable database caused POST /interactions/favorites to hit the configured statement timeout and return **500 internal_error**. Bodies were sanitized, which is correct, but the unavailable-database result violates the controlled-503 contract.

Required correction: classify transient database availability failures into a sanitized 503 response; define lock/pool exhaustion behavior and retry guidance. Preserve rollback and keep programming/integrity failures distinguishable. Test failure followed by recovery. View retries must preserve the UUID; avoid implying that every lost commit response means rollback.

### M-02 — Private error responses lose the no-store policy

Locations: `backend/app/modules/interactions/router.py:17`, `backend/app/core/errors.py:12`, `backend/app/core/correlation.py:37`; contract: `docs/API.md:63`.

The router dependency sets a header on FastAPI's injected response. Exception handlers and generic middleware build replacement responses without that header.

**Reproduced:** unauthenticated history (401), invalid rating (422), missing-movie rating (404), and lock-timeout mutation (500) all lacked `Cache-Control`. Successful personal responses have the expected header. Private 404/conflict outcomes can disclose resource state, so applying the policy only to successes is incomplete. No actual intermediary caching or cross-user disclosure was demonstrated.

Required correction: apply no-store to all responses under the private interaction API, including early validation/auth failures and unexpected exceptions. Add assertions for success, 204, 401, 404, 409, 422 and 5xx paths.

### M-03 — Lint and backend static type gates cannot be executed

Locations: `backend/pyproject.toml:17`, `frontend/package.json:6`, `frontend/tsconfig.json:8`.

Explicit Ruff and mypy commands fail with missing modules. No equivalent configured backend linter/type checker was found. Frontend lint and standalone typecheck scripts are absent. The production build does run TypeScript successfully, so frontend application type checking is verified; a missing standalone script does not negate that pass. Its include list excludes browser tests and Playwright configuration.

Required correction: choose and pin reproducible lint/Python type tooling, configure commands and resolve their findings; include authored test/config TypeScript in an appropriate check. Compilation and passing integration tests are not substitutes for static analysis. No hypothetical type errors are claimed by this report.

### M-04 — Unhandled failures lack actionable diagnostic classification

Locations: `backend/app/core/correlation.py:33`, `backend/app/core/logging.py:9`.

The two reproduced database failures logged only `unhandled_request_error` with a request ID, followed by the response status. The handler records no exception category, SQLSTATE or safe operation context; the formatter does not preserve exception information. An unavailable database and a coding defect are operationally indistinguishable through these records.

Required correction: log a safe exception category and relevant operational context with correlation, while keeping credentials, tokens, connection URLs and bound parameters out of logs. Test representative database/programming failures and redaction. Structured JSON and request IDs already work; the missing element is diagnostic content.

## Low-priority improvements and untested edges

1. **Coverage gaps:** current tests cover same-user concurrent duplicates and rating updates, but do not force interaction writes racing catalog soft deletion, suspension, logout/refresh, or simultaneous collection add/remove. The shared row-lock approach is plausible; its complete race matrix is not verified. Add focused tests rather than a broad generic concurrency framework.
2. **Migration edges:** existing tests preserve legacy integer ratings and reject fractional/live-sequence downgrades, but do not seed sub-1 recommendation scores to exercise that downgrade guard. No production-sized migration timing, lock budget, offline downgrade generation or concurrent-write downgrade test was run. The documented operator migration prerequisite is essential because readiness does not verify schema head.
3. **Performance:** history aggregates all of a user's views for both count and page retrieval; pagination permits offsets approaching 100 million rows. Collections use fixed-count joined queries, and no N+1 pattern was found, but neither bounded page size nor fixed statement count proves bounded database work. Benchmark the documented dataset before claiming NFR-01; consider cursor/projection changes only after measurement. The user row lock also serializes authentication session writes with interactions.
4. **Abstractions and duplication:** no materially incorrect new architectural abstraction or duplicated mutation implementation was found. A shared collection implementation for favorites/watchlist is proportionate. Collection model selection is repeated in three repository methods; a small explicit mapping could reduce drift. The fallback to Watchlist for any non-favorites string relies on internal Literal typing; no untrusted string currently reaches it. Reusing Identifier from movie transport schemas couples modules; a shared core ID type would be cleaner if more modules need it. The duplicate page upper bound in catalog/interaction schemas is a small maintenance risk.
5. **Scope/documentation:** FR-05/06/07 still describe rating removal/listing and independent watched state. The Phase 6 note explicitly defers these, so this audit does not invent them as immediate implementation tasks. They remain outstanding product requirements and need traceable acceptance/disposition. README's Phase 5 paragraph still says interactions are future work, and API.md's older admin-auth paragraph says no catalog endpoint exists. Update current-status prose while retaining historical evidence. The preexisting Phase 6 full-regression placeholder is superseded by the fresh result below.
6. **Packaging and broader security:** no rebuilt Linux/Python 3.12 image, cold Compose startup, container vulnerability scan, dependency advisory scan, TLS deployment or backup restore was verified in this audit. Existing documented image-build limitations remain open. Browser tests exercised the currently served health page/proxy; they do not establish that the running backend contains Phase 6. Do not present the browser pass as an interaction UI or updated-container pass.
7. **Warnings:** the upstream Starlette TestClient/httpx deprecation remains; browser tests emit a color-environment warning. Neither failed the executed tests. No numerical line/branch coverage was measured.

## Fresh commands and results

Commands ran from repository root unless a directory is specified. Each result was inspected individually; compound-command final exit codes were not treated as proof of earlier checks.

| Command/check | Actual result |
| --- | --- |
| `$env:RUN_INTEGRATION='1'; .\backend\.venv\Scripts\python -m pytest -q backend/tests` | **101 passed**, 1 upstream warning, **252.87 seconds**; PostgreSQL/Redis integration included. Collected before temporary audit probes were added. |
| `.\backend\.venv\Scripts\python -m pytest -q backend/tests` in a fresh process without the integration flag | **11 passed, 90 skipped**, 1 warning, 3.43 seconds. Integration behavior is not established by this default run. |
| `.\backend\.venv\Scripts\python -m compileall -q backend/app backend/alembic backend/tests` | Pass. |
| `.\backend\.venv\Scripts\python -m pip check` | Pass: no broken requirements. This is dependency consistency, not a vulnerability scan. |
| `.\backend\.venv\Scripts\python -m ruff check backend` | Unavailable: No module named ruff. |
| `.\backend\.venv\Scripts\python -m mypy backend/app` | Unavailable: No module named mypy. |
| `npm run build` (frontend) | Pass: `tsc -b` and Vite production bundle; 146 modules transformed. |
| `npm run lint --prefix frontend` | Unavailable: Missing script lint. |
| `npm run typecheck --prefix frontend` | Unavailable: Missing script typecheck; TypeScript already passed inside build. |
| `npm run test:e2e` (frontend) | **2 passed**, 4.7 seconds, against existing localhost:5173 service; health/proxy and unavailable-API cases only. |
| Temporary pytest diagnostic: `RUN_INTEGRATION=1 ... -m pytest -q -s backend/tests/test_phase6_audit_probe.py --tb=short` | **1 passed**, 18.78 seconds: asserted 61 successful writes, missing error headers and 500 on a real lock timeout. These assertions confirm defects, not acceptance. |
| Additional diagnostic: same command with `-k database_unavailable` | **1 passed, 1 deselected**, 5.07 seconds: asserted 500 from isolated unavailable-DB app. |
| Read-only SQL: `SELECT rolsuper FROM pg_roles WHERE rolname=current_user` | **True** through configured backend URL; no credentials printed. |
| Read-only SQL: `SELECT version_num FROM alembic_version` | **0002_interactions** in configured database. Full schema consistency is independently covered by the integration suite's metadata comparison. |

The diagnostic module was initially placed in Windows TEMP; pytest collection traversed parent directories and failed on inaccessible Windows paths. An explicit root/config attempt had the same collection failure. Moving this audit-owned file under backend/tests allowed collection and successful execution. It was removed after both probes. These initial collection errors are not application test failures. A file-read probe also used the wrong nginx path; the actual `frontend/nginx.conf` was subsequently read.

Probe recipe: use existing `test_auth` disposable-database/client fixtures; register/login, insert a movie, post 61 unique UUID views and inspect status/time; inspect error headers; hold `SELECT ... FOR UPDATE` on that user's row through a second connection while posting a favorite. For database unavailability, create an isolated app using a bound-but-not-listening loopback port and a valid signed access token; POST a view. The unavailable app does not connect to the configured database. No audit probe adds or changes application behavior.

## Passing criteria

- Router/service/repository/schema boundaries, async dependency injection and explicit transaction ownership are present; no router SQL or direct Redis publishing.
- Authenticated ownership is applied throughout the interaction routes. Cross-user isolation and rejected caller-selected user IDs pass integration tests.
- Exact decimal validation, create conflict/update semantics, unchanged-rating no-op and preservation of creation time pass.
- UUID view replay/conflict, grouped history, inactive movie behavior, pagination and independent idempotent collections pass.
- State, durable user sequence and outbox mutation commit/rollback together in the tested failure and concurrency scenarios.
- Empty/legacy-data migrations, schema/model comparison and guarded downgrade/re-upgrade scenarios pass against PostgreSQL.
- Full backend regression, Python compilation, dependency consistency, frontend application TypeScript/build and existing browser tests pass.
- API, schema, event contracts and deployment prerequisites are substantially documented.

## Failing or unresolved criteria

- **Fail:** documented view/mutation limits and API concurrency admission policy (H-01).
- **Fail:** least-privilege runtime database role (H-02, inherited and freshly confirmed).
- **Fail:** controlled unavailable-database 503 behavior (M-01).
- **Fail:** no-store policy across private error responses (M-02).
- **Unavailable gate:** lint and backend static typing; frontend browser-test/config static coverage (M-03).
- **Fail:** useful sanitized operational error classification (M-04).
- **Unverified:** load targets, the expanded race matrix, rebuilt Linux image and production operational/security checks listed above.
- **Outstanding product scope:** deferred rating removal/listing and independent watched features; do not count them as delivered by Phase 6.

Phase completion is withheld pending high-priority remediation and explicit disposition/verification of the remaining quality gates. No new feature implementation or unrelated refactoring was performed.
