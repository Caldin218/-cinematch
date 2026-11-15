# Event flow

PostgreSQL remains the source of truth. Delivery is at least once; exactly-once delivery is not claimed.

The envelope contains event_id, event_type, aggregate_id, user_id, payload, occurred_at, schema_version and correlation_id. UUIDs identify events/users/correlations; catalog user_id is null. Version 1 requires an actual integer. Payloads reject unknown fields and invalid identities. Producers validate before committing business changes and outbox rows together.

Required events: movie.viewed, movie.rated (create/update), movie.favorite_added and movie.favorite_removed. Existing catalog and watchlist events remain supported. Interaction aggregates identify users. Routing invalidates persisted recommendations within the receipt transaction.

```mermaid
sequenceDiagram
    participant API
    participant PG as PostgreSQL
    participant P as Publisher
    participant R as Redis Streams
    participant C as Consumer
    API->>PG: BEGIN; business data + validated outbox
    API->>PG: COMMIT
    P->>PG: Lock committed pending row, SKIP LOCKED
    P->>R: XADD envelope
    R-->>P: Entry ID
    P->>PG: Mark published; COMMIT
    C->>R: XREADGROUP
    R-->>C: Envelope
    C->>PG: Verify source; receipt + handler effects; COMMIT
    C->>R: XACK
```

```mermaid
sequenceDiagram
    participant P as Publisher
    participant PG as PostgreSQL
    participant R as Redis
    participant C as Consumer
    P->>R: XADD
    R-->>P: Confirm
    Note over P: Crash before marking published
    PG->>PG: Release lock; row stays pending
    P->>R: Restart; duplicate XADD with same event_id
    C->>PG: Receipt and effects commit
    Note over C: Crash before ACK
    C->>R: XAUTOCLAIM after idle timeout
    C->>PG: Receipt conflict; skip effects
    C->>R: XACK
```

From backend, migrate with `alembic upgrade head`, then launch independent supervised processes:

```sh
python -m app.events.worker publisher
python -m app.events.worker consumer --group recommendations-v1 --name worker-1
python -m app.events.worker consumer --group recommendations-v1 --name worker-2
```

One group divides work across consumers. Other groups receive independent copies and receipts. SIGINT/SIGTERM stop admission, finish the current transaction and close clients. Unprocessed batch entries remain recoverable. Database and Redis timeouts bound routine waits; strict shutdown latency is not guaranteed.

Publisher Redis failures leave rows pending with exponential delay capped at 300 seconds. Transactions hold a row lock during XADD; measure database pool occupancy before scaling. Ambiguous timeouts can duplicate publication. Aggregate delivery order is not guaranteed.

Monitor oldest pending outbox age, publish_attempts/last_error, worker metrics and the dead-letter stream. Consumer failure handling is specified below; publisher validation failures remain retained in the outbox for operator repair.

## Redis-loss recovery

XADD confirmation does not guarantee survival of later Redis persistence loss. Retain PostgreSQL outbox rows and processed receipts. After restoring Redis, identify affected committed event IDs in PostgreSQL and replay each:

```sh
python -m app.events.worker replay --event-id <UUID>
```

Replay validates the retained source, preserves event_id and publication history, and requires a confirmed XADD. Retry on failure. Normal consumer polling recreates a lost group. Existing receipts skip completed effects; use a new group only for an intentional rebuild. This is operator recovery, not automatic loss detection. Restore PostgreSQL backups first if PostgreSQL was also lost.

No automatic stream trimming exists. Reconcile every required group before retention changes; receipt foreign keys restrict outbox deletion. External handler effects require their own idempotency or transactional outbox. Memory growth and poison-message operations remain explicit limitations.

Compose supervision: run `docker compose --profile workers up -d outbox-publisher event-consumer` after migrations. Both inherit backend configuration and restart policy; scale event-consumer for additional group members. Consumer healthchecks query the internal HTTP health endpoint; the publisher still uses process/backlog monitoring.


## Phase 8 consumer reliability

Redis 7+ is required. Groups are created at 0-0 with MKSTREAM; BUSYGROUP is accepted and NOGROUP errors trigger recreation on the next poll. Never delete a group to clear errors. XREADGROUP admits one message at a time. Each poll scans a bounded portion of the PEL using a persistent XAUTOCLAIM cursor before reading new work. Reclaimed work observes durable per-entry retry deadlines. With the default 60-second idle threshold, actual retries may occur later than their backoff deadline.

The processed_events primary key is (consumer_group, event_id): event identity is unique within a handler group, while independent groups can each handle an event. Receipt insertion and PostgreSQL handler effects share one transaction. Concurrent duplicates wait on that unique constraint and skip already committed effects. ACK follows COMMIT, including duplicate deliveries. Ownership-checked Lua ACK prevents a stale owner acknowledging a replacement consumer's work. No schema migration is necessary.

A heartbeat every idle-timeout/3 renews the active entry using ownership-checked XCLAIM JUSTID. A crashed worker loses its heartbeat and its pending entry becomes reclaimable. Only the current message is admitted, avoiding an idle prefetched batch. If Redis fails and another consumer claims work, PostgreSQL receipt uniqueness still protects database effects. Handlers must use only the supplied session; external effects require their own outbox/idempotency. Do not configure an idle timeout shorter than ordinary scheduler/network delays. The CLI uses statement/lock timeouts of 10/5 seconds; it does not promise a hard timeout for arbitrary Python handlers.

