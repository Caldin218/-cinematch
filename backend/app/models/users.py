from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(btrim(email)) AND length(email) BETWEEN 3 AND 320", name="email_normalized"),
        CheckConstraint("length(btrim(display_name)) BETWEEN 1 AND 100", name="display_name_length"),
        CheckConstraint("length(password_hash) > 0", name="password_hash_nonempty"),
        CheckConstraint("role IN ('USER', 'ADMIN')", name="role_allowed"),
        CheckConstraint("status IN ('active', 'suspended')", name="status_allowed"),
        CheckConstraint("updated_at >= created_at", name="timestamp_order"),
        CheckConstraint("interaction_version >= 0", name="interaction_version_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, server_default="USER")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")

    interaction_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
