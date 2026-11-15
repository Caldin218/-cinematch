# Recommendation status

Phase 2 adds the recommendations SQLAlchemy model and table only. It stores a current set per user, atomically replaced in a future service transaction. Unique user/movie and user/rank constraints prevent duplicate candidates/ranks. Distinct nullable predicted_rating/popularity_score columns preserve provenance, and catalog fallback has no numeric score. See DATABASE.md for the replacement protocol and checks.

No algorithm, generated recommendations, learning model, batch job or API exists yet. Numeric values in database tests are explicit fixtures, not system-generated recommendation evidence. ARCHITECTURE.md defines planned popularity, centered user-based cosine similarity, Top-K, weighted predictions, cold-start fallback and evaluation. Earlier snapshot-run/history tables are deferred in favor of the Phase 2 replacement strategy.

Phase 6 rating input now uses exact 0.50-5.00 decimals (up to two places), replacing the integer baseline. Future prediction/rating-derived popularity bounds are [0.5,5]; migration 0002 aligns stored score checks. View history, favorites and watchlist are actual source data; they must not be converted into invented explicit ratings. No recommender is implemented in this phase.
