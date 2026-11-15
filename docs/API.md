# Implemented API

Health: GET /health (alias /health/live) returns {status:ok,checks:{}} independently of dependencies. GET /health/ready returns 200 ready or 503 not_ready with PostgreSQL/Redis checks. Versioned aliases exist under /api/v1. OpenAPI is available at /docs and /openapi.json. The frontend health proxy strips /api before forwarding.

Phase 3 conventions: success uses {data:...}, pagination {items,page,page_size,total}, health retains {status,checks}. Errors use code/message/details/request_id. X-Request-ID accepts a UUID or generates one; validation errors omit raw input. Pagination bounds: page>=1, page_size 1-100.

## Phase 4 authentication

| Route | JSON request | Success |
| --- | --- | --- |
| POST /api/v1/auth/register | email, password (12-128 characters), display_name (trimmed 1-100) | 201 data: id/email/display_name/role, always USER |
| POST /api/v1/auth/login | email, password | 200 data: access_token/refresh_token/token_type/expires_in |
| POST /api/v1/auth/refresh | refresh_token | 200 same token response with rotated refresh token |
| POST /api/v1/auth/logout | refresh_token | 204, idempotent family revocation |
| GET /api/v1/users/me | Authorization: Bearer <access_token> | 200 data: id/email/display_name/role |

Email is validated and normalized to lowercase. Extra fields, including caller-selected role, are rejected. Duplicate email returns 409 email_exists. Wrong/unknown credentials and suspended accounts return generic 401 invalid_credentials. Invalid/expired tokens return 401. Reusing a consumed refresh token returns 401 refresh_reuse and commits family revocation before the error. Missing/weak/placeholder signing configuration returns 503 auth_unavailable for token issuance. Sensitive password/token hashes are never serialized.

Passwords use Argon2id (64 MiB, 3 iterations, parallelism 2) in a threadpool. HS256 JWTs require issuer/audience/sub/sid/jti/iat/exp, a fixed permitted algorithm and a default 15-minute lifetime. Every protected request queries current PostgreSQL user status/role and a live unrevoked token family; stale JWT role claims never authorize requests. Logout, reuse revocation and suspension invalidate subsequent access checks.

Refresh tokens are random 48-byte opaque values transmitted in JSON bodies, NOT cookies. Only SHA-256 hashes are stored, including consumed hashes for replay detection. Cookie flags and cookie CSRF flows do not apply. Use HTTPS outside local development, keep tokens in client memory, never put them in URLs or localStorage, and redact auth bodies/Authorization in proxies/monitoring. Memory-only clients must sign in after page reload; no frontend auth UI/storage is implemented here. Token responses and /users/me use Cache-Control:no-store; token responses also use Pragma:no-cache.

Rotation locks the owning user row, reloads the token, marks it consumed and inserts a successor in one commit. Successors retain the original absolute 7-day expiry. Reuse revokes the family and commits even though the request returns 401. Concurrent duplicates are strict: one can succeed, but the second revokes the family; clients must coordinate refresh. Logout accepts consumed tokens to revoke their family. Other login families remain valid. Expired/revoked tokens cannot rotate. No cleanup removes consumed hashes yet.

Redis Lua INCR+EXPIRE limiting is atomic and fail-closed: login 5 attempts/60 seconds independently per account and peer IP; registration 3/hour; refresh/logout 30/minute per peer IP. All attempts count, including successes. Exceeding a bucket returns 429 rate_limited. Redis failure returns 503 before auth mutation. Keys hash identities under cinematch:auth:. Forwarding headers are not trusted. Current Nginx clients share its peer IP, making limits conservative across clients; trusted proxy-aware client IP handling remains deployment work.

require_admin is the reusable dependency for future admin routers: anonymous 401, USER 403, active ADMIN allowed. Tests mount an isolated admin probe; no admin/catalog business endpoint is invented. ADMIN provisioning remains an operator responsibility, unavailable through public registration.

Configuration: JWT_SECRET (random >=32 bytes), JWT_ISSUER (cinematch), JWT_AUDIENCE (cinematch-api), ACCESS_TOKEN_MINUTES (15), REFRESH_TOKEN_DAYS (7). A random local signing key was generated in ignored .env without printing it. The example placeholder is rejected. Restart processes after key changes; old JWTs cease validating. No schema migration is required.

