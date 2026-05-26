-- migrate:up

-- ============================================================
-- Extensions & shared functions
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- agent_message_usage
-- Uma linha por chamada de LLM (cost tracking). Imutável (sem updated_at).
-- ============================================================

CREATE TABLE agent_message_usage (
  id SERIAL PRIMARY KEY,
  thread_id VARCHAR(128) NOT NULL,
  message_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(255),
  client_id VARCHAR(255),
  agent_id VARCHAR(255) NOT NULL,
  provider VARCHAR(64) NOT NULL,
  model_id VARCHAR(255) NOT NULL,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  cached_input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  reasoning_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_agent_message_usage_client_id ON agent_message_usage(client_id);
CREATE INDEX ix_agent_message_usage_created_at ON agent_message_usage(created_at);
CREATE INDEX ix_agent_message_usage_thread_id ON agent_message_usage(thread_id);

-- ============================================================
-- chat_history
-- Uma thread de conversa por linha (messages em JSONB).
-- ============================================================

CREATE TABLE chat_history (
  thread_id VARCHAR(128) PRIMARY KEY,
  user_id VARCHAR(255) NOT NULL,
  client_id VARCHAR(255),
  agent_id VARCHAR(255) NOT NULL,
  messages JSONB NOT NULL DEFAULT '[]'::jsonb,
  preview TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_chat_history_client_id ON chat_history(client_id);
CREATE INDEX ix_chat_history_user_id ON chat_history(user_id);

CREATE TRIGGER update_chat_history_updated_at
  BEFORE UPDATE ON chat_history
  FOR EACH ROW
  WHEN (OLD.* IS DISTINCT FROM NEW.*)
  EXECUTE PROCEDURE update_updated_at_column();

-- ============================================================
-- checkpoint_blobs / checkpoint_writes / checkpoints   (langgraph)
-- Tabelas do AsyncPostgresSaver. Schema versionado via dbmate em vez de
-- checkpointer.setup() em runtime — sem DDL no startup.
-- ============================================================

CREATE TABLE checkpoint_blobs (
  thread_id VARCHAR NOT NULL,
  checkpoint_ns VARCHAR NOT NULL DEFAULT '',
  channel VARCHAR NOT NULL,
  version VARCHAR NOT NULL,
  type VARCHAR NOT NULL,
  blob BYTEA,
  PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

CREATE TABLE checkpoint_writes (
  thread_id VARCHAR NOT NULL,
  checkpoint_ns VARCHAR NOT NULL DEFAULT '',
  checkpoint_id VARCHAR NOT NULL,
  task_id VARCHAR NOT NULL,
  task_path VARCHAR NOT NULL DEFAULT '',
  idx INTEGER NOT NULL,
  channel VARCHAR NOT NULL,
  type VARCHAR,
  blob BYTEA,
  PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

CREATE TABLE checkpoints (
  thread_id VARCHAR NOT NULL,
  checkpoint_ns VARCHAR NOT NULL DEFAULT '',
  checkpoint_id VARCHAR NOT NULL,
  parent_checkpoint_id VARCHAR,
  type VARCHAR,
  checkpoint JSONB NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

-- ============================================================
-- user_uploads
-- Single source of truth para todo upload user-owned (anexos de chat etc).
-- owner_user_id é VARCHAR (a identidade do template é string — sem tabela users).
-- Ver rule uploads.md + skill uploads-storage.
-- ============================================================

CREATE TABLE user_uploads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id VARCHAR(255) NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  kind TEXT NOT NULL,
  url TEXT NOT NULL,
  filename TEXT NOT NULL,
  mime_type TEXT,
  size_bytes INTEGER,
  width INTEGER,
  height INTEGER,
  visibility TEXT NOT NULL DEFAULT 'public',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ,
  CONSTRAINT ck_user_uploads_kind CHECK (kind IN (
    'logo','banner','avatar','photo','gallery_image','document',
    'attachment','whatsapp_media','export','other'
  )),
  CONSTRAINT ck_user_uploads_visibility CHECK (visibility IN ('public','tenant','private'))
);

CREATE INDEX ix_user_uploads_owner_user_id ON user_uploads(owner_user_id);
CREATE INDEX ix_user_uploads_entity ON user_uploads(entity_type, entity_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_user_uploads_kind ON user_uploads(kind) WHERE deleted_at IS NULL;

CREATE TRIGGER update_user_uploads_updated_at
  BEFORE UPDATE ON user_uploads
  FOR EACH ROW
  WHEN (OLD.* IS DISTINCT FROM NEW.*)
  EXECUTE PROCEDURE update_updated_at_column();

-- migrate:down

DROP TRIGGER IF EXISTS update_user_uploads_updated_at ON user_uploads;
DROP TABLE IF EXISTS user_uploads;
DROP TABLE IF EXISTS checkpoint_writes;
DROP TABLE IF EXISTS checkpoint_blobs;
DROP TABLE IF EXISTS checkpoints;
DROP TRIGGER IF EXISTS update_chat_history_updated_at ON chat_history;
DROP TABLE IF EXISTS chat_history;
DROP TABLE IF EXISTS agent_message_usage;
DROP FUNCTION IF EXISTS update_updated_at_column();
