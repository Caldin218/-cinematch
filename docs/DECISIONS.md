# Architecture decision log

All entries dated 2026-11-15. Status: proposed for Phase 0 approval; implementation evidence does not yet exist.

| ID | Decision | Rationale and consequence |
| --- | --- | --- |
| ADR-001 | Modular monolith with separate API/worker processes | Keeps transactions and development manageable while demonstrating asynchronous processing. Shared database/codebase; no microservices. |
| ADR-002 | PostgreSQL source of truth, transactional outbox | Prevents business commit/event publication gaps. Requires publisher, retention and reconciliation; Redis success alone is insufficient. |
| ADR-003 | Redis Streams groups and at-least-once delivery | Supports pending recovery. PostgreSQL receipts protect derived effects; no exactly-once delivery claim. |
| ADR-004 | Preserve MVP outbox/receipts; durable quarantine | Makes Redis-loss replay and failed-event diagnosis possible. Storage growth needs monitoring and a later retention policy. |
| ADR-005 | Versioned resulting-state events | Handles out-of-order state changes. Shared per-user/movie revision locking is required for ratings and collection mutations. |
| ADR-006 | Explicit ratings only for collaborative math | Avoids inventing preference scores from clicks. Sparse data uses popularity/cold-start fallbacks. |
| ADR-007 | Centered cosine, Top-K and weighted predictions | Simple inspectable collaborative filtering. Bounded batch runs and benchmarks are necessary; no deep learning or factorization. |
| ADR-008 | Separate methods in ranking, no artificial blended score | Predictions and popularity have distinct evidence. API exposes provenance, null scores where unsupported, and deterministic fallback. |
| ADR-009 | Stored run snapshots and atomic activation | Fast reads and safe failed-run handling. Personalization is eventually fresh; current eligibility is checked synchronously. |
| ADR-010 | Same-origin UI, memory access token and rotating cookie refresh | Reduces persistent token exposure. Requires CSRF controls, session checks and cross-tab refresh coordination. |
| ADR-011 | Soft deactivation and suspension | Preserves history, foreign keys and auditability. Public-release deletion/retention policy remains unresolved. |
| ADR-012 | Compose single-host MVP | Reproducible graduation demonstration using approved stack. No high availability claim; backups must be outside the host. |
| ADR-013 | Synchronous personal statistics initially | Source queries provide immediate correctness. Async analytics demonstrate projections without making user lists depend on worker availability. |
| ADR-014 | Durable scheduled/admin jobs, no broker outside Redis Streams | PostgreSQL job leases prevent duplicate active generation and allow restart recovery. Avoid adding Celery or other infrastructure. |

## Open decisions and risk register

| Item | Proposed handling / decision gate |
| --- | --- |
| Catalog source and licensing | Manual admin entry for MVP; approve seed/poster provenance before import. No external API dependency yet. |
| Host capacity and CF runtime | Confirm hardware and benchmark before accepting numerical scale/freshness targets. Lower evaluation scale transparently if needed; never fabricate results. |
| Public release policy | Decide account deletion, telemetry/audit retention, privacy notice and backup erasure obligations before public deployment. |
| Password hashing and ingress packages | Select maintained Argon2id library and TLS/static ingress implementation in dependency setup, explain additions and pin compatible versions. |
| Dataset quality | Document rating sparsity, temporal split sizes and fallback coverage; no guarantee collaborative filtering beats popularity. |
| Outbox growth and backup volume | Monitor disk; design retention only after replay and group completion requirements are proven. |
| Notification/email features | Deferred; MVP has no email-based account recovery. State this limitation in login help. |

Changes to approved decisions require a dated amendment describing the trigger, alternatives, migration impact and validation. Approval of Phase 0 does not approve implementation of future-scope features.

## Phase 1 amendments — 2026-11-15

- Foundation only: four Compose services and no business schema/workers. The Phase 1 instruction authorizes implementation of the foundation described by the blueprint.
- Health contract: canonical `/health` plus `/health/live` alias; readiness requires both PostgreSQL and Redis for the requested foundation connectivity verification. Redis-degraded operation/schema checks remain future work. Verified through failure tests and live integration.
- Nginx is selected as an ancillary compiled-SPA server and same-origin proxy; Vite provides the equivalent proxy locally. This avoids browser-facing Docker hostnames and environment-dependent frontend builds. Verified by browser tests and HTTP smoke checks.
- psycopg 3 supplies SQLAlchemy's PostgreSQL driver; pydantic-settings handles environment validation. These support approved stack components rather than introducing new application architecture.
- Python dependencies are pinned in requirements.lock and frontend dependencies in package-lock.json. Host Python 3.10 and Docker Python 3.12 were both exercised. Test tooling remains in the foundation image for verification; production dependency separation is future hardening.
