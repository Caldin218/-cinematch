from alembic import context
from sqlalchemy import Connection

from app.core.config import get_settings
from app.core.database import Base, create_database_engine
from app import models  # noqa: F401 -- register all mapped tables in Base.metadata

target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(url=get_settings().database_url, target_metadata=target_metadata,
                      literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    # Tests may supply an isolated database connection without modifying .env.
    supplied_connection = context.config.attributes.get("connection")

    def run_online(connection: Connection) -> None:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    if supplied_connection is not None:
        run_online(supplied_connection)
    else:
        engine = create_database_engine(get_settings())
        try:
            with engine.connect() as connection:
                run_online(connection)
        finally:
            engine.dispose()
