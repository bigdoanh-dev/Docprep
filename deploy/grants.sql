-- Run only as the migration owner. Repeat after every migration. No runtime role owns tables.
revoke create on schema public from public;
revoke all on all tables in schema public from phase_business, phase_chat;
revoke all on all sequences in schema public from phase_business, phase_chat;
grant usage on schema public to phase_business, phase_chat;
grant select, insert, update, delete on all tables in schema public to phase_business;
revoke all on ai_model_call from phase_business;
grant usage, select on all sequences in schema public to phase_business;
grant select on alembic_version, learner, auth_token, consent_record, exam_attempt,
  module, unit, unit_item, unit_session, practice_set, item_response, mastery,
  competency_node, document, passage, glossary_term, question, status_transition,
  session_addition, chat_session, chat_message, suggestion, ai_turn, ai_outbox,
  ai_model_call, ai_purge to phase_chat;
grant select (id,role,active) on staff_user to phase_chat;
grant insert,update,delete on chat_session, chat_message, suggestion, ai_turn, ai_outbox, ai_model_call, ai_purge to phase_chat;
grant insert on activity_event to phase_chat;
grant usage,select on all sequences in schema public to phase_chat;
revoke all on learner_identity from phase_chat;
-- Prevent runtime schema rewrites and table ownership escalation.
revoke all on alembic_version from phase_business;
grant select on alembic_version to phase_business;
