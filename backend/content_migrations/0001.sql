create table content_schema_version(version int primary key);
create table content_user (
 id uuid primary key, username text unique not null check(username ~ '^[a-z0-9][a-z0-9._-]{2,63}$'),
 password_hash text not null, display_name text not null, active boolean not null default true,
 created_at timestamptz not null default now());
create table content_user_role (
 user_id uuid references content_user on delete cascade, role text check(role in ('editor','reviewer','publisher')),
 primary key(user_id,role));
create table content_token (
 hash text primary key, user_id uuid not null references content_user, kind text not null check(kind in ('access','refresh')),
 family uuid not null, expires_at timestamptz not null, revoked boolean not null default false);
create index content_token_user on content_token(user_id);
create table content_auth_failure(ip_hash text not null, at timestamptz not null default now());
create index content_auth_failure_ip on content_auth_failure(ip_hash,at);
create table content_audit_event (
 id bigint generated always as identity primary key, actor_id uuid references content_user,
 action text not null, target text not null, metadata jsonb not null default '{}', at timestamptz not null default now());
create table content_import_batch (
 id uuid primary key, source_namespace text not null, archive_sha256 text not null,
 importer_version text not null, mapping_version text not null, status text not null check(status in ('running','completed','failed')),
 report jsonb not null default '{}', created_by uuid references content_user, created_at timestamptz not null default now(),
 unique(source_namespace,archive_sha256,importer_version,mapping_version));
create table source_document (
 id uuid primary key, source_namespace text not null, external_doc_id text not null, title text not null,
 issuer text, publication_year int, source_kind text not null, citation_mode text not null check(citation_mode in ('section','page')),
 unique(source_namespace,external_doc_id));
create table source_document_revision (
 id uuid primary key, document_id uuid not null references source_document, revision_no int not null check(revision_no>0),
 batch_id uuid not null references content_import_batch, artifact_sha256 text not null,
 parser_version text not null, chunker_version text not null, source_availability text not null,
 created_at timestamptz not null default now(), unique(document_id,revision_no), unique(document_id,artifact_sha256));
create index source_revision_batch on source_document_revision(batch_id);
create table source_asset (
 id uuid primary key, revision_id uuid not null references source_document_revision, asset_key text not null,
 role text not null, mime_type text not null, size_bytes bigint not null check(size_bytes>=0), sha256 text not null,
 storage_key text not null, unique(revision_id,asset_key));
create table document_chunk (
 id uuid primary key, revision_id uuid not null references source_document_revision,
 source_chunk_id text not null, seq int not null check(seq>=0), kind text not null check(kind in ('text','table','figure','box','formula')),
 text text not null, search_text text not null, location jsonb not null, tokens int check(tokens>=0),
 content_sha256 text not null, source_content_hash text not null, quality_flags jsonb not null default '[]',
 refs jsonb not null default '[]', unique(revision_id,source_chunk_id), unique(revision_id,seq));
create table taxonomy_snapshot (
 version text primary key, payload jsonb not null, sha256 text not null, mapping jsonb not null default '{}');
create table taxonomy_issue (
 snapshot_version text references taxonomy_snapshot, issue_id int, name text not null, group_code text not null,
 primary key(snapshot_version,issue_id));
create table taxonomy_domain (
 snapshot_version text references taxonomy_snapshot, domain_code text, name text not null,
 primary key(snapshot_version,domain_code));
create table chunk_tag_set (
 id uuid primary key, chunk_id uuid not null references document_chunk, taxonomy_version text not null references taxonomy_snapshot,
 source text not null check(source in ('auto','human')), bloom_ceiling text not null,
 bloom_confidence double precision check(bloom_confidence between 0 and 1), content_type text not null,
 population text[] not null, rationale text not null default '', original_payload jsonb not null,
 created_by uuid references content_user, created_at timestamptz not null default now(),
 unique(id,chunk_id), unique(id,taxonomy_version));
create index chunk_tags_chunk on chunk_tag_set(chunk_id,created_at);
create table chunk_issue_tag (
 tag_set_id uuid, taxonomy_version text, issue_id int, is_primary boolean not null,
 confidence double precision check(confidence between 0 and 1), primary key(tag_set_id,issue_id),
 foreign key(tag_set_id,taxonomy_version) references chunk_tag_set(id,taxonomy_version),
 foreign key(taxonomy_version,issue_id) references taxonomy_issue(snapshot_version,issue_id));
