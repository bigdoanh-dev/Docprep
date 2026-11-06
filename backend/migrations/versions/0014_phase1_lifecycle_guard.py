"""Ensure lifecycle triggers branch by relation before accessing NEW/OLD row fields."""
from app.db import run_sql

revision = "0014"
down_revision = "0013"


def upgrade():
    run_sql("""
    create or replace function phase1_invalidate_ai() returns trigger language plpgsql
      security definer set search_path=public,pg_temp as $$
    declare lid int;
    begin
      if TG_TABLE_NAME = 'exam_attempt' then
        lid := NEW.learner_id;
        if NEW.submitted_at is not null or NEW.deadline_at <= now() then return NEW; end if;
      elsif TG_TABLE_NAME = 'learner' then
        lid := OLD.id;
        if TG_OP = 'UPDATE' then
          if NEW.active then return NEW; end if;
        end if;
      else
        lid := OLD.learner_id;
        if OLD.kind <> 'service' then
          if TG_OP = 'DELETE' then return OLD; else return NEW; end if;
        end if;
        if TG_OP = 'UPDATE' then
          if NEW.withdrawn_at is null then return NEW; end if;
        end if;
      end if;
      perform pg_advisory_xact_lock(71103, lid);
      insert into ai_purge select id from ai_turn where learner_id=lid on conflict do nothing;
      update ai_turn set status='cancelled',finished_at=now(),
        error='{"code":"ai_cancelled","message_vi":"Lượt AI đã dừng do điều kiện sử dụng thay đổi."}'::jsonb
        where learner_id=lid and status in ('queued','running');
      if TG_OP = 'DELETE' then return OLD; else return NEW; end if;
    end $$;
    revoke all on function phase1_invalidate_ai() from public;
    """)


def downgrade():
    raise NotImplementedError("forward-only")
