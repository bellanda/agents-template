-- migrate:up
-- Preferências de interface por pessoa (hoje: o estilo visual escolhido, `app_style`).
-- O template não tem tabela de usuários (identidade aberta por header, services/auth.py), então
-- esta migration cria a mínima, chaveada pelo MESMO `user_id` texto do auth context. App novo com
-- tabela `users` própria troca o CREATE TABLE por
--   ALTER TABLE users ADD COLUMN ui_preferences jsonb NOT NULL DEFAULT '{}'::jsonb;
-- (padrão de frota 2026-11-07; ver skill frontend, ref app-styles).
CREATE TABLE IF NOT EXISTS users (
  id VARCHAR(255) PRIMARY KEY,
  ui_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- migrate:down
DROP TABLE IF EXISTS users;
