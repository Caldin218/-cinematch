"""Decimal ratings and durable interaction event sequence.

Revision ID: 0002_interactions
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_interactions"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def score_check(lower: str) -> str:
    return (
        f"(method = 'user_cf' AND predicted_rating BETWEEN {lower} AND 5 AND predicted_rating IS NOT NULL AND popularity_score IS NULL) OR "
        f"(method = 'popularity' AND popularity_score BETWEEN {lower} AND 5 AND popularity_score IS NOT NULL AND predicted_rating IS NULL) OR "
        "(method = 'catalog_fallback' AND predicted_rating IS NULL AND popularity_score IS NULL)"
    )


def upgrade() -> None:
    op.drop_constraint(op.f("ck_ratings_value_range"), "ratings", type_="check")
    op.alter_column("ratings", "value", existing_type=sa.SmallInteger(), type_=sa.Numeric(3, 2),
                    existing_nullable=False, postgresql_using="value::numeric(3,2)")
    op.create_check_constraint(op.f("ck_ratings_value_range"), "ratings", "value BETWEEN 0.5 AND 5")
    op.add_column("users", sa.Column("interaction_version", sa.BigInteger(), nullable=False, server_default="0"))
    op.create_check_constraint(op.f("ck_users_interaction_version_nonnegative"), "users", "interaction_version >= 0")
    op.drop_constraint(op.f("ck_recommendations_method_score_consistent"), "recommendations", type_="check")
    op.create_check_constraint(op.f("ck_recommendations_method_score_consistent"), "recommendations", score_check("0.5"))


def downgrade() -> None:
    # Refuse lossy downgrade instead of rounding fractional user data silently.
    connection = op.get_bind()
    incompatible = connection.scalar(sa.text(
        "SELECT EXISTS(SELECT 1 FROM ratings WHERE value < 1 OR value <> trunc(value)) OR "
        "EXISTS(SELECT 1 FROM recommendations WHERE predicted_rating < 1 OR popularity_score < 1) OR "
        "EXISTS(SELECT 1 FROM users WHERE interaction_version > 0)"
    ))
    if incompatible:
        raise RuntimeError("Cannot downgrade interaction data losslessly; back up and explicitly reconcile data first")
    op.drop_constraint(op.f("ck_recommendations_method_score_consistent"), "recommendations", type_="check")
    op.create_check_constraint(op.f("ck_recommendations_method_score_consistent"), "recommendations", score_check("1"))
    op.drop_constraint(op.f("ck_users_interaction_version_nonnegative"), "users", type_="check")
    op.drop_column("users", "interaction_version")
    op.drop_constraint(op.f("ck_ratings_value_range"), "ratings", type_="check")
    op.alter_column("ratings", "value", existing_type=sa.Numeric(3, 2), type_=sa.SmallInteger(),
                    existing_nullable=False, postgresql_using="value::smallint")
    op.create_check_constraint(op.f("ck_ratings_value_range"), "ratings", "value BETWEEN 1 AND 5")
