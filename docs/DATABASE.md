# Database — Phase 1

PostgreSQL uses SQLAlchemy 2 and psycopg 3. Settings construct a URL from separate environment fields, escaping reserved password characters. Connections use pre-ping and bounded connection/pool timeouts. The session factory initializes at startup; future services own transaction commits.

No application tables or schema revisions exist. Alembic has an environment, template and versions directory. From backend/, run `./.venv/Scripts/python -m alembic history`. Future schema changes use `alembic revision --autogenerate -m "description"` with manual review, followed by `alembic upgrade head`; import future models into Alembic metadata first. Startup never creates tables.

The postgres_data volume preserves data. SELECT 1 verifies connectivity, not schema correctness. Planned entities remain in ARCHITECTURE.md.
