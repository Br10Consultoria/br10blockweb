-- BR10 Block Web - Migration 002: Lista de Remoção de Domínios
-- Adiciona suporte a uploads de PDF para remoção e remoção manual em lote
-- Versão: 3.1.0
-- Data: 2026-03-12

-- Tabela de uploads de PDF para REMOÇÃO de domínios
CREATE TABLE IF NOT EXISTS pdf_removals (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size INTEGER,
    file_hash VARCHAR(64),
    domains_extracted INTEGER DEFAULT 0,
    domains_removed INTEGER DEFAULT 0,
    domains_not_found INTEGER DEFAULT 0,
    uploaded_by VARCHAR(100),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    processing_error TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Índices para pdf_removals
CREATE INDEX IF NOT EXISTS idx_pdf_removals_uploaded_at ON pdf_removals(uploaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_pdf_removals_processed ON pdf_removals(processed);
CREATE INDEX IF NOT EXISTS idx_pdf_removals_file_hash ON pdf_removals(file_hash);

-- Comentário
COMMENT ON TABLE pdf_removals IS 'Histórico de uploads de PDF para remoção de domínios bloqueados';
