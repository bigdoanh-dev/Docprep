""""Tôi đã hiểu" / "Tôi chưa hiểu" on an answer: the learner's own signal, kept beside "Hữu ích"."""
from app.db import run_sql

revision = "0020"
down_revision = "0019"


def upgrade():
    run_sql("alter table chat_message add column if not exists understood boolean;")


def downgrade():
    raise NotImplementedError("forward-only")
