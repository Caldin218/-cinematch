# Event processing status

Phase 2 adds outbox_events and processed_events models/tables. Outbox UUIDs identify original events; processed receipts are unique per consumer_group/event_id and reference retained outbox rows with ON DELETE RESTRICT. Database tests verify business/outbox rollback and receipt/effect rollback, retry and duplicate receipt behavior. See DATABASE.md for fields and indexes.

No streams, workers, publishing, retries, pending recovery or Redis acknowledgement logic exists yet. Future services must insert business state and outbox atomically; consumers must commit their receipt/effects before acknowledgement. The schema alone does not guarantee event delivery. ARCHITECTURE.md retains the intended lifecycle/recovery design. No exactly-once delivery claim is made.
