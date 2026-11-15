# Requirements and acceptance targets

Status: proposed; requirement IDs remain stable across implementation phases.

## Functional requirements

| ID | Requirement and acceptance condition |
| --- | --- |
| FR-01 | Register a unique normalized email with validated password; login returns an authenticated session; invalid credentials return a generic error. Concurrent duplicate registration cannot create duplicate users. |
| FR-02 | Refresh rotates the refresh token; logout revokes the session; suspended accounts cannot authenticate or use existing sessions. Users view and update their own display name and password, with current-password verification for password changes. |
| FR-03 | Browse active movies with pagination, case-insensitive title search, genre and release-year filters, and deterministic title/release-date/popularity sorting. Combined filters work together. |
| FR-04 | Movie details display metadata and genres; inactive movies are unavailable to ordinary users. A detail-page visit records a best-effort view only after successful detail retrieval; view failure never blocks reading. |
| FR-05 | Create, change and remove an integer rating from 1 to 5. Store at most one current rating per user/movie. A successful change atomically creates its outbox event. |
| FR-06 | Independently set/unset watched, favorite and watchlist status with idempotent PUT/DELETE operations; retries do not create duplicate state or change events. Watching does not silently remove a watchlist item. |
| FR-07 | View and paginate own ratings, watched movies, favorites and watchlist. Other users' private collections are inaccessible. |
| FR-08 | Receive recommendations excluding inactive, watched and already-rated movies. Use collaborative predictions when supported, otherwise real popularity values. Return method, generation time and fallback reason without exposing neighbors' identities. Empty eligible catalog returns an empty list. |
| FR-09 | Personal statistics show watched/favorite/watchlist/rated counts, mean current rating and watched-by-genre counts. Multi-genre movies count in each genre; genre totals may exceed watched total. Empty averages are null. |
| FR-10 | ADMIN creates/edits/deactivates movies, assigns genres, manages unique genres and views paginated users. Referenced genres cannot be deleted until assignments are removed. Movie deactivation preserves history. |
| FR-11 | ADMIN suspends/reactivates users and changes roles with audit records. No operator can remove/suspend the last active ADMIN; concurrent changes preserve that invariant. Self-demotion/suspension is rejected in MVP. |
| FR-12 | ADMIN sees user/movie/interaction counts, event backlog/oldest age, retries/quarantine, worker heartbeats and recommendation run status/duration/failure. Manual regeneration and event replay return job identifiers and are audited. |
| FR-13 | Every committed business change requiring async processing writes state and outbox in one database transaction. Duplicate delivery, worker crashes, stale pending entries and Redis loss have verified recovery paths. |
| FR-14 | Recommendation runs record algorithm/configuration, source cutoff, coverage, fallback counts and failure reasons. Failed runs preserve the last successful output and show its age. |

## Roles and authorization

| Capability | Anonymous | USER | ADMIN |
| --- | --- | --- | --- |
| Browse/search active catalog and genres | Yes | Yes | Yes |
| Register/login | Yes | Yes | Yes |
| Read/update own profile and collections | No | Own only | Own only |
| Read personalized recommendations/statistics | No | Own only | Own only |
| Modify catalog/genres | No | No | Yes |
| List users, manage status/roles | No | No | Yes, FR-11 restrictions |
| Read system monitoring, trigger jobs/replay | No | No | Yes |
| Read another user's private collections | No | No | No MVP endpoint |

Authorization is enforced server-side at operation and object levels. UI hiding is convenience only. Background workers use restricted database/Redis service credentials and have no public user endpoints.

## Non-functional requirements

These are proposed test gates on a documented single-host evaluation environment, not production SLAs.

