# Recommendation status

Phase 2 adds the recommendations SQLAlchemy model and table only. It stores a current set per user, atomically replaced in a future service transaction. Unique user/movie and user/rank constraints prevent duplicate candidates/ranks. Distinct nullable predicted_rating/popularity_score columns preserve provenance, and catalog fallback has no numeric score. See DATABASE.md for the replacement protocol and checks.

No algorithm, generated recommendations, learning model, batch job or API exists yet. Numeric values in database tests are explicit fixtures, not system-generated recommendation evidence. ARCHITECTURE.md defines planned popularity, centered user-based cosine similarity, Top-K, weighted predictions, cold-start fallback and evaluation. Earlier snapshot-run/history tables are deferred in favor of the Phase 2 replacement strategy.

Phase 6 rating input now uses exact 0.50-5.00 decimals (up to two places), replacing the integer baseline. Future prediction/rating-derived popularity bounds are [0.5,5]; migration 0002 aligns stored score checks. View history, favorites and watchlist are actual source data; they must not be converted into invented explicit ratings. No recommender is implemented in this phase.


## Phase 9 — implemented engine (2026-11-15)

Implementation: `backend/app/recommendation_engine/`. This section supersedes earlier
planned algorithm descriptions. No training framework or additional dependency is required:
sparse dictionaries represent observed ratings without zero-filling missing values.
Explicit ratings alone drive CF; views are never converted into ratings.

### Algorithms and score meanings

Popularity uses a Bayesian estimate `B_i = (sum_ratings_i + m * global_mean) / (count_i + m)`.
The prior strength `m` defaults to 20 pseudo-ratings. This shrinks small samples toward
the training mean; it cannot guarantee that a single highly rated movie never ranks first.
Normalize `B_i` using configured rating bounds, then blend with
`log(1 + views_i) / log(1 + max_views)` using `view_weight` (default 0.1).
With no views, the view term is zero. With no ratings, the prior is the scale midpoint.
Unrated catalog movies therefore remain eligible for popularity; tied scores use movie ID.
Popularity is a [0,1] ranking score, not a predicted rating or the existing database
`popularity_score` field, which has a different rating-scale contract.

Similarity uses cosine of deviations from each user's training mean, restricted to
co-rated items. At least two overlaps are required by default. Multiply cosine by
`overlap / (overlap + shrinkage)` (default shrinkage 10) to reduce sparse overlap confidence.
Constant profiles and zero norms return zero. Only positive similarities qualify.
Choose the global Top-K neighbors (default 30), then predict a candidate as
`user_mean + sum(similarity * (neighbor_rating - neighbor_mean)) / sum(similarity)`
over neighbors who rated that movie. Clamp predictions to the configured rating bounds.
Negative neighbors are deliberately ignored. Missing candidate ratings are not imputed.
`UserBasedCF.recommend` returns only supported CF predictions, sorted descending.

Hybrid uses `cf_weight * normalized_prediction + popularity_weight * popularity`,
divided by the sum of weights. Default weights are 0.7 and 0.3. CF is normalized
with the rating scale, rather than candidate-dependent min/max values. Unsupported
candidates use their popularity score directly. Scores from these two paths are
comparable in range, but are not calibrated probabilities. The result method and
component scores expose which path was used. Already-rated movies are always excluded.

### Configuration, data ownership and cold starts

Pass a validated `EngineConfig` to `Snapshot`, then construct `RecommendationEngine`.
All thresholds, bounds, prior strength, shrinkage, neighbor count, and hybrid weights
are configurable constructor parameters. Application environment mapping is left to
Phase 10; this phase does not add routes, jobs, Redis caching or persistence.

```python
from app.recommendation_engine import EngineConfig, Rating, Snapshot, RecommendationEngine

snapshot = Snapshot([Rating("user", 1, 4.0)], movie_ids=[1, 2, 3],
                    config=EngineConfig(neighbors=20, prior_count=30))
results = RecommendationEngine(snapshot).recommend("user", n=10)
```

