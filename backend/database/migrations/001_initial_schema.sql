-- BR10 Block Web - Migração Inicial
-- Cria todas as tabelas do sistema
-- Versão: 3.0.0
-- Data: 2026-02-08

-- Extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabela de usuários
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    email VARCHAR(255),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para users
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_active ON users(active);

-- Tabela de domínios bloqueados
CREATE TABLE IF NOT EXISTS domains (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) UNIQUE NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by VARCHAR(100),
    source VARCHAR(50),  -- 'pdf', 'manual', 'api', 'import'
    source_reference VARCHAR(255),  -- nome do arquivo PDF, ID da API, etc
    active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Índices para domains
CREATE INDEX idx_domains_domain ON domains(domain);
CREATE INDEX idx_domains_active ON domains(active);
CREATE INDEX idx_domains_source ON domains(source);
CREATE INDEX idx_domains_added_at ON domains(added_at DESC);
CREATE INDEX idx_domains_metadata ON domains USING gin(metadata);

-- Tabela de clientes DNS
CREATE TABLE IF NOT EXISTS dns_clients (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    api_key VARCHAR(64) UNIQUE NOT NULL,
    ip_address INET,
    description TEXT,
    status VARCHAR(50) DEFAULT 'offline',  -- 'online', 'offline', 'syncing', 'error'
    last_sync TIMESTAMP,
    last_heartbeat TIMESTAMP,
    domains_count INTEGER DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Índices para dns_clients
CREATE INDEX idx_dns_clients_api_key ON dns_clients(api_key);
CREATE INDEX idx_dns_clients_status ON dns_clients(status);
CREATE INDEX idx_dns_clients_active ON dns_clients(active);
CREATE INDEX idx_dns_clients_last_sync ON dns_clients(last_sync DESC);

-- Tabela de histórico de sincronizações
CREATE TABLE IF NOT EXISTS sync_history (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES dns_clients(id) ON DELETE CASCADE,
    domains_sent INTEGER DEFAULT 0,
    domains_applied INTEGER DEFAULT 0,
    status VARCHAR(50),  -- 'success', 'failed', 'partial', 'pending'
    message TEXT,
    error_details TEXT,
    duration_seconds INTEGER,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Índices para sync_history
CREATE INDEX idx_sync_history_client_id ON sync_history(client_id);
CREATE INDEX idx_sync_history_status ON sync_history(status);
CREATE INDEX idx_sync_history_synced_at ON sync_history(synced_at DESC);

-- Tabela de uploads de PDF
CREATE TABLE IF NOT EXISTS pdf_uploads (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size INTEGER,
    file_hash VARCHAR(64),
    domains_extracted INTEGER DEFAULT 0,
    domains_added INTEGER DEFAULT 0,
    domains_duplicated INTEGER DEFAULT 0,
    uploaded_by VARCHAR(100),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    processing_error TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Índices para pdf_uploads
CREATE INDEX idx_pdf_uploads_uploaded_at ON pdf_uploads(uploaded_at DESC);
CREATE INDEX idx_pdf_uploads_processed ON pdf_uploads(processed);
CREATE INDEX idx_pdf_uploads_file_hash ON pdf_uploads(file_hash);

-- Tabela de histórico de domínios
CREATE TABLE IF NOT EXISTS domain_history (
    id SERIAL PRIMARY KEY,
    domain_id INTEGER REFERENCES domains(id) ON DELETE SET NULL,
    domain VARCHAR(255) NOT NULL,
    action VARCHAR(50) NOT NULL,  -- 'added', 'removed', 'updated', 'activated', 'deactivated'
    performed_by VARCHAR(100),
    old_value JSONB,
    new_value JSONB,
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Índices para domain_history
CREATE INDEX idx_domain_history_domain_id ON domain_history(domain_id);
CREATE INDEX idx_domain_history_domain ON domain_history(domain);
CREATE INDEX idx_domain_history_action ON domain_history(action);
CREATE INDEX idx_domain_history_performed_at ON domain_history(performed_at DESC);

-- Tabela de logs de API
CREATE TABLE IF NOT EXISTS api_logs (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES dns_clients(id) ON DELETE SET NULL,
    endpoint VARCHAR(255),
    method VARCHAR(10),
    ip_address INET,
    user_agent TEXT,
    status_code INTEGER,
    request_data JSONB,
    response_data JSONB,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para api_logs
CREATE INDEX idx_api_logs_client_id ON api_logs(client_id);
CREATE INDEX idx_api_logs_endpoint ON api_logs(endpoint);
CREATE INDEX idx_api_logs_status_code ON api_logs(status_code);
CREATE INDEX idx_api_logs_created_at ON api_logs(created_at DESC);

-- Tabela de configurações do sistema
CREATE TABLE IF NOT EXISTS system_settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT,
    value_type VARCHAR(50) DEFAULT 'string',  -- 'string', 'integer', 'boolean', 'json'
    description TEXT,
    updated_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para system_settings
CREATE INDEX idx_system_settings_key ON system_settings(key);

-- Função para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para atualizar updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_dns_clients_updated_at BEFORE UPDATE ON dns_clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Inserir usuário admin padrão (senha: admin123)
INSERT INTO users (username, password_hash, role, email)
VALUES (
    'admin',
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',  -- SHA-256 de 'admin123'
    'admin',
    'admin@br10.local'
) ON CONFLICT (username) DO NOTHING;

-- Inserir configurações padrão do sistema
INSERT INTO system_settings (key, value, value_type, description)
VALUES
    ('sync_interval_minutes', '15', 'integer', 'Intervalo de sincronização automática com clientes DNS'),
    ('max_domains_per_sync', '10000', 'integer', 'Número máximo de domínios por sincronização'),
    ('enable_auto_backup', 'true', 'boolean', 'Habilitar backup automático'),
    ('backup_retention_days', '7', 'integer', 'Dias de retenção de backups'),
    ('api_rate_limit', '100', 'integer', 'Limite de requisições por minuto na API')
ON CONFLICT (key) DO NOTHING;

-- Comentários nas tabelas
COMMENT ON TABLE users IS 'Usuários do sistema administrativo';
COMMENT ON TABLE domains IS 'Lista de domínios bloqueados';
COMMENT ON TABLE dns_clients IS 'Clientes DNS que recebem atualizações';
COMMENT ON TABLE sync_history IS 'Histórico de sincronizações com clientes';
COMMENT ON TABLE pdf_uploads IS 'Histórico de uploads de arquivos PDF';
COMMENT ON TABLE domain_history IS 'Histórico de mudanças nos domínios';
COMMENT ON TABLE api_logs IS 'Logs de requisições da API';
COMMENT ON TABLE system_settings IS 'Configurações do sistema';
