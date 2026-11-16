"""Immutable content publications and release-scoped source access."""
from app.db import run_sql
from alembic import op
revision='0018'
down_revision='0017'


def upgrade():
    # A local, unpublished corpus migration previously used 0017. The upstream
    # 0017 is Bloom metadata. Preserve either existing database and converge here.
    run_sql('alter table question add column if not exists bloom_level_6 smallint check (bloom_level_6 between 1 and 6)')
    connection=op.get_bind()
    if connection.exec_driver_sql("select to_regclass('public.corpus_release') is not null").scalar():
        complete=connection.exec_driver_sql("""select
            to_regclass('public.corpus_release_member') is not null and
            to_regclass('public.corpus_activation') is not null and
            to_regclass('public.corpus_activation_event') is not null and
            to_regprocedure('public.corpus_passage_visible(text,boolean)') is not null and
            exists(select 1 from information_schema.columns where table_schema='public' and table_name='passage' and column_name='release_id') and
            exists(select 1 from pg_trigger where tgrelid='public.passage'::regclass and tgname='published_passage_immutable')
            """).scalar()
        if not complete:
            raise RuntimeError('Incomplete legacy corpus schema; restore and reconcile before upgrading')
        return
    run_sql("""
    create table corpus_release (
      id uuid primary key, version text unique not null, manifest jsonb not null, manifest_sha256 text not null,
      trust text not null check(trust in ('local_dev','verified')), status text not null check(status in ('candidate','ready','revoked')),
      created_at timestamptz not null default now());
    create table corpus_release_member (
      release_id uuid not null references corpus_release, passage_id text not null references passage,
      source_chunk_ref text not null, source_revision_ref text not null, source_hash text not null,
      classification_snapshot jsonb not null, approval_snapshot jsonb not null,
      primary key(release_id,passage_id), unique(release_id,source_chunk_ref));
    create index corpus_member_passage on corpus_release_member(passage_id);
    create table corpus_activation (
      channel text primary key, release_id uuid not null references corpus_release, generation bigint not null,
      activated_at timestamptz not null default now(), actor_ref text not null);
    create table corpus_activation_event (
      id uuid primary key, channel text not null, from_release_id uuid references corpus_release,
      to_release_id uuid not null references corpus_release, action text not null, actor_ref text not null,
      reason text not null, created_at timestamptz not null default now());
    create trigger corpus_activation_event_immutable before update or delete on corpus_activation_event
      for each statement execute function forbid_change();
    alter table passage add column release_id uuid references corpus_release;
    create index passage_release on passage(release_id);
    create function corpus_passage_visible(pid text, historical boolean default false) returns boolean
      language sql stable as $$
      select exists(select 1 from passage p left join corpus_release r on r.id=p.release_id
       where p.id=pid and (
        (p.release_id is null and (historical or not exists(select 1 from corpus_release x
          where x.version=nullif(current_setting('app.corpus_version',true),''))))
        or (p.release_id is not null and r.status<>'revoked' and
          ((historical and r.status='ready') or (r.version=nullif(current_setting('app.corpus_version',true),'') and
           (r.status='ready' or current_setting('app.corpus_index',true)='on'))))))
      $$;
    create function corpus_snapshot_immutable() returns trigger language plpgsql as $$
    begin
      if tg_op='DELETE' then raise exception 'published source cannot be deleted'; end if;
      if tg_table_name='corpus_release' and
         (to_jsonb(new)-'status') is not distinct from (to_jsonb(old)-'status') then return new; end if;
      raise exception 'published snapshot is immutable';
    end $$;
    create trigger corpus_release_immutable before update or delete on corpus_release
      for each row execute function corpus_snapshot_immutable();
    create trigger corpus_member_immutable before update or delete on corpus_release_member
      for each row execute function corpus_snapshot_immutable();
    create function published_passage_immutable() returns trigger language plpgsql as $$
    begin
      if old.release_id is not null then raise exception 'published passage is immutable'; end if;
      if tg_op='DELETE' then return old; end if;
      return new;
    end $$;
    create trigger published_passage_immutable before update or delete on passage
      for each row execute function published_passage_immutable();
    """)


def downgrade():
    raise NotImplementedError('Forward only; restore into a separate database')
