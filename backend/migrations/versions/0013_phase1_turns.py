"""Durable AI turns, dispatch outbox and model-call quarantine. Additive to Alpha."""
from app.db import run_sql

revision = "0013"
down_revision = "0012"


def upgrade():
    run_sql("""
    create table ai_turn (
      id uuid primary key,
      seq bigserial unique not null,
      learner_id int not null references learner on delete cascade,
      session_id int references chat_session on delete cascade,
      kind text not null check (kind in ('chat','explain','hint')),
      route text not null,
      idempotency_key text not null,
      payload_hash text not null,
      payload jsonb not null,
      status text not null default 'queued'
        check (status in ('queued','running','completed','failed','cancelled','interrupted')),
      owner text,
      fence bigint not null default 0,
      heartbeat_at timestamptz,
      model_started boolean not null default false,
      created_at timestamptz not null default now(),
      queue_deadline timestamptz not null,
      deadline_at timestamptz not null,
      finished_at timestamptz,
      result jsonb,
      error jsonb,
      unique (learner_id, route, idempotency_key)
    );
    create unique index ai_turn_one_active on ai_turn(learner_id)
      where status in ('queued','running');
    create index ai_turn_dispatch on ai_turn(status,seq);
    create table ai_outbox (
      turn_id uuid primary key references ai_turn on delete cascade,
      published_epoch text
    );
    create table ai_model_call (
      id uuid primary key,
      turn_id uuid not null references ai_turn on delete cascade,
      resource text not null,
      owner text not null,
      started_at timestamptz not null default now(),
      ended_at timestamptz,
      -- Separate from the FK: account deletion must not silently free a GPU slot.
      quarantined boolean not null default false
    );
    -- Tombstones survive removal of a learner/turn while an external call may still run.
    alter table ai_model_call drop constraint ai_model_call_turn_id_fkey;
    create index ai_model_call_open on ai_model_call(resource) where ended_at is null;
    alter table chat_message add column ai_turn_id uuid references ai_turn on delete set null;
    create unique index chat_message_ai_assistant on chat_message(ai_turn_id)
      where role = 'assistant' and ai_turn_id is not null;
    create table ai_purge (turn_id uuid primary key);
    create function phase1_invalidate_ai() returns trigger language plpgsql
      security definer set search_path=public,pg_temp as $$
    declare lid int;
    begin
      -- Branch before accessing record fields: NEW has a different row type per trigger.
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
      update ai_turn set status='cancelled', finished_at=now(),
        error='{"code":"ai_cancelled","message_vi":"Lượt AI đã dừng do điều kiện sử dụng thay đổi."}'::jsonb
        where learner_id=lid and status in ('queued','running');
      if TG_OP = 'DELETE' then return OLD; else return NEW; end if;
    end $$;
    revoke all on function phase1_invalidate_ai() from public;
    create trigger phase1_exam before insert on exam_attempt
      for each row execute function phase1_invalidate_ai();
    create trigger phase1_consent before update or delete on consent_record
      for each row execute function phase1_invalidate_ai();
    create trigger phase1_learner before update of active or delete on learner
      for each row execute function phase1_invalidate_ai();
    """)


def downgrade():
    raise NotImplementedError("forward-only; restore to a separate database")
