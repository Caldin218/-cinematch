# Event processing status

Phase 2 adds outbox_events and processed_events models/tables. Outbox UUIDs identify original events; processed receipts are unique per consumer_group/event_id and reference retained outbox rows with ON DELETE RESTRICT. Database tests verify business/outbox rollback and receipt/effect rollback, retry and duplicate receipt behavior. See DATABASE.md for fields and indexes.

No streams, workers, publishing, retries, pending recovery or Redis acknowledgement logic exists yet. Future services must insert business state and outbox atomically; consumers must commit their receipt/effects before acknowledgement. The schema alone does not guarantee event delivery. ARCHITECTURE.md retains the intended lifecycle/recovery design. No exactly-once delivery claim is made.

Phase 5: movie create/update/soft-delete services now append movie.created/movie.updated/movie.deleted to outbox_events in the same transaction as catalog state. Aggregate version increases under a movie row lock, and payload contains movie_id/version. These records remain pending until a later phase implements the publisher. Genre administration currently has no downstream asynchronous event contract.
