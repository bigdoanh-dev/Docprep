"""Versioned pgvector corpus and operator index turns on the shared FIFO."""
from app.db import run_sql

revision = '0015'
down_revision = '0014'


def upgrade():
    run_sql("""
    create extension if not exists vector;
    alter table ai_turn alter column learner_id drop not null;
    alter table ai_turn drop constraint ai_turn_kind_check;
    alter table ai_turn add check (kind in ('chat','explain','hint','index'));
    alter table ai_turn add check ((kind='index' and learner_id is null and session_id is null)
                               or (kind<>'index' and learner_id is not null));
    create unique index ai_turn_one_index on ai_turn((payload->>'model'))
      where kind='index' and status in ('queued','running');
    create table embedding_index (
      model text not null, revision text not null, corpus_version text not null,
      dimensions int not null check (dimensions > 0), completed_at timestamptz,
      primary key(model,revision,corpus_version)
    );
    create table passage_embedding (
      passage_id text not null references passage(id) on delete cascade,
      model text not null, revision text not null, corpus_version text not null,
      content_hash text not null, embedding vector not null,
      primary key(passage_id,model,revision,corpus_version),
      foreign key(model,revision,corpus_version) references embedding_index on delete cascade
    );
    create function invalidate_passage_embedding() returns trigger language plpgsql
      security definer set search_path=public,pg_temp as $$
    begin
      if NEW.text is distinct from OLD.text or NEW.context is distinct from OLD.context then
        delete from passage_embedding where passage_id=OLD.id;
      end if;
      return NEW;
    end $$;
    revoke all on function invalidate_passage_embedding() from public;
    create trigger passage_embedding_changed before update of text,context on passage
      for each row execute function invalidate_passage_embedding();
    """)


def downgrade():
    raise NotImplementedError('forward-only; restore into a separate database')
