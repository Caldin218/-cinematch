from sqlalchemy import BigInteger, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app import models
from app.core.database import Base


def test_registry_and_key_types_without_database():
    assert len(Base.metadata.tables) == 15
    assert isinstance(models.User.__table__.c.id.type, UUID)
    assert isinstance(models.Movie.__table__.c.id.type, BigInteger)
    for table in Base.metadata.tables.values():
        assert table.primary_key.name
        for column in table.c:
            if isinstance(column.type, DateTime):
                assert column.type.timezone is True
        for constraint in table.constraints:
            assert constraint.name, (table.name, constraint)
