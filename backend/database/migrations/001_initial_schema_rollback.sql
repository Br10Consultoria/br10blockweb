-- BR10 Block Web - Rollback da Migração Inicial
-- Remove todas as tabelas criadas na migração 001
-- Versão: 3.0.0
-- Data: 2026-02-08

-- Remover triggers
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
DROP TRIGGER IF EXISTS update_dns_clients_updated_at ON dns_clients;

-- Remover função
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Remover tabelas (ordem inversa devido às foreign keys)
DROP TABLE IF EXISTS api_logs CASCADE;
DROP TABLE IF EXISTS domain_history CASCADE;
DROP TABLE IF EXISTS pdf_uploads CASCADE;
DROP TABLE IF EXISTS sync_history CASCADE;
DROP TABLE IF EXISTS dns_clients CASCADE;
DROP TABLE IF EXISTS domains CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS system_settings CASCADE;

-- Remover extensões (comentado para não afetar outros bancos)
-- DROP EXTENSION IF EXISTS "uuid-ossp";
