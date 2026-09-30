-- migrate:up
-- ============================================================
-- Canonical AI layer (2026-09-30): per-tenant cost + tenant agent instructions.
--
-- `tenant_id` is the accounting/config scope. The template has no organizations table, so
-- the auth seam sets tenant_id = user_id; apps map their organization_id here (kailos/balizap
-- kept an `organization_id UUID` column for the same purpose).
-- ============================================================

ALTER TABLE agent_message_usage ADD COLUMN tenant_id VARCHAR(255);

-- Monthly spend per tenant: WHERE tenant_id = $1 AND created_at >= $2.
CREATE INDEX ix_agent_message_usage_tenant_id_created_at
  ON agent_message_usage(tenant_id, created_at)
  WHERE tenant_id IS NOT NULL;

-- ============================================================
-- agent_configs
-- The ACTIVE tenant instructions for one agent: a single Markdown (built in ChatGPT and
-- pasted — the kailos/balizap screen), appended at runtime to the agent's base system prompt.
-- One row per (tenant, agent); history lives in agent_config_versions.
-- ============================================================

CREATE TABLE agent_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id VARCHAR(255) NOT NULL,
  agent_id VARCHAR(255) NOT NULL,
  model_id VARCHAR(255) NOT NULL,
  system_prompt_markdown TEXT NOT NULL DEFAULT '',
  active_version INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Mirrors MAX_PROMPT_MARKDOWN_CHARS (schemas/agents/agent_config.py + frontend lib/api.ts).
  CONSTRAINT ck_agent_configs_markdown_length CHECK (char_length(system_prompt_markdown) <= 20000)
);

CREATE UNIQUE INDEX uq_agent_configs_tenant_id_agent_id ON agent_configs(tenant_id, agent_id);

CREATE TRIGGER update_agent_configs_updated_at
  BEFORE UPDATE ON agent_configs
  FOR EACH ROW
  WHEN (OLD.* IS DISTINCT FROM NEW.*)
  EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- agent_config_versions
-- Immutable snapshot per save (rollback = activate an old version as a NEW version).
-- No updated_at: versions never mutate.
-- ============================================================

CREATE TABLE agent_config_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  config_id UUID NOT NULL REFERENCES agent_configs(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  model_id VARCHAR(255) NOT NULL,
  system_prompt_markdown TEXT NOT NULL DEFAULT '',
  note TEXT,
  created_by VARCHAR(255),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Also covers the FK (config_id leftmost) and the newest-first listing.
CREATE UNIQUE INDEX uq_agent_config_versions_config_id_version
  ON agent_config_versions(config_id, version);

-- migrate:down
DROP TABLE IF EXISTS agent_config_versions;
DROP TABLE IF EXISTS agent_configs;
DROP INDEX IF EXISTS ix_agent_message_usage_tenant_id_created_at;
ALTER TABLE agent_message_usage DROP COLUMN IF EXISTS tenant_id;
