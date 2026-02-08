# Análise do Sistema BR10 Block Web

## Data da Análise
08 de Fevereiro de 2026

## Estrutura Atual do Projeto

### Componentes Identificados

1. **Dashboard Web (br10dashboard/)**
   - Framework: Flask (Python)
   - Arquivo principal: `app.py` (3151 linhas)
   - Sistema de autenticação com usuários
   - Interface web para visualização de estatísticas DNS
   - Testes de performance e latência DNS
   - Monitoramento de recursos do sistema

2. **Infraestrutura**
   - Redis para cache
   - Unbound DNS Server
   - Docker/Docker Compose para containerização

### Funcionalidades Existentes

#### Dashboard Web
- ✅ Sistema de login e autenticação
- ✅ Visualização de estatísticas DNS
- ✅ Monitoramento de clientes DNS
- ✅ Testes de latência, cache e hypercache
- ✅ Visualização de logs
- ✅ Gerenciamento de usuários
- ✅ Monitoramento de recursos do sistema

#### Gestão de Domínios
- ✅ Leitura de domínios bloqueados de arquivo texto (`/var/lib/br10api/blocked_domains.txt`)
- ✅ Visualização de domínios bloqueados via interface web
- ✅ Carregamento de zona RPZ do Unbound

## Problemas Identificados

### 1. **AUSÊNCIA DE FUNCIONALIDADE DE UPLOAD DE PDF**
   - ❌ Não existe nenhuma rota ou função para upload de arquivos PDF
   - ❌ Não há extração de domínios de arquivos PDF
   - ❌ Sistema atual apenas lê domínios de arquivo texto estático

### 2. **AUSÊNCIA DE API CLIENT**
   - ❌ Não existe código de API client no repositório
   - ❌ Não há comunicação com DNS clientes externos
   - ❌ Não há sistema de envio de domínios para clientes via API
   - ❌ Não há sistema de recebimento de feedback dos clientes

### 3. **AUSÊNCIA DE HISTÓRICO DE ATUALIZAÇÕES**
   - ❌ Existe rota `/api/history` mas a função `load_history_data()` não foi encontrada implementada
   - ❌ Não há registro de quando domínios foram adicionados/removidos
   - ❌ Não há rastreamento de sincronização com clientes

### 4. **GESTÃO DE DOMÍNIOS LIMITADA**
   - ⚠️ Domínios são lidos apenas de arquivo texto estático
   - ⚠️ Não há interface para adicionar/remover domínios manualmente
   - ⚠️ Não há validação de domínios
   - ⚠️ Não há banco de dados para armazenar domínios

### 5. **CÓDIGO DUPLICADO E DESORGANIZADO**
   - ⚠️ Configurações duplicadas no arquivo `app.py` (linhas 45-70 e 184-214)
   - ⚠️ Arquivo muito extenso (3151 linhas) sem modularização adequada
   - ⚠️ Falta de separação de responsabilidades

## Funcionalidades Necessárias (Requisitos do Usuário)

### 1. **Upload e Extração de PDF**
   - 📋 Interface web para upload de arquivos PDF
   - 📋 Extração automática de domínios do PDF
   - 📋 Validação e sanitização de domínios extraídos
   - 📋 Preview dos domínios antes de aplicar

### 2. **Armazenamento Local**
   - 📋 Banco de dados para armazenar domínios (SQLite ou PostgreSQL)
   - 📋 Versionamento de listas de domínios
   - 📋 Histórico de mudanças com timestamp
   - 📋 Backup automático

### 3. **API Client e Sincronização**
   - 📋 API REST para comunicação com DNS clientes
   - 📋 Sistema de autenticação para clientes (API keys)
   - 📋 Endpoint para envio de lista de domínios
   - 📋 Endpoint para receber status de aplicação dos clientes
   - 📋 Sistema de heartbeat para monitorar clientes online

### 4. **Histórico de Atualizações**
   - 📋 Registro de todas as atualizações de domínios
   - 📋 Registro de sincronizações com clientes
   - 📋 Status de aplicação por cliente
   - 📋 Visualização em timeline

### 5. **Gestão de DNS Clientes**
   - 📋 Cadastro de clientes DNS
   - 📋 Monitoramento de status (online/offline)
   - 📋 Visualização de última sincronização
   - 📋 Forçar sincronização manual

## Proposta de Arquitetura Refatorada

### Stack Tecnológico Recomendado

