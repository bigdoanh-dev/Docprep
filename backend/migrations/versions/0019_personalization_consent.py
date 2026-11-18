"""A third, optional consent: personalization. Separate from service and research, off until given."""
from app.db import run_sql

revision = "0019"
down_revision = "0018"


def upgrade():
    run_sql("""
    alter table consent_record drop constraint consent_record_kind_check;
    alter table consent_record add constraint consent_record_kind_check
      check (kind in ('service', 'research', 'personalization'));
    """)


def downgrade():
    raise NotImplementedError("forward-only")