Users with fewer than three ratings, unseen users, zero-similarity users and users
without candidate-rating neighbors fall back to popularity. Movies with fewer than
three ratings are excluded from CF predictions; they may appear through popularity.
Empty catalogs produce empty lists. Nonnegative N is required; N=0 returns no results.
Duplicate user/item observations, nonfinite/out-of-range ratings and negative views
are rejected. Nested rating indexes are read-only.

`loading.py` provides MovieLens and async SQLAlchemy adapters; algorithms contain no SQL
or API dependencies. The database adapter includes active movies and their ratings/views.
Its caller must use a single REPEATABLE READ transaction to obtain a consistent snapshot.
Historical evaluation must use the offline train-only adapter: current database ratings
are updated in place and cannot reconstruct historical rating revisions.

Reuse the engine for a snapshot: an inverted item index finds potential neighbors,
and sorted Top-K neighbors are computed lazily and cached per queried user. There is
no dense full similarity matrix. Replace the entire snapshot and engine after data
changes; there is no incremental cache invalidation or automatic refresh yet.
Memory is O(observed ratings + queried users * K + catalog). Worst-case neighbor work
still grows with overlapping users; this is intended for modest datasets, not web-scale serving.

### MovieLens 100K and evaluation

Download and unpack MovieLens 100K locally from
[GroupLens](https://grouplens.org/datasets/movielens/100k/).
The official [README](https://files.grouplens.org/datasets/movielens/ml-100k-README.txt)
defines 100,000 ratings, 943 users, 1,682 movies, 1–5 ratings and Unix timestamps.
Respect its usage and citation terms; the dataset is not committed or redistributed.
From `backend`, run:

```powershell
.\.venv\Scripts\python -m app.recommendation_engine.evaluation C:\datasets\ml-100k\u.data --k 10 --test-fraction 0.2
```

The CLI sets MovieLens's minimum rating to 1, while application defaults are 0.5–5.
A global chronological 80/20 split places every timestamp tie at the cutoff in test;
test size can exceed 20%. It prevents future interactions from other users leaking
into training. All means, counts, popularity, similarities and candidates use train
only. Held-out movies absent from train remain unavailable recommendations. Pair overlap
and nonchronological train/test inputs are rejected. For hyperparameter tuning, create
a separate chronological validation partition within train; never tune on final test.

MAE/RMSE report rating errors using CF where available and the training Bayesian rating
estimate otherwise. They do not treat hybrid ranking scores as ratings. CF-only errors
and CF coverage are reported separately to make fallback prevalence visible. Empty
error sets return null. Precision@K divides by K even for short recommendation lists;
Recall@K divides by held-out relevant items. Relevant means test rating >=4 by default.
Ranking metrics are macro averages over users with at least one relevant held-out item;
empty ranking populations yield zero with an explicit user count. Full train-catalog
ranking is used, without sampled negatives. Unknown test items remain in recall's
denominator. Observed ratings do not establish relevance for unobserved movies.

### Verification and limitations

Deterministic tests cover formulas, overlap shrinkage, positive/negative/constant profiles,
Top-K, cache reuse, popularity shrinkage/views, hybrid components, exclusions, cold starts,
empty inputs, validation, database adapter mapping, MovieLens parsing, metrics and leakage.
No model training is performed. Popularity favors established titles and can be manipulated
by repeated views. CF can have low coverage on sparse or cold profiles and ignores taste
changes, metadata and diversity. Snapshot replacement requires memory and rebuild work.
The MovieLens sample is old and filtered, so its results do not establish production quality.
Phase 10 adds the hybrid persistence contract described below.


Verified MovieLens run on 2026-11-15 (default parameters, K=10): 79,999 train ratings,
20,001 test ratings; 290 users with relevant held-out items. MAE 0.837879,
RMSE 1.041161; CF-only MAE 0.848547, RMSE 1.083149; CF coverage 0.124044.
Precision@10 0.172414, Recall@10 0.049412. Low CF coverage reflects the strict global
time split and cold users; this run does not prove hybrid superiority over popularity.
No tuning or baseline comparison was performed. Dataset downloaded to OS temporary
storage using PowerShell's certificate trust; Python urllib download failed certificate
validation on this host. No certificate checks were disabled.

## Phase 10 — event and API integration

Flow: committed interaction + outbox → publisher → Redis Stream → event consumer →
PostgreSQL job → calculation worker → PostgreSQL results → Redis cache-aside.
Stream receipts and job scheduling commit together before ACK. Duplicate event
delivery does not schedule twice for the same consumer group.

Interaction events schedule their actor; catalog changes schedule all active users.
Favorites/watchlists trigger recalculation without directly changing engine weights.
Other users' ratings influence the next snapshot; they do not eagerly fan out to
every user. Explicit refresh also schedules a job.

### Scheduling and failures

Jobs coalesce by user in a bounded batch window: the first event sets the deadline,
and further events increment the revision without extending the pending deadline.
Default `RECOMMENDATION_BATCH_SECONDS=5`; zero disables the wait. Continuous events
cannot indefinitely postpone the deadline. Refresh returns after scheduling and
optional cache invalidation. Calculations hold no scheduling row locks.

Workers claim due jobs with `FOR UPDATE SKIP LOCKED`, a UUID lease token and
`RECOMMENDATION_LEASE_SECONDS=300` expiry. Source queries use one REPEATABLE READ
snapshot. Completion checks both token ownership and input revision. Superseded
results are discarded, leaving work pending; expired workers cannot overwrite
replacement work. Superseded calculations wait for the next configured batch window,
preventing a tight recalculation loop under continuous interactions. Results and
metadata replace the previous generation atomically, including successful empty
generations. Errors preserve old results and retry
indefinitely with exponential delays (2–256 seconds). Only exception classes are
recorded. Lease expiry recovers crashes and failures during failure bookkeeping.

Migration `0004_recommendation_jobs` adds durable jobs, metadata, `ranking_score`
and the `hybrid` method. The engine's ranking score is [0,1]. For compatibility with
existing storage, `popularity_score` is `0.5 + 4.5 * engine_popularity_score` on
[0.5,5]; it is not a predicted rating. Hybrid rows retain both components. Version:
`hybrid-cf-popularity-v1`. `generation_seconds` measures snapshot loading and
calculation, excluding commit/cache I/O. `generated_at` and `source_cutoff` are UTC.
Internal `/metrics` exposes generated/failed/superseded totals and cumulative
generation seconds. Generation logs include duration and algorithm version.

### Cache and freshness

Keys: `recommendations:user:{user_id}`, TTL `RECOMMENDATION_CACHE_TTL=300`.
JSON validates schema version, owner, completed revision, timestamps, score bounds,
methods, finite duration, unique movies and contiguous ranks. Invalid/foreign/old
entries are deleted and loaded from PostgreSQL. Redis read/write/delete failures
fall back to PostgreSQL. Refresh and generation delete the key. Event scheduling
logically invalidates it by advancing the authoritative PostgreSQL revision; dirty
jobs bypass the cache. Delayed fills cannot hide newer generations because each
read checks the revision. Redis is not required for refresh or calculation.

Every response filters currently rated movies and inactive candidates in PostgreSQL,
including cache hits. Exclusions can shorten Top-N until recalculation. Optional
`n` is capped by `RECOMMENDATION_TOP_N` (default 10). Cold profiles use popularity.
Before the first generation, GET schedules work and returns deterministic unrated
catalog candidates with `status=unavailable`, a fallback explanation and null
generation timestamps. Pending jobs with prior results return `status=stale` and
their original metadata. Successful empty generations are `ready` with metadata.

Recommendations are eventually consistent. Under light load, expected freshness is
outbox/stream lag + up to 5 seconds batching + up to 0.5 seconds worker polling +
snapshot/calculation time. Stream receipt polling may add about a second. This is
not a latency guarantee: backlogs, supersession, failures or stopped workers extend
it. TTL adds no extra five-minute delay because revisions bypass obsolete entries.
`generated_at` describes the last completed generation, not the latest interaction.

Limits: full sparse snapshot loading per job; O(active users) catalog fanout. Set
the lease longer than normal calculation time to reduce duplicate work; fencing
still protects writes. No hard CPU timeout, periodic global rebuild, job retention
or autoscaling. Metrics reset on restart.