### Failure policy

| Failure | Action |
| --- | --- |
| Invalid JSON/envelope, unsupported event route, missing/mismatched PostgreSQL source | Immediate dead-letter transfer; preserve original fields and reason |
| Handler exception / commit failure other than infrastructure failure | Roll back; retry with exponential backoff; quarantine after retry budget |
| PostgreSQL OperationalError/InterfaceError (outage, timeout, disconnect) | Roll back; retain pending; exponential backoff without spending handler retry budget |
| Redis unavailable, ACK or quarantine confirmation lost | Retain/recover pending; retry when Redis returns; committed receipts suppress duplicate effects |
| Duplicate event | Skip effects on receipt conflict, commit then ACK |
| Worker crash / restart | Reclaim stale PEL; uncommitted PostgreSQL work rolls back |
| Long-running event | Renew PEL idle time while executing; competing committed effects remain deduplicated |
| Retry exhaustion | Atomic XADD to dead stream followed by XACK and retry-state deletion |

WORKER_MAX_RETRIES defaults to 5 retries after the initial attempt (6 total handler failures). WORKER_RETRY_BASE_SECONDS=2 and WORKER_RETRY_MAX_SECONDS=300 yield min(cap, base * 2^(failure-1)). Infrastructure failures use a separate durable backoff counter. Crash attempts cannot be counted reliably as handler failures and do not spend the handler budget. Retry state lives in `<stream>:retry:<group>:<entry-id>` until ACK/quarantine; no TTL discards it. Redis persistence loss requires the outbox replay recovery above. Publisher retries remain independently unbounded and capped at 300 seconds.

Dead letters live in `<stream>:dead`, shared across groups with source_stream, source_group, source_id, consumer, reason, failures and original fields. Lua checks PEL ownership, appends evidence, then ACKs atomically; a failed XADD does not ACK. No stream trimming or dead-letter deletion runs automatically. This implementation targets the existing standalone Redis deployment; multi-key scripts are not Redis Cluster compatible.

### Health and metrics

Consumers expose GET /health and /metrics on WORKER_HEALTH_PORT (default 9101, internal container port). /health returns 503 until a successful poll and while the last processing/dependency failure remains unresolved; successful processing clears the error. Signals stop new admission, finish current work and close HTTP, Redis and database resources. A forced kill leaves recoverable PEL entries. Health endpoints are internal and unauthenticated; do not expose them publicly.

/metrics emits Prometheus text: processed_total (successful committed deliveries including duplicates), failed_total (failed processing attempts), retried_total (attempts with recorded handler or infrastructure failures), pending_messages (group PEL size), processing_duration (cumulative wall seconds across batch admission/processing), consumer_lag (Redis group lag, omitted when unknown). Counters are per process and reset on restart; pending/lag gauges are refreshed after polls. Scrape each worker separately. A successful poll with no work does not clear an earlier processing failure. Publisher metrics are outside this consumer interface.

### Recovery runbook

1. Check /health, /metrics, logs, XPENDING and XINFO GROUPS. Restore database/Redis connectivity first. Infrastructure outages must not be fixed by ACKing or deleting pending entries.
2. After worker crash, restart the same group with a fresh consumer name. Wait for the idle threshold plus retry deadline and cursor scan. Confirm pending count and lag drain. Keep inactive consumer records until their PEL is empty before XGROUP DELCONSUMER.
3. Inspect `<stream>:dead` with XRANGE. Original fields can contain user data; restrict operator access. Correct the producer/source or deploy the handler fix. Replay a valid retained outbox event with `python -m app.events.worker replay --event-id <UUID>`. Replay preserves event identity and committed receipts; it does not undo prior effects. Verify receipt/ACK before manually retiring dead-letter evidence. Malformed events without a valid source require operator investigation and a corrected transactional producer event.
4. If Redis data or pending stream entries were deleted, restore Redis then replay affected PostgreSQL outbox IDs. Missing PEL entries emit an error and unhealthy status; operators must reconcile retained outbox rows. Do not trim live streams without reconciling every group.
5. For shutdown, send SIGTERM and allow at least the configured Compose 30-second grace period. Investigate handlers exceeding database bounds; forced termination is recovered through the PEL and transactional receipts.

Failure-injection integration tests use disposable migrated PostgreSQL databases and isolated Redis stream names: `$env:RUN_INTEGRATION='1'; backend/.venv/Scripts/python -m pytest -q backend/tests/test_events.py` from the repository root. They inject handler/commit/ACK failures, Redis and PostgreSQL unavailability, restart, duplicate delivery, long-running handlers, backoff and retry exhaustion. Services themselves are not stopped and configured application data is not modified.
# Phase 10 recommendation scheduling

Interaction routes now coalesce the actor's durable recommendation job instead of
deleting persisted results. Catalog events schedule all active users. Job upserts
and event receipts commit together before ACK. The separate `recommendations`
worker calculates and atomically persists results. Lease token/revision fencing
rejects superseded work. Cache revision checks provide logical invalidation when
Redis cannot delete keys. Manual refresh uses the same PostgreSQL scheduling path
without Redis Streams. See RECOMMENDATION.md for batching, failures and freshness.
