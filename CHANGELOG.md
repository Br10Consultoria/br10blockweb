# Changelog - BR10 Block Web

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

---

## [3.0.0] - 2026-02-08

### 🎉 Refatoração Completa

Esta é uma **refatoração completa** do sistema, migrando de uma arquitetura monolítica para uma arquitetura modular moderna.

### ✨ Adicionado

#### Arquitetura
- **Arquitetura modular**: Backend separado em models, services, api, utils
- **PostgreSQL**: Migração de SQLite para PostgreSQL 16
- **Redis**: Cache integrado para alta performance
- **Docker**: Sistema completamente containerizado

#### Funcionalidades
- **Upload de PDF**: Extração automática de domínios de arquivos PDF
  - Suporte a PyPDF2 e pdfplumber
  - Detecção de duplicatas via hash SHA-256
  - Preview de domínios extraídos
  - Estatísticas de extração (TLDs, contadores)

- **API REST Completa**:
  - API para Clientes DNS (`/api/v1/client`)
    - `GET /ping` - Heartbeat
    - `GET /domains` - Lista de domínios (JSON/TXT/RPZ)
    - `GET /domains/count` - Contagem rápida
    - `POST /sync/start` - Iniciar sincronização
    - `POST /sync/complete` - Finalizar com feedback
    - `GET /sync/history` - Histórico de sincronizações
    - `GET /status` - Status detalhado do cliente
  
  - API Administrativa (`/api/v1/admin`)
    - CRUD completo de domínios
    - Gerenciamento de clientes DNS
    - Histórico e estatísticas
    - Upload de PDF via API

- **Sistema de Histórico e Auditoria**:
  - Histórico de domínios (adições, remoções, ativações)
  - Histórico de sincronizações com clientes
  - Histórico de uploads de PDF
  - Timeline unificada de eventos
  - Logs de requisições da API

- **Gerenciamento de Clientes DNS**:
  - Cadastro de clientes com API keys individuais
  - Monitoramento de status (online/offline/syncing)
  - Heartbeat automático
  - Regeneração de API keys
  - Relatórios por cliente

- **Cache e Performance**:
  - Cache Redis para lista de domínios
  - Cache de estatísticas
  - Cache de status de clientes
  - Rate limiting por cliente
  - TTL configurável por tipo de dado

- **Interface Web**:
  - Dashboard modernizado com Bootstrap 5
  - Visualização de timeline de eventos
  - Monitoramento de clientes em tempo real
  - Upload de PDF com drag & drop
  - Estatísticas e gráficos

#### Modelos de Dados
- `User` - Usuários administrativos
- `Domain` - Domínios bloqueados
- `DNSClient` - Clientes DNS cadastrados
- `SyncHistory` - Histórico de sincronizações
- `PDFUpload` - Histórico de uploads
- `DomainHistory` - Auditoria de domínios
- `APILog` - Logs de requisições

#### Serviços
- `PDFExtractor` - Extração de domínios de PDF
- `DomainManager` - Gerenciamento de domínios
- `CacheService` - Cache com Redis
- `ClientSyncService` - Sincronização com clientes
- `HistoryService` - Gerenciamento de histórico

### 🔄 Alterado

- **Banco de Dados**: SQLite → PostgreSQL
- **Estrutura**: Monolítica → Modular
- **Autenticação**: Básica → API Keys + Sessão Web
- **Cache**: Opcional → Integrado e essencial
- **API**: Endpoints misturados → API separada (client/admin)

### 🗑️ Removido

- Dependência de SQLite
- Código monolítico do `app.py` antigo
- Endpoints não documentados

### 🔒 Segurança

- Senhas com hash SHA-256
- API Keys únicas por cliente
- Validação de uploads (tipo, tamanho)
- Rate limiting para proteção contra abuso
- Sanitização de nomes de arquivo
- Validação de domínios, IPs, emails

### 📚 Documentação

- README.md completo
- API_DOCS.md com todos os endpoints
- MIGRATION_GUIDE.md para migração da v2.x
- Comentários e docstrings em todo o código
- Type hints em Python

### 🐛 Corrigido

- Problemas de performance com listas grandes
- Falta de histórico de operações
- Ausência de feedback de sincronização
- Falta de validação de uploads
- Ausência de cache

---

## [2.x] - Versões Anteriores

Sistema monolítico com SQLite e funcionalidades básicas.

---

## Formato

Este changelog segue o formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

Versionamento segue [Semantic Versioning](https://semver.org/lang/pt-BR/).
