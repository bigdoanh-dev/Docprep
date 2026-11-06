#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v bp="$BUSINESS_DB_PASSWORD" -v cp="$CHAT_DB_PASSWORD" -v mp="$MIGRATOR_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE phase_business LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L', :'bp')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='phase_business') \gexec
SELECT format('CREATE ROLE phase_chat LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L', :'cp')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='phase_chat') \gexec
SELECT format('CREATE ROLE phase_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L', :'mp')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='phase_migrator') \gexec
GRANT USAGE,CREATE ON SCHEMA public TO phase_migrator;
-- Supports upgrading the initial local Phase 1 draft without resetting its data.
SELECT format('ALTER TABLE public.%I OWNER TO phase_migrator', tablename)
FROM pg_tables WHERE schemaname='public' AND tableowner='phase_owner' \gexec
SELECT format('ALTER SEQUENCE public.%I OWNER TO phase_migrator', sequencename)
FROM pg_sequences WHERE schemaname='public' AND sequenceowner='phase_owner' \gexec
SELECT 'ALTER FUNCTION phase1_invalidate_ai() OWNER TO phase_migrator'
WHERE to_regprocedure('phase1_invalidate_ai()') IS NOT NULL \gexec
SQL