References: [Argon2 API](https://argon2-cffi.readthedocs.io/en/stable/api.html), [PyJWT validation](https://pyjwt.readthedocs.io/en/stable/usage.html). Password recovery, email delivery and browser login screens remain future features.


## Phase 5 movie catalog

Public reads require no token. Admin mutations require a live ADMIN bearer token (anonymous 401, USER 403).

| Method /api/v1 route | Request | Response |
| --- | --- | --- |
| GET /movies | catalog query parameters below | 200 data: {items,page,page_size,total} |
| GET /movies/search | same query parameters; static route precedes movie ID | same page envelope |
| GET /movies/{movie_id} | positive signed BIGINT | 200 data: movie; absent/inactive 404 |
| GET /genres | none | 200 data: [{id,name}] |
| POST /admin/movies | title; optional synopsis, release_year, runtime_minutes, poster_url, genre_ids | 201 data: movie |
| PATCH /admin/movies/{movie_id} | nonempty subset of creation fields | 200 data: movie |
| DELETE /admin/movies/{movie_id} | none | 204 soft deletion; absent/inactive 404 |
| POST /admin/genres | name | 201 data: genre |
| PATCH /admin/genres/{genre_id} | name | 200 data: genre |
| DELETE /admin/genres/{genre_id} | none | 204; assigned genre 409; missing 404 |

Query parameters: `q` is a trimmed, case-insensitive title **prefix**, 1-255 characters; `%`, `_` and backslash are literal characters. `genre_id` is one positive BIGINT, `release_year` is 1888-9999, `min_rating`/`max_rating` are inclusive 0-5 bounds on average rating. Both rating bounds exclude unrated movies; min must not exceed max. Unknown genre filters yield an empty page. `sort` is popularity (default), rating or release_year, always descending with nulls last and ascending ID ties. `page` is 1-1,000,000 (bounded to prevent oversized OFFSET values); `page_size` defaults to 20, maximum 100. Pages beyond the end are empty and retain total. Search without q is equivalent to listing. Examples: `/api/v1/movies/search?q=alien&genre_id=2&min_rating=3&sort=rating&page_size=10`.

Movie output: id, title, synopsis, release_year, runtime_minutes, poster_url, version, genres, average_rating (null if unrated), rating_count, popularity. Rating is the mean of actual stored 1-5 ratings; popularity is recorded movie-view count, zero for unseen movies. These are catalog aggregates, not recommendation predictions. GET does not record a view. Interaction writes belong to later phases.

Titles are trimmed 1-255 characters, synopsis at most 20,000, runtime positive signed INTEGER, poster_url HTTP/HTTPS, genre_ids at most 100 distinct existing positive BIGINTs. Unknown body fields are rejected. PATCH omission preserves fields; null clears nullable fields; title and genre_ids cannot be null. An empty genre_ids removes associations. Invalid input/IDs return 422; valid missing IDs return 404. Genre names are trimmed 1-80 characters, unique ignoring case (409 on duplicate). Deleting an assigned genre returns 409, including associations to soft-deleted movies. Soft deletion preserves historical references and hides movies from all public reads; no restore API in this phase.

Movie mutations lock the row, increment version on update/delete and commit an outbox event in the same PostgreSQL transaction. Events movie.created/movie.updated/movie.deleted have schema_version=1, aggregate_type=movie, aggregate_id and aggregate_version; payload {movie_id,version}. Consumers must re-read PostgreSQL; delivery workers are not implemented in Phase 5.

Genres use Redis cache-aside, 60-second TTL, database-scoped key `cinematch:genres:v1:<database>`, invalidated after genre mutation. Cache payloads are validated; malformed values and Redis failure fall back to PostgreSQL and emit safe warning logs. A failed invalidation or concurrent read-fill can leave genre names stale for at most the TTL after fill; movie reads always use PostgreSQL. Successful database commits are not reported as failed solely because cache invalidation fails. No dynamic catalog page caching is used.
