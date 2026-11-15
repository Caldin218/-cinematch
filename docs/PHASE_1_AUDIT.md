# Phase 1 quality audit

Date: 2026-11-15. Scope: project foundation only. Earlier implementation claims were independently checked against current source and fresh execution.

**Verdict: core foundation checks pass; the quality gate remains open.** No critical issues were identified. One high-priority defect and six medium-priority findings require attention. This is not unconditional Phase 1 approval. No application code, dependencies or business features were changed during the audit.

## Scope and method

Inspected authored backend application modules, tests, Alembic environment/template, frontend source/browser tests, TypeScript/Vite/Playwright configuration, package manifests/lockfiles, Dockerfiles/ignore rules, Compose, environment example, smoke script, README and implementation docs. Compared them with the Phase 1 request and architectural blueprint. Generated output, dependency source and bytecode were excluded from authored source review. Lockfile inspection does not mean every dependency's source was security-reviewed.

Executed available tests/build/checks, inspected container health/logs, and used temporary read-only browser probes to intercept readiness responses. Queried the configured database role's privilege flag without printing credentials. No application data or service availability was changed by the fault probes. Builds/tests wrote normal ignored artifacts. Only audit documentation and the progress record were edited. The progress file changed to a phase checklist template during review; its latest contents were preserved and the audit record appended.

## Critical issues

None found within the local-only Phase 1 scope. This is not production/security certification or proof that all failure paths are covered.

## High-priority issues

### H-01 — Unexpected HTTP 503 payload blanks the diagnostic page

Locations: `frontend/src/lib/api.ts:12`, `frontend/src/pages/HealthPage.tsx:21`.

The client accepts every HTTP 503 as typed Health data, although Axios generics do not validate runtime bodies. A plain-text or HTML proxy error lacks checks; Object.entries(health.data.checks) then throws. A browser probe fulfilled the readiness request with status 503, content type text/plain and body `Service unavailable`. Captured page error: `Cannot convert undefined or null to object`. The resulting body text was empty.

Impact: the health page disappears during a plausible infrastructure failure. The existing aborted-request test does not cover this case.

Correction: validate the response shape before accepting diagnostic data; reject malformed status/body combinations into the query error state. Test valid JSON 503, text/HTML 503 and malformed JSON objects. A render error boundary is additional protection, not a substitute for response validation.

Acceptance: invalid payloads show a usable error state and retry control with no uncaught render errors.

## Medium-priority issues

### M-01 — Lint and backend static type gates are absent

Locations: `frontend/package.json:6`, `backend/pyproject.toml:16`, `frontend/tsconfig.json:8`.

`npm.cmd run lint` fails with Missing script. Python probes for Ruff and mypy fail because those modules are not installed/configured. These are probe choices, not required technology selections; equivalent maintained tooling can satisfy the gap. No backend static type pass can be claimed.

The configured TypeScript check passes, but excludes tests/ and playwright.config.ts. Running Playwright does not statically type-check these files. The mixed callable/resource tuple in HealthService also weakens Python type narrowing and should be checked with the chosen checker.

Correction: define reproducible lint/type commands and development dependencies, include all authored TypeScript through suitable check configurations, run them and resolve actual findings.

### M-02 — Failed refresh retains an unqualified success status

Location: `frontend/src/pages/HealthPage.tsx:16–24`.

After a successful live readiness check, a browser probe aborted the next request. The error alert, `All services ready` heading and API `reachable` value remained visible together. A stale-data disclaimer was also visible, so historical values are disclosed, but the primary status still asserts success.

Correction: derive current status from fetch failures and explicitly label cached results as historical, with their check time. Add a success → failure → recovery regression test.

### M-03 — Runtime application uses a PostgreSQL superuser

Location: `docker-compose.yml:6` and backend environment wiring.

A read-only query through the backend SQLAlchemy connection returned rolsuper=True for current_user. The bootstrap PostgreSQL role is reused by the API. Future API compromise would inherit cluster-wide privileges. Loopback bindings and no business endpoints reduce present exposure; no exploit was demonstrated.

Correction: separate bootstrap/migration credentials from a non-superuser runtime role, document provisioning, and verify grants before business data or public deployment. Normal current connectivity passes.

### M-04 — Database readiness lacks an execution deadline

