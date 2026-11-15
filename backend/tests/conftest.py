import os

# Explicit test-only configuration; never changes a developer's configured values.
if os.getenv("RUN_INTEGRATION") != "1":
    os.environ.setdefault("POSTGRES_USER", "test")
    os.environ.setdefault("POSTGRES_PASSWORD", "test-only")
    os.environ.setdefault("POSTGRES_DB", "test")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
