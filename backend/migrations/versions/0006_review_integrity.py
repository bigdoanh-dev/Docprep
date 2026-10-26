"""Findings of the phase 2 review: a tighter approval rule, immutable review decisions, and three
contract fields that had no column behind them."""
from app.db import run_sql

revision = "0006"
down_revision = "0005"

SQL = """
-- A content item's topic, so the review queue can show and filter it before the item is in a unit.
alter table content_item add column competency_code text references competency_node;
update content_item c set competency_code = u.competency_code
  from unit_item i join unit u on u.id = i.unit_id
  where i.content_id = c.id and c.competency_code is null;

-- The chat history endpoint returns these; none can be recomputed later.
alter table chat_message
  add column clarify_options jsonb,
  add column searched jsonb,
  add column nearest_chapter jsonb;

-- The name from the import file, held until the code is activated, then moved to learner_identity
-- and cleared here.
alter table activation_code add column display_name text;

-- The evidence behind an approval cannot be edited, re-pointed or removed.
create trigger review_decision_append_only before update or delete on review_decision
  for each statement execute function forbid_change();

-- Serving a question by id must find one approved version.
create unique index question_one_approved_version on question (id) where status = 'approved';
create unique index content_item_one_approved_version on content_item (id) where status = 'approved';

-- Human in the loop, tightened:
--   * approved is reached only by an update from in_review_r2, never by insert or from another status,
--     so a retired item cannot come back on its old reviews;
--   * the latest decision of each round must be a pass, by different reviewers;
--   * an approved item keeps its id, version and content; an edit is a new version.
create or replace function approved_requires_two_reviews() returns trigger language plpgsql as $$
declare
  r1 record;
  r2 record;
  -- columns that legitimately change on an approved row
  mutable text[] := case tg_argv[0]
    when 'question' then array['status', 'difficulty_b', 'n_responses']
    else array['status'] end;
begin
  if tg_op = 'UPDATE' and old.status = 'approved' then
    if (to_jsonb(new) - mutable) is distinct from (to_jsonb(old) - mutable) then
      raise exception 'an approved item cannot be edited; create a new version';
    end if;
    return new;
  end if;
  if new.status <> 'approved' then
    return new;
  end if;
  if tg_op = 'INSERT' or old.status <> 'in_review_r2' then
    raise exception 'approved needs a pass in round 1 and round 2 from different reviewers, and is reached only from in_review_r2';
  end if;
  select decision, reviewer_id into r1 from review_decision
    where target_type = tg_argv[0] and target_id = new.id and version = new.version and round = 1
    order by id desc limit 1;
  select decision, reviewer_id into r2 from review_decision
    where target_type = tg_argv[0] and target_id = new.id and version = new.version and round = 2
    order by id desc limit 1;
  if r1.decision is distinct from 'pass' or r2.decision is distinct from 'pass'
     or r1.reviewer_id = r2.reviewer_id then
    raise exception 'approved needs a pass in round 1 and round 2 from different reviewers';
  end if;
  return new;
end $$;
"""


def upgrade() -> None:
    run_sql(SQL)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
