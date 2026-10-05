"""
Row-Level Security (RLS) Policies para PostgreSQL
Executa automaticamente ao inicializar o banco

Documentação: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
"""

# RLS policies que devem ser executadas no banco de dados
# Execute isso como superuser (postgres) uma vez

RLS_POLICIES = """
-- ============================================================================
-- SUBSCRIPTIONS - Row Level Security
-- ============================================================================

-- Habilitar RLS na tabela de subscriptions
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Policy: Cada account só pode ver suas próprias subscriptions
CREATE POLICY subscriptions_tenant_isolation ON subscriptions
  USING (account_id = current_setting('app.current_account_id')::TEXT)
  WITH CHECK (account_id = current_setting('app.current_account_id')::TEXT);

-- ============================================================================
-- USERS - Row Level Security (isolamento por tenant)
-- ============================================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY users_tenant_isolation ON users
  USING (tenant_id = current_setting('app.current_tenant_id')::TEXT)
  WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::TEXT);

-- ============================================================================
-- CONVERSATIONS - Row Level Security
-- ============================================================================

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY conversations_tenant_isolation ON conversations
  USING (tenant_id = current_setting('app.current_tenant_id')::TEXT)
  WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::TEXT);

-- ============================================================================
-- MESSAGES - Row Level Security
-- ============================================================================

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY messages_tenant_isolation ON messages
  USING (tenant_id = current_setting('app.current_tenant_id')::TEXT)
  WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::TEXT);

-- ============================================================================
-- AUDIT LOG TABLE (imutável)
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id VARCHAR(36) NOT NULL,
  action VARCHAR(100) NOT NULL,
  resource_type VARCHAR(100) NOT NULL,
  resource_id VARCHAR(255),
  old_values JSONB,
  new_values JSONB,
  ip_address VARCHAR(45),
  user_agent TEXT,
  status VARCHAR(20) DEFAULT 'success',
  error_message TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  
  CONSTRAINT fk_audit_account FOREIGN KEY (account_id) 
    REFERENCES accounts(id) ON DELETE CASCADE,
  CONSTRAINT idx_audit_timestamp 
    CHECK (created_at <= CURRENT_TIMESTAMP)
);

-- Index para queries rápidas
CREATE INDEX IF NOT EXISTS idx_audit_logs_account_id ON audit_logs(account_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);

-- RLS para audit logs (cada account vê só seus logs)
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_logs_tenant_isolation ON audit_logs
  USING (account_id = current_setting('app.current_account_id')::TEXT)
  WITH CHECK (account_id = current_setting('app.current_account_id')::TEXT);

-- ============================================================================
-- SENSIBLE DATA LOG TABLE (para rastrear acessos a dados sensíveis)
-- ============================================================================

CREATE TABLE IF NOT EXISTS sensitive_data_access_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id VARCHAR(36) NOT NULL,
  data_type VARCHAR(100) NOT NULL,  -- 'payment', 'personal_info', 'api_key', etc
  resource_id VARCHAR(255),
  accessed_by VARCHAR(36),  -- user_id ou 'system'
  ip_address VARCHAR(45),
  user_agent TEXT,
  action VARCHAR(50),  -- 'read', 'export', 'delete'
  is_successful BOOLEAN DEFAULT true,
  reason TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  
  CONSTRAINT fk_sensitive_account FOREIGN KEY (account_id) 
    REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sensitive_access_account ON sensitive_data_access_logs(account_id);
CREATE INDEX IF NOT EXISTS idx_sensitive_access_created ON sensitive_data_access_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sensitive_access_data_type ON sensitive_data_access_logs(data_type);

ALTER TABLE sensitive_data_access_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY sensitive_access_tenant_isolation ON sensitive_data_access_logs
  USING (account_id = current_setting('app.current_account_id')::TEXT)
  WITH CHECK (account_id = current_setting('app.current_account_id')::TEXT);
"""

# Função para set current account (execute em cada request)
SET_ACCOUNT_FUNCTION = """
-- Função para setar o current_account_id no session
-- Chamada na autenticação de cada request

CREATE OR REPLACE FUNCTION set_account_context(account_id TEXT)
RETURNS void AS $$
BEGIN
  PERFORM set_config('app.current_account_id', account_id, false);
END;
$$ LANGUAGE plpgsql;

-- Função para setar tenant context
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_id TEXT)
RETURNS void AS $$
BEGIN
  PERFORM set_config('app.current_tenant_id', tenant_id, false);
END;
$$ LANGUAGE plpgsql;

-- Função para criar audit log
CREATE OR REPLACE FUNCTION audit_subscription_change()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO audit_logs (
    account_id,
    action,
    resource_type,
    resource_id,
    old_values,
    new_values,
    status
  ) VALUES (
    NEW.account_id,
    TG_OP,
    'subscription',
    NEW.id,
    to_jsonb(OLD),
    to_jsonb(NEW),
    'success'
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para audit de subscriptions
CREATE TRIGGER subscriptions_audit_trigger
  AFTER INSERT OR UPDATE OR DELETE ON subscriptions
  FOR EACH ROW
  EXECUTE FUNCTION audit_subscription_change();
"""

# Instruções para setup
SETUP_INSTRUCTIONS = """
Para habilitar RLS no seu banco de dados PostgreSQL:

1. Conecte como superuser (postgres):
   psql -U postgres -d adstudioai

2. Execute os scripts RLS:
   \i rls_policies.sql

3. Confirme que RLS está ativo:
   SELECT * FROM information_schema.tables 
   WHERE table_name='subscriptions' AND rowsecurity = true;

4. Teste o isolamento:
   -- Como admin, set o account_id
   SELECT set_account_context('account-id-123');
   
   -- Agora só verá dados dessa account
   SELECT * FROM subscriptions;

IMPORTANTE:
- RLS não substitui validação no código, mas complementa
- Sempre valide tenant_id no Python também
- RLS é última linha de defesa contra SQL injection
"""

__all__ = [
    'RLS_POLICIES',
    'SET_ACCOUNT_FUNCTION',
    'SETUP_INSTRUCTIONS'
]
