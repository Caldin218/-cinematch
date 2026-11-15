# Phase 7 Quality Audit

Date: 2026-11-15. Verdict: **FAIL — Phase 7 is incomplete.**

Review scope: `backend/app/events/*`, event models, migration 0003, interaction and catalog producers, database/Redis/config/correlation support, test suite, Docker Compose and event documentation. Existing Phase 6 work was preserved. This audit changes documentation only.

## Critical issues

No independently confirmed critical security vulnerability was identified. Reliability acceptance remains blocked by the high-priority findings below; this is not a production certification.

## High-priority issues

1. **Required delivery tests are missing.** No tests exercise OutboxPublisher or EventConsumer. Successful XADD, publisher restart, ambiguous XADD timeout, duplicate publication, Redis outage, handler/receipt atomicity, ACK failure, pending recovery, schema rejection and multiple competing consumers remain unverified. Existing database receipt tests do not exercise these workers. Add real PostgreSQL/Redis tests plus deterministic crash/failure injection before accepting delivery guarantees.
2. **Redis data loss has no replay mechanism.** `publisher.py` permanently excludes published rows. If Redis loses a confirmed entry before consumption (including persistence loss), the event remains published in PostgreSQL but never reaches its handler. Retaining PostgreSQL rows preserves recovery material, but an explicit replay/reconciliation procedure is missing. Document the durability boundary and implement/test an operator-controlled recovery path.
3. **Event-flow requirement is unmet.** `docs/EVENT_FLOW.md` still says streams and workers do not exist, lists the old interaction event names, and contains no required Mermaid sequence diagrams. It lacks startup, restart, duplicate delivery, shutdown and recovery instructions.
4. **Migration regression test is stale.** `test_interaction_migration.py` asserts revision `0002_interactions` after upgrading to head. Head is now 0003. Its downgrade-failure assertions need review against the new migration boundary; this is a static finding, not a successfully reproduced assertion failure.

## Medium-priority issues

1. **Type safety is weak.** Worker constructors, session/Redis dependencies, handler signatures, return values and envelope conversion lack annotations; `payload: dict` loses the validated payload type. Handlers index the original untyped dictionary. Define typed dependencies and a handler protocol; retain validated payloads where practical.
2. **Poison events retry indefinitely.** Invalid outbox rows get repeated retries, while invalid stream entries remain pending forever. There is no quarantine, bounded retry policy, structured diagnostic detail or operational backlog monitoring. Preserve evidence while providing an explicit remediation path.
3. **Database transactions span Redis calls.** Publisher row locks and a pooled PostgreSQL connection remain held during XADD. Socket timeouts bound ordinary waits, but Redis outages reduce publisher throughput and increase connection occupancy. Benchmark concurrency and outage behavior before scaling.
4. **Schema validation is delayed until publication.** Producers construct OutboxEvent directly; bad producer payloads can commit successfully and become permanently unpublishable. Validate the envelope/payload contract within the business transaction and test rollback on invalid payloads.
5. **Deployment integration is absent.** Compose defines no publisher/consumer services. The CLI can run independently, but existing deployment starts neither worker. Add documented explicit launch instructions and process supervision configuration.
6. **Schema-version coercion needs a test.** `Literal[1]` is not an explicit strict integer boundary. Test booleans/numeric coercions and catalog user identity semantics. Extra fields, event names, aware timestamps and payload identity are otherwise checked.
7. **Recovery concurrency is untested.** XAUTOCLAIM can move work between consumers; receipt uniqueness appears to serialize database effects, but timeout/reclaim interactions and shutdown mid-batch require real tests.

## Low-priority improvements

- Remove or explain unused lease_expires_at now that publisher coordination uses row locks.
- Separate schema registration from default handler routing: HANDLERS automatically assigns every schema a recommendation invalidation handler, coupling contract extension to business behavior.
- Consider a shared producer event factory to avoid duplicated correlation-ID construction and centralize contract validation.
- Avoid XGROUP CREATE on every poll after successful initialization; recreate only on missing-group recovery.
- Add backlog, retry, processing-latency and missing-pending-entry metrics. Current exception-class-only logging protects payloads but limits diagnosis.

## Passing criteria

Static review supports these properties; worker behavior still requires integration validation:

- Business state and outbox insertion share PostgreSQL transactions.
- Publisher reads committed outbox rows with FOR UPDATE SKIP LOCKED.
- published_at is assigned only after XADD returns an entry ID.
- A crash before the publication-mark commit leaves the row eligible for retry; duplicate publication is possible.
- Consumer receipt insertion and PostgreSQL handler effects share a transaction, with uniqueness by consumer_group/event_id.
- XACK follows the database transaction; duplicate receipts skip handlers.
- Consumers compare incoming envelopes against PostgreSQL source rows.
- SIGINT/SIGTERM stop further work, with final Redis/engine cleanup; shutdown has not been exercised.
- No exactly-once delivery claim is made. PostgreSQL remains authoritative.

## Failing / unverified criteria

Required publisher success/restart/outage/duplicate tests, worker schema tests, multiple consumers, actual shutdown tests, migration regression verification, operational replay and required Mermaid documentation are missing or unverified. Phase completion is rejected.

## Executed checks

| Check | Observed result |
| --- | --- |
| Default backend pytest | 11 passed, 90 skipped; one Starlette/httpx deprecation warning |
| Integration run with RUN_INTEGRATION=1 | Setup errors connecting to localhost:55432; bounded interaction run stopped at first error with psycopg ConnectionTimeout |
| Full integration retry outside sandbox | Also began producing setup errors; no passing integration result claimed |
| Frontend npm run build | Passed: tsc -b and Vite production build, 146 modules transformed |
| Ruff | Could not run: No module named ruff |
| mypy | Could not run: No module named mypy |
| Lint/type configuration inspection | No backend lint/type tools configured in pyproject; frontend has no lint script |
| git diff --check | Passed; only LF/CRLF normalization warnings |

Frontend browser tests were not run: Phase 7 introduces no frontend behavior. No dependency vulnerability scan was performed. Security conclusions are limited to inspected source: SQLAlchemy statements use bound values, consumer source verification prevents arbitrary envelope substitution, and worker logs avoid raw payloads/secrets. PostgreSQL/Redis credentials and network deployment were not penetration-tested.

## Remediation status

The subsequent fix pass adds required regression coverage, strict version checks, validation before producer commits, explicit replay, worker supervision and rewritten EVENT_FLOW documentation. The original findings above are retained as audit history. Actual post-fix execution results and remaining limitations are recorded in DEVELOPMENT_PROGRESS.md; do not interpret the original environment failures as final post-fix test outcomes.
