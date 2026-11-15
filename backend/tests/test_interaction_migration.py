import os
from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError
from app.models import Movie, Rating, User
from test_database_schema import temporary_database, alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="Requires PostgreSQL")]


def test_upgrade_preserves_integer_ratings_and_safe_downgrade():
    with temporary_database() as engine:
        with engine.connect() as c:
            config = alembic_config(c)
            command.upgrade(config, "0001_initial_schema")
            user = c.scalar(insert(User).values(email="migration@example.com", display_name="Migration", password_hash="fixture").returning(User.id))
            movie = c.scalar(insert(Movie).values(title="Migration").returning(Movie.id))
            c.execute(insert(Rating).values(user_id=user,movie_id=movie,value=4))
            c.commit()
            command.upgrade(config, "head")
            assert c.scalar(select(Rating.value)) == Decimal("4.00")
            assert c.scalar(select(User.interaction_version)) == 0
            c.commit()
            command.downgrade(config,"0001_initial_schema")
            assert c.scalar(select(Rating.value)) == 4
            c.commit()
            command.upgrade(config,"head")
            c.execute(text("UPDATE ratings SET value=0.5"))
            c.commit()
            assert c.scalar(select(Rating.value)) == Decimal("0.50")
            c.commit()
            for value in (0,0.49,5.01):
                with pytest.raises(IntegrityError), c.begin_nested():
                    c.execute(text("UPDATE ratings SET value=:value"),{"value":value})
            c.rollback()
            with pytest.raises(RuntimeError,match="losslessly"):
                command.downgrade(config,"0001_initial_schema")
            c.rollback()
            assert c.scalar(select(Rating.value)) == Decimal("0.50")
            assert c.scalar(text("SELECT version_num FROM alembic_version")) == "0005_user_portal"
            c.execute(text("UPDATE ratings SET value=4"))
            c.execute(text("UPDATE users SET interaction_version=1"))
            c.commit()
            with pytest.raises(RuntimeError,match="losslessly"):
                command.downgrade(config,"0001_initial_schema")
            c.rollback()
            assert c.scalar(select(User.interaction_version)) == 1
