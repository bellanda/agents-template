-- migrate:up

-- Audit 2026-11-13 core-performance-09: the /files gate (and every private download) runs
-- `SELECT ... FROM <uploads> WHERE url = $1 AND deleted_at IS NULL` on each GET; with no index
-- on url that is a sequential scan per photo. Partial on deleted_at to match the query.

CREATE INDEX IF NOT EXISTS ix_user_uploads_url ON user_uploads(url) WHERE deleted_at IS NULL;

-- migrate:down

DROP INDEX IF EXISTS ix_user_uploads_url;