| ID | Target and verification |
| --- | --- |
| NFR-01 Performance | With the overview dataset and 50 concurrent users for 10 minutes, p95 catalog/detail reads ≤500 ms and writes ≤750 ms, excluding network transit; unexpected HTTP 5xx <1%. Report hardware, workload mix, warm/cold cache and DB size using Locust. |
| NFR-02 Freshness | Healthy steady state: 95% of events processed within 30 seconds; scheduled recommendation generation at least every 15 minutes; a run completes within 10 minutes on the evaluation dataset. Expose stale results rather than imply freshness. |
| NFR-03 Durability | API success follows PostgreSQL commit. No acknowledged-but-uncommitted consumer work. Redis flush and publisher/consumer crash tests recover all retained required events. Delivery is at least once. |
| NFR-04 Availability | PostgreSQL failure rejects writes with a controlled 503. Redis failure preserves outbox writes; catalog/collection reads remain available through PostgreSQL and cache bypass. Recommendations use stored successful runs or popularity fallback. |
| NFR-05 Maintainability | Typed Python, Pydantic v2 validation, router/service/repository separation, explicit transaction ownership, Alembic for every schema change; no SQL or business logic in routers. |
| NFR-06 Observability | Structured JSON logs carry request/event/run IDs. Metrics cover request latency/errors, outbox age, consumer lag, pending/retries/quarantine and recommendation run health. Never log passwords or tokens. |
| NFR-07 Usability | Responsive keyboard-accessible core journeys, labeled controls, visible focus, meaningful loading/empty/error states and accessible chart summaries. Verify with Playwright and manual review; do not claim formal accessibility certification. |
| NFR-08 Recovery | Proposed single-host backup targets: RPO ≤24 hours, RTO ≤4 hours, proven by a timed restore exercise before deployment sign-off. Daily PostgreSQL backups stored outside the host; retention 7 daily and 4 weekly copies. |
| NFR-09 Bounds | Pagination defaults 20, maximum 100; search length maximum 200; recommendation limit maximum 50. Reject unbounded queries and invalid filter ranges. Worker memory/time limits and bounded retries protect the host. |

## Security requirements

- Passwords: Argon2id through a maintained Python password hashing library (implementation dependency to approve with its rationale); minimum 12, maximum 128 characters, no silent truncation. Never store plaintext. Benchmark work factor on deployment hardware.
- Short-lived signed access JWTs (15 minutes) held in frontend memory; opaque random refresh tokens in Secure, HttpOnly, SameSite=Lax cookies (7-day absolute session lifetime). Store only refresh-token hashes. Validate issuer, audience, expiration and permitted signing algorithm. Rotate refresh tokens transactionally; reuse revokes the session family. Coordinate refresh across tabs to avoid concurrent rotation.
- Access tokens include a session ID; protected requests verify active user and unrevoked session against PostgreSQL. Logout, suspension, password changes and role changes therefore take effect immediately; do not rely on stale JWT role claims. Password changes revoke all sessions.
- Same-origin frontend/API deployment. Cookie-backed refresh/logout require CSRF token plus Origin validation; no state changes on GET. Local development CORS allows only explicit origins and credentials; never wildcard credentialed CORS.
- Parameterized SQLAlchemy access, input length/type constraints, output schemas that exclude hashes/tokens, generic authentication failures, ownership checks and least privilege roles. Registration never accepts a role field.
- Rate-limit login/registration/refresh, view recording, mutations and expensive admin jobs; initial limits 5 login attempts/minute per IP and account, 3 registrations/hour/IP, 30 refreshes/minute/session, 60 views/minute/user, 120 mutations/minute/user and 5 admin jobs/hour/admin. Tune with tests; Redis outage returns 503 for auth/admin jobs requiring the limiter, while durable authenticated interaction writes use bounded API concurrency.
- Secrets come from environment/deployment secret injection, never source control. TLS is required for public traffic; database and Redis are private. Restrict metrics/admin endpoints and redact personal data from telemetry.
- Audit admin mutations with actor, action, target, UTC time, request ID and safe change summary. Audit writes share the business transaction. Limit audit access and protect backups. Do not copy passwords/tokens into audit payloads.

## Testing and evidence

| Layer | Required scenarios |
| --- | --- |
| Unit / Pytest | Service rules, validation, permissions, recommendation formula fixtures, sparse/cold-start cases, deterministic ranking and retry classification. |
| Integration / real PostgreSQL and Redis | Alembic upgrade from empty DB; uniqueness/FKs/check constraints; concurrent writes; rollback of business+outbox; publish/crash windows; duplicate consumption; pending reclaim; retry exhaustion; poison payload quarantine; replay and Redis-loss recovery. SQLite does not substitute for PostgreSQL semantics. |
| API / Pytest | Auth rotation/reuse/revocation, IDOR prevention, USER vs ADMIN matrix, filters/pagination, idempotent collection operations, consistent errors and cache invalidation after deactivation. |
| End-to-end / Playwright | Register → discover → rate/save → personal statistics/recommendations; admin catalog change, suspension and monitoring; keyboard navigation and failure states. |
| Load / Locust | NFR-01 workload plus event backlog/recovery and recommendation generation alongside API traffic. |
| Operations | Compose startup/readiness, worker restart, unavailable Redis/DB, backup restore, migrations and last-successful recommendation preservation. |

Tests must exercise failure boundaries with controlled process stops/fault injection. Report exact commands and actual outcomes per implementation phase. No executable tests exist in Phase 0; documentation validation is the only current check.
