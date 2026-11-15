# CineMatch product definition

Status: proposed Phase 0 baseline, 2026-11-15; awaiting approval.

## Purpose and success

CineMatch helps people find movies, record their preferences, and receive explainable recommendations. The graduation demonstration must show that committed interactions survive publisher and worker failures, duplicate deliveries are safe, and recommendations derive from real stored data.

Success means users can complete the discovery-to-rating journey, administrators can maintain the catalog and inspect processing health, and recovery tests demonstrate at-least-once delivery without silently discarding committed events. Numerical targets in REQUIREMENTS.md are acceptance targets, not measured results.

## Audience and boundaries

USER is a registered movie explorer. ADMIN has catalog and operational responsibilities and retains ordinary user capabilities. Anonymous visitors may browse the active catalog; account-specific features require authentication. Registration always creates USER accounts. Initial ADMIN provisioning is an explicit operator action in a later phase, never a public registration option.

Movies have metadata, poster URLs, genres, and optional external identifiers. CineMatch does not stream video, sell tickets, host copyrighted media, or provide social networking. Catalog entry is initially manual through admin tools; a licensed external import provider is not selected.

## MVP and later scope

| MVP, required before product completion | Future scope, requires another phase |
| --- | --- |
| Register, login, logout, token refresh, profile and account status | Email verification, email delivery, password recovery, third-party login |
| Paginated browsing, title search, genre/year filters, details | Advanced semantic search, external catalog synchronization |
| Ratings, watched status, favorites, watchlist, personal statistics | Reviews, social feeds, shared lists, notifications |
| Popularity fallback and user-based collaborative filtering with cosine similarity, Top-K neighbors and weighted predictions | Large-scale recommendation optimizations; no complex ML without explicit scope revision |
| Movie/genre/user administration; system, event and recommendation monitoring | Multi-region operations, managed orchestration, automated scaling |
| Outbox, consumer groups, retries, recovery, replay, idempotency | Additional consumers only when justified |
| Docker Compose, metrics, dashboards, automated tests and load evaluation | Production high availability and disaster-recovery automation |

The required technology list is the approved toolbox, not a requirement to force every library into every feature. ML remains an in-process batch calculation using NumPy/Pandas/scikit-learn as needed. No separate model serving service is planned.

## Delivery sequence and dependencies

1. Approve this blueprint, requirements, decisions and unresolved assumptions.
2. Establish repository structure, configuration, CI/test foundations, database and Alembic baseline.
3. Build authentication, authorization and catalog management.
4. Build user interactions and transactional outbox writes together.
5. Implement publisher, consumer, recovery, idempotency and monitoring; prove failure cases.
6. Implement popularity and collaborative recommendations from verified source data.
7. Deliver frontend journeys, analytics, end-to-end validation and deployment evaluation.

This sequence is a proposal for future phase instructions, not authorization to implement. Durable interactions precede recommendation projections. Backend contracts precede frontend integration. Each phase updates documentation and its own acceptance evidence.

## Constraints and assumptions

- Single PostgreSQL database and single backend codebase; separate API and worker processes are deployment roles, not microservices.
- Initial evaluation dataset: at most 10,000 users, 20,000 movies and 1,000,000 interactions. Sparse ratings may make popularity the dominant fallback.
- Ratings use integer values 1–5, one current rating per user/movie. All timestamps are UTC; the UI localizes display.
- No external paid service is required. Poster licensing, seed-data provenance, target hardware and public hosting remain to be confirmed before data import or deployment.
- Account deletion/export and jurisdiction-specific retention obligations require a later explicit policy decision before public release. MVP supports account suspension and session revocation.

Detailed security, permission, testing and acceptance contracts are in REQUIREMENTS.md. ARCHITECTURE.md defines API modules, entities, event semantics, recommendation math and deployment.
