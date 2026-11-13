"""Preserve grouped Bloom history and accept explicitly reviewed six-level metadata."""
from app.db import run_sql

revision = "0017"
down_revision = "0016"


def upgrade():
    run_sql("alter table question add column bloom_level_6 smallint check (bloom_level_6 between 1 and 6)")


def downgrade():
    raise NotImplementedError("forward-only")