Locations: `backend/app/core/database.py:13–23`, `backend/app/core/health.py:26–31`.

Connection acquisition has timeouts, but SQL SELECT 1 and pool pre-ping have no configured execution/network deadline. Checks are sequential. The frontend's 10-second timeout and Compose probe timeout limit their callers, not the synchronous backend thread performing dependency I/O.

Risk: a connected but stalled database/network can occupy readiness threads beyond the caller budget; repeated polling can compound this. This is a source-confirmed missing bound, not a reproduced network-blackhole/load result.

Correction: define a total probe budget with driver/server execution and transport bounds, and test stalled established connections. PostgreSQL documents [connect_timeout as a connection-establishment setting](https://www.postgresql.org/docs/17/libpq-connect.html#LIBPQ-CONNECT-CONNECT-TIMEOUT); it is not a SQL execution deadline.

### M-05 — Proxy replacement recovery is unverified

Location: `frontend/nginx.conf:8` and frontend Compose health check.

proxy_pass uses a static hostname without dynamic re-resolution configuration. Frontend container health checks only the static root. Startup ordering does not verify ongoing API reachability.

Risk/inference: if backend replacement receives another IP, the running proxy may retain the old resolution until reload/restart, while frontend health remains green. Current proxy traffic passes. No IP-changing backend recreation was performed in this read-only review; this is not a reproduced outage.

Correction: configure/test DNS-aware upstream recovery or document a coupled proxy restart; verify a backend address change. Keep frontend liveness distinct from end-to-end readiness. See [NGINX proxy resolution behavior](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass).

### M-06 — Structured logging is incomplete

Locations: `backend/app/core/logging.py:6–20`, `backend/app/main.py:20`.

Fresh Docker logs contain plain-text Uvicorn access lines even though application dependency warnings can use JSON. The custom formatter drops exception information and contextual fields except dependency; request correlation is absent. Broad Exception handling protects health responses but collapses infrastructure and programming failures into the same sparse warning.

Correction: configure server/application logging consistently, preserve sanitized error categories and useful exception context, and verify representative startup/access/dependency-error records. Do not leak credentials or connection URLs. The global structured-logging requirement is partially satisfied.

## Low-priority improvements

1. **Untested edges:** malformed 503, stale refresh/recovery, Redis PING returning false, missing/invalid settings, CORS, exceptional startup/shutdown cleanup, session rollback, proxy address changes and stalled I/O. No numerical coverage metric was collected. Alembic history alone does not test migration execution. Prioritize tests accompanying the findings above.
2. **Unused abstraction:** database.py:30 defines session_scope as an unused generator with a context-manager-style name, without contextmanager decoration or request-dependency wiring. No current caller fails, but future misuse is possible. Choose its actual purpose before use. No material duplicated business logic was found; probes at unit, browser, smoke and Compose layers serve different purposes.
3. **Exceptional lifecycle cleanup:** client construction precedes lifespan's try/finally; redis.close precedes engine.dispose without an independent finally. Construction/close exceptions can skip cleanup. Normal shutdown is tested and passes.
4. **Dependency drift/hardening:** mutable base tags, setuptools without an upper pin, runtime/test tools combined in the image, and a Windows-generated package freeze rather than a cross-platform resolver artifact. Current Windows/Linux checks pass. Python package and container OS vulnerability scanners were not configured/run; npm advisories do not cover them.
5. **Documentation drift:** PROJECT_OVERVIEW.md says awaiting Phase 0 approval; DECISIONS.md opens by saying implementation evidence does not exist, despite later amendments. README's Node requirement has no package.json engines enforcement. No Git repository exists, so commit history and historical secrets cannot be assessed. The live progress file is now a template; audit evidence is appended without replacing it.
6. **Local exposure:** npm run dev binds Vite to all interfaces, unlike loopback-bound Compose. Bind localhost or document LAN exposure. No TLS, Redis authentication or business auth is a documented local Phase 1 limitation, not a requirement to implement future business features now.
7. **Warnings:** upstream TestClient/httpx deprecation and Playwright color-environment warning remain. The container cache warning can be avoided with a writable /tmp test cache. None caused test failure.

## Commands and fresh results

Results were inspected per command; the final exit code of a compound shell invocation was not used as evidence for preceding commands.

| Directory | Command/probe | Result |
| --- | --- | --- |
| backend | `.venv/Scripts/python -m pytest -q` | 7 passed, 1 integration test intentionally skipped; one deprecation warning |
| backend | `.venv/Scripts/python -m pip check` | Pass: no broken requirements |
| backend | `.venv/Scripts/python -m ruff check app tests` | Cannot run: No module named ruff |
| backend | `.venv/Scripts/python -m mypy app` | Cannot run: No module named mypy |
| frontend | `npm.cmd run build` | Pass: TypeScript check and production build, 146 modules |
| frontend | `npm.cmd run lint` | Fail: Missing script lint |
| root | `frontend/node_modules/.bin/tsc.cmd --noEmit -p frontend/tsconfig.json` | Pass, exit 0; tests/Playwright config outside include list |
| root | `docker compose config --quiet` | Pass after authorized elevated Docker access; no resolved secrets printed |
| root | `docker compose ps --format 'table {{.Service}}\t{{.Status}}'` | All four services healthy |
| root | `docker compose exec -e RUN_INTEGRATION=1 backend python -m pytest -q -o cache_dir=/tmp/pytest-audit-cache` | 8 passed on Linux/Python 3.12, including real PostgreSQL/Redis; one upstream warning |
| frontend | `npm.cmd run test:e2e` | 2 passed against live stack; color-environment warning |
| root | `./scripts/smoke.ps1` | Pass: liveness, readiness, SPA and API proxy |
| frontend | `npm.cmd audit --json` | Exit 0; 0 known npm vulnerabilities |
| frontend | Temporary Playwright aborted-refetch probe | Confirmed stale success/API reachable alongside error and disclaimer |
| frontend | Temporary Playwright text/plain 503 probe | Confirmed uncaught render error and empty body |
| root | Read-only privilege query through backend engine | Current role rolsuper=True |
| root | `docker compose logs --tail 8 backend` | Plain-text server access logs confirmed |

Initial Docker access was denied by sandbox permissions; elevated retry succeeded. No unresolved approval blocker prevented core tests. Lint/backend type tooling is absent from the project; those checks cannot be described as passing. No fresh image rebuild, destructive persistence test, load run, Python/container advisory scan or migration upgrade was performed.

Browser probe reproduction uses installed Playwright Chromium in frontend/. For M-02, visit /health, await success, uncheck auto-refresh, intercept `**/api/health/ready` with route.abort(), click Check again, then inspect alert and heading. For H-01, intercept before navigation using route.fulfill({status:503, contentType:'text/plain', body:'Service unavailable'}), capture pageerror and inspect body text. These probes were temporary stdin Node scripts, not persisted regression tests.

## Passing and failing criteria

| Criterion | Audit outcome |
| --- | --- |
| Requested monorepo, approved stack and entry points | PASS |
| Four services, health checks and persistent-volume configuration | PASS in current running environment; fresh rebuild/volume recovery not repeated |
| Frontend production build and configured TypeScript check | PASS |
| Backend starts and connects to real PostgreSQL/Redis | PASS |
| GET /health, /health/ready and frontend API communication | PASS under normal operation and existing failure mocks |
| Environment-driven config; no actual credential hardcoded in reviewed authored source | PASS source review; Git history unavailable |
| Thin routers, no router SQL, dependency lifecycle separation | PASS normal operation; exceptional cleanup risk noted |
| Application database consistency | No application tables/schema changes; transaction-heavy business behavior is outside this phase |
| Graceful UI for malformed upstream failure | FAIL: H-01 |
| Accurate current UI after failed refresh | FAIL: M-02 |
| Reproducible lint and complete static type gates | FAIL/unavailable: M-01 |
| Least-privilege runtime database role | FAIL: M-03 |
| Bounded dependency execution and proxy replacement recovery | NOT PROVEN: M-04/M-05 |
| Uniform structured logging | PARTIAL: M-06 |
| Performance targets, restore/replay, migration upgrades, Python/container advisories | NOT EVALUATED; no results claimed |
| No business-feature scope expansion | PASS |

## Remediation gate

Correct H-01 first, then M-02 and M-01 with executable regression/lint/type checks. Resolve or explicitly disposition the remaining medium findings before quality approval, and verify security/operational hardening before production use. Re-run affected checks and record actual evidence. Core happy-path requirements are verified; the audit remains open. Services were left running, and no new business phase was started.
