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

Monitor oldest pending outbox age, publish_attempts/last_error, XPENDING age/count and worker error logs. Poison rows/entries remain retained for investigation and retry. Repair the producer or deploy a compatible handler before retrying. Automated quarantine/metrics are deferred; never delete evidence solely to clear a backlog.

## Redis-loss recovery

XADD confirmation does not guarantee survival of later Redis persistence loss. Retain PostgreSQL outbox rows and processed receipts. After restoring Redis, identify affected committed event IDs in PostgreSQL and replay each:

```sh
python -m app.events.worker replay --event-id <UUID>
```

Replay validates the retained source, preserves event_id and publication history, and requires a confirmed XADD. Retry on failure. Normal consumer polling recreates a lost group. Existing receipts skip completed effects; use a new group only for an intentional rebuild. This is operator recovery, not automatic loss detection. Restore PostgreSQL backups first if PostgreSQL was also lost.

No automatic stream trimming exists. Reconcile every required group before retention changes; receipt foreign keys restrict outbox deletion. External handler effects require their own idempotency or transactional outbox. Memory growth and poison-message operations remain explicit limitations.

Compose supervision: run `docker compose --profile workers up -d outbox-publisher event-consumer` after migrations. Both inherit backend configuration and restart policy; scale event-consumer for additional group members. Worker healthchecks are disabled; monitor process status and backlog.
