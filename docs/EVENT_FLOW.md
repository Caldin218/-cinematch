# Event processing status

Phase 1 provides Redis connectivity only. No streams, outbox tables, workers, publishing or acknowledgement logic exists yet. ARCHITECTURE.md defines the proposed transactional lifecycle, retries, pending recovery and quarantine. Future phases must implement and verify these contracts; a Redis PING is not event durability evidence.