**Opção 1: Python (Manter Flask)**
- ✅ Já está implementado
- ✅ Equipe pode já conhecer Python
- ✅ Bibliotecas maduras para PDF (PyPDF2, pdfplumber)
- ✅ Flask é leve e eficiente
- ⚠️ Código atual precisa de refatoração significativa

**Opção 2: PHP (Alternativa)**
- ✅ Muito usado para sistemas web
- ✅ Bibliotecas para PDF (TCPDF, FPDI)
- ✅ Fácil deploy em servidores tradicionais
- ❌ Requer reescrever todo o sistema
- ❌ Perda do código já desenvolvido

**Recomendação: Manter Python/Flask e refatorar**

### Arquitetura Proposta

```
br10blockweb/
├── backend/
│   ├── app.py                    # Aplicação Flask principal (simplificada)
│   ├── config.py                 # Configurações centralizadas
│   ├── models/
│   │   ├── domain.py            # Modelo de domínio
│   │   ├── client.py            # Modelo de cliente DNS
│   │   ├── history.py           # Modelo de histórico
│   │   └── user.py              # Modelo de usuário
│   ├── services/
│   │   ├── pdf_extractor.py    # Serviço de extração de PDF
│   │   ├── domain_manager.py   # Serviço de gestão de domínios
│   │   ├── client_sync.py      # Serviço de sincronização com clientes
│   │   └── history_service.py  # Serviço de histórico
│   ├── api/
│   │   ├── admin_routes.py     # Rotas administrativas
│   │   ├── client_routes.py    # Rotas para clientes DNS
│   │   └── auth.py             # Autenticação
│   ├── utils/
│   │   ├── validators.py       # Validadores
│   │   └── helpers.py          # Funções auxiliares
│   └── database/
│       ├── db.py               # Conexão com banco
│       └── migrations/         # Migrações de banco
├── frontend/
│   ├── templates/              # Templates HTML (existentes)
│   └── static/                 # CSS, JS, imagens
├── uploads/                    # Diretório para PDFs enviados
├── data/
│   ├── domains.db             # Banco de dados SQLite
│   └── backups/               # Backups automáticos
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

### Banco de Dados Proposto

```sql
-- Tabela de domínios
CREATE TABLE domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT UNIQUE NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by TEXT,
    source TEXT,  -- 'pdf', 'manual', 'api'
    active BOOLEAN DEFAULT 1
);

-- Tabela de clientes DNS
CREATE TABLE dns_clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    api_key TEXT UNIQUE NOT NULL,
    ip_address TEXT,
    last_sync TIMESTAMP,
    status TEXT DEFAULT 'offline',  -- 'online', 'offline', 'syncing'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de histórico de sincronizações
CREATE TABLE sync_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    domains_sent INTEGER,
    status TEXT,  -- 'success', 'failed', 'partial'
    message TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES dns_clients(id)
);

-- Tabela de uploads de PDF
CREATE TABLE pdf_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    domains_extracted INTEGER,
    uploaded_by TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de histórico de domínios
CREATE TABLE domain_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER,
    action TEXT,  -- 'added', 'removed', 'updated'
    performed_by TEXT,
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (domain_id) REFERENCES domains(id)
);
```

## Plano de Implementação

### Fase 1: Refatoração Base
1. Modularizar código existente
2. Criar estrutura de diretórios proposta
3. Implementar banco de dados SQLite
4. Migrar gestão de domínios para banco

### Fase 2: Upload e Extração de PDF
1. Criar rota de upload de PDF
2. Implementar extração de domínios (regex + validação)
3. Interface de preview e confirmação
4. Armazenar no banco de dados

### Fase 3: API para Clientes DNS
1. Sistema de autenticação com API keys
2. Endpoint GET para lista de domínios
3. Endpoint POST para feedback de aplicação
4. Sistema de heartbeat

### Fase 4: Histórico e Monitoramento
1. Implementar registro de todas as operações
2. Interface de visualização de histórico
3. Dashboard de status dos clientes
4. Alertas e notificações

### Fase 5: Testes e Deploy
1. Testes unitários e de integração
2. Documentação da API
3. Scripts de deploy
4. Backup automático

## Estimativa de Esforço

- **Fase 1**: 2-3 dias
- **Fase 2**: 2-3 dias
- **Fase 3**: 3-4 dias
- **Fase 4**: 2-3 dias
- **Fase 5**: 2 dias

**Total estimado**: 11-15 dias de desenvolvimento

## Próximos Passos

1. ✅ Análise concluída
2. ⏳ Aguardar aprovação do usuário
3. ⏳ Iniciar refatoração conforme plano aprovado
