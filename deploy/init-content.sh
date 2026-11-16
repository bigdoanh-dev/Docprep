#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -v pw="$CONTENT_APP_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE content_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L', :'pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='content_app') \gexec
REVOKE CONNECT ON DATABASE content_workspace FROM PUBLIC;
GRANT CONNECT ON DATABASE content_workspace TO content_app;
SQL
