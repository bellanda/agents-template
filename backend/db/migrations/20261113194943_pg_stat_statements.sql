-- migrate:up

-- Audit 2026-11-13 infra-live-04: postgresql.conf preloads pg_stat_statements, but the extension was
-- never created in any database, so the statistics view did not exist and nobody could tell which
-- query was expensive. Idempotent. Needs a superuser (POSTGRES_USER of the compose is one).
-- Top queries: SELECT calls, round(total_exec_time) AS total_ms, round(mean_exec_time) AS mean_ms,
-- left(query, 120) FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20;

CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA public;

-- migrate:down

DROP EXTENSION IF EXISTS pg_stat_statements;
