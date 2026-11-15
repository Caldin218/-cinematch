"""User portal catalog metadata and persistent community comments."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0005_user_portal"
down_revision = "0004_recommendation_jobs"
branch_labels = depends_on = None

def upgrade():
    op.add_column("movies", sa.Column("original_title", sa.String(255)))
    op.add_column("movies", sa.Column("trailer_youtube_id", sa.String(11)))
    op.create_table("movie_comments",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("movie_id", sa.BigInteger(), sa.ForeignKey("movies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(btrim(body)) BETWEEN 1 AND 2000", name=op.f("ck_movie_comments_body_length")))
    op.create_index("ix_movie_comments_movie_time", "movie_comments", ["movie_id", sa.text("created_at DESC"), sa.text("id DESC")])
    op.create_table("comment_likes",
        sa.Column("comment_id", sa.BigInteger(), sa.ForeignKey("movie_comments.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True))

def downgrade():
    op.drop_table("comment_likes")
    op.drop_table("movie_comments")
    op.drop_column("movies", "trailer_youtube_id")
    op.drop_column("movies", "original_title")