create unique index chunk_one_primary on chunk_issue_tag(tag_set_id) where is_primary;
create table chunk_domain_tag (
 tag_set_id uuid, taxonomy_version text, domain_code text,
 confidence double precision check(confidence between 0 and 1), primary key(tag_set_id,domain_code),
 foreign key(tag_set_id,taxonomy_version) references chunk_tag_set(id,taxonomy_version),
 foreign key(taxonomy_version,domain_code) references taxonomy_domain(snapshot_version,domain_code));
create table chunk_review_task (
 id uuid primary key, chunk_id uuid not null references document_chunk,
 purpose text not null check(purpose in ('classification','content')),
 status text not null check(status in ('open','resolved')), reasons jsonb not null,
 unique(chunk_id,purpose));
create table chunk_review_decision (
 id uuid primary key, task_id uuid not null references chunk_review_task,
 chunk_id uuid not null references document_chunk, tag_set_id uuid,
 purpose text not null check(purpose in ('classification','content')),
 decision text not null check(decision in ('accept','revise','reject')),
 reviewer_id uuid not null references content_user, comment text not null, policy_version text not null,
 created_at timestamptz not null default now(), unique(id,chunk_id),
 foreign key(tag_set_id,chunk_id) references chunk_tag_set(id,chunk_id),
 check(decision='accept' or length(btrim(comment))>0));
create index chunk_decision_chunk on chunk_review_decision(chunk_id,created_at);
create table chunk_state (
 chunk_id uuid primary key references document_chunk, classification_status text not null default 'unclassified'
 check(classification_status in ('classified','unclassified')),
 proposed_tag_set_id uuid, confirmed_tag_set_id uuid, classification_decision_id uuid, content_approval_decision_id uuid,
 content_status text not null default 'pending' check(content_status in ('pending','approved','needs_revision','rejected')),
 row_version int not null default 1, updated_at timestamptz not null default now(),
 foreign key(proposed_tag_set_id,chunk_id) references chunk_tag_set(id,chunk_id),
 foreign key(confirmed_tag_set_id,chunk_id) references chunk_tag_set(id,chunk_id),
 foreign key(classification_decision_id,chunk_id) references chunk_review_decision(id,chunk_id),
 foreign key(content_approval_decision_id,chunk_id) references chunk_review_decision(id,chunk_id),
 check((classification_status='classified')=(confirmed_tag_set_id is not null and classification_decision_id is not null)),
 check((content_status='approved')=(content_approval_decision_id is not null)));
create index chunk_state_filter on chunk_state(classification_status,content_status,updated_at);
create table content_operation (
 actor_id uuid references content_user, route text, key text, payload_hash text not null, result jsonb not null,
 primary key(actor_id,route,key));
create function content_immutable() returns trigger language plpgsql as $$
begin raise exception '% is immutable',tg_table_name; end $$;
create function content_state_guard() returns trigger language plpgsql as $$
declare d chunk_review_decision; t chunk_tag_set; n int; p int;
begin
 if new.classification_status='classified' then
  select * into d from chunk_review_decision where id=new.classification_decision_id;
  if d.purpose<>'classification' or d.decision<>'accept' or d.tag_set_id is distinct from new.confirmed_tag_set_id then
   raise exception 'classification requires matching accepted decision'; end if;
  select count(*),count(*) filter(where is_primary) into n,p from chunk_issue_tag where tag_set_id=new.confirmed_tag_set_id;
  if n not between 1 and 3 or p<>1 then raise exception 'one primary and at most two secondary issues required'; end if;
  select count(*) into n from chunk_domain_tag where tag_set_id=new.confirmed_tag_set_id;
  if n not between 1 and 2 then raise exception 'one or two domains required'; end if;
 end if;
 if new.content_status='approved' then
  select * into d from chunk_review_decision where id=new.content_approval_decision_id;
  if d.purpose<>'content' or d.decision<>'accept' then raise exception 'content requires accepted decision'; end if;
 end if;
 return new;
end $$;
create trigger chunk_state_guard before insert or update on chunk_state for each row execute function content_state_guard();
do $$declare t text; begin
 foreach t in array array['source_document_revision','source_asset','document_chunk','taxonomy_snapshot','taxonomy_issue',
 'taxonomy_domain','chunk_tag_set','chunk_issue_tag','chunk_domain_tag','chunk_review_decision','content_audit_event'] loop
 execute format('create trigger immutable before update or delete on %I for each row execute function content_immutable()',t);
 end loop; end $$;
insert into content_schema_version values(1);
