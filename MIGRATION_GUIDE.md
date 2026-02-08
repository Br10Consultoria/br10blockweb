# Guia de Migração - BR10 Block Web v2.x → v3.0.0

Este guia explica como migrar do sistema antigo (monolítico, app.py único) para a nova arquitetura refatorada.

---

## 1. Principais Mudanças

### 1.1. Arquitetura

| Aspecto | v2.x (Antigo) | v3.0.0 (Novo) |
| :--- | :--- | :--- |
| **Estrutura** | Monolítica (1 arquivo `app.py`) | Modular (backend/frontend separados) |
| **Banco de Dados** | SQLite (arquivo local) | PostgreSQL (containerizado) |
| **Cache** | Redis (opcional) | Redis (integrado, essencial) |
| **Autenticação** | Básica | API Keys para clientes + sessão web |
| **API** | Endpoints misturados | API separada (client/admin) |
| **Upload de PDF** | ❌ Não existia | ✅ Implementado |
| **Histórico** | ❌ Não existia | ✅ Completo (domínios, syncs, uploads) |
| **Sincronização** | ❌ Não existia | ✅ Com feedback dos clientes |

### 1.2. Banco de Dados

**Antes (SQLite):**
- Arquivo `database.db` local
- Tabelas simples
- Sem histórico

**Agora (PostgreSQL):**
- Servidor PostgreSQL dedicado
- 7 tabelas principais:
  - `users` - Usuários administrativos
  - `domains` - Domínios bloqueados
  - `dns_clients` - Clientes DNS cadastrados
  - `sync_history` - Histórico de sincronizações
  - `pdf_uploads` - Histórico de uploads
  - `domain_history` - Auditoria de domínios
  - `api_logs` - Logs de requisições da API

### 1.3. Funcionalidades Novas

1. **Upload de PDF**: Extração automática de domínios de arquivos PDF
2. **API REST Completa**: Endpoints para clientes DNS e administração
3. **Histórico e Auditoria**: Rastreamento completo de todas as operações
4. **Sincronização com Feedback**: Clientes reportam status de aplicação
5. **Cache Inteligente**: Redis cache para alta performance
6. **Rate Limiting**: Proteção contra abuso da API
7. **Gerenciamento de Clientes**: Cadastro, API keys, monitoramento

---

## 2. Passo a Passo da Migração

### 2.1. Backup do Sistema Antigo

**IMPORTANTE**: Faça backup de tudo antes de começar!

```bash
# Parar sistema antigo
docker-compose down  # ou systemctl stop br10blockweb

# Backup do banco SQLite
cp database.db database.db.backup

# Backup das configurações
tar czf config-backup.tar.gz config/ .env

# Backup dos domínios (se houver arquivo de zona)
cp /etc/unbound/blocklist.conf /etc/unbound/blocklist.conf.backup
```

### 2.2. Exportar Domínios do Sistema Antigo

Se você tem domínios no sistema antigo, exporte-os:

```python
# Script para exportar domínios do SQLite
import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Exportar domínios
cursor.execute("SELECT domain FROM domains WHERE active = 1")
domains = [row[0] for row in cursor.fetchall()]

# Salvar em arquivo
with open('domains_export.txt', 'w') as f:
    f.write('\n'.join(domains))

print(f"Exportados {len(domains)} domínios para domains_export.txt")
conn.close()
```

### 2.3. Instalar o Novo Sistema

1. **Clonar o repositório refatorado**:
   ```bash
   git clone https://github.com/Br10Consultoria/br10blockweb.git br10blockweb-v3
   cd br10blockweb-v3
   ```

2. **Configurar variáveis de ambiente**:
   ```bash
   cp .env.example .env
   # Editar .env se necessário
   ```

3. **Subir os containers**:
   ```bash
   docker-compose up --build -d
   ```

4. **Inicializar o banco de dados**:
   ```bash
   docker-compose exec web python3 init_db.py
   ```
   - Siga as instruções para criar o usuário admin

### 2.4. Importar Domínios

Você pode importar os domínios exportados de duas formas:

#### Opção 1: Via Interface Web (Recomendado para PDFs)

1. Acesse http://localhost:5000
2. Faça login
3. Vá em "Upload PDF"
4. Faça upload do seu PDF de blocklist

#### Opção 2: Via API (Para listas TXT)

```bash
# Importar domínios via API
curl -X POST http://localhost:5000/api/v1/admin/domains/bulk \
  -H "Content-Type: application/json" \
  -d "{\"domains\": $(cat domains_export.txt | jq -R -s -c 'split(\"\n\")[:-1]')}"
```

#### Opção 3: Via Script Python

```python
# Script de importação
import sys
sys.path.insert(0, '/caminho/para/br10blockweb-v3')

from backend.services.domain_manager import DomainManager

# Ler domínios
with open('domains_export.txt', 'r') as f:
    domains = [line.strip() for line in f if line.strip()]

# Importar
result = DomainManager.add_domains_bulk(
    domains=domains,
    added_by='migration',
    source='migration_v2'
)

print(f"Importados: {result['added']}")
print(f"Duplicados: {result['duplicated']}")
```

### 2.5. Migrar Clientes DNS

Se você tinha clientes DNS configurados, você precisará:

1. **Cadastrar cada cliente no novo sistema**:
   - Acesse "Clientes DNS" no dashboard
   - Clique em "Novo Cliente"
   - Preencha nome, IP, descrição
   - Copie a API key gerada

2. **Atualizar scripts dos clientes**:
   
   **Antes (v2.x)**:
   ```bash
   # Cliente antigo (exemplo)
   curl http://servidor:5000/domains > blocklist.txt
   ```
   
   **Agora (v3.0.0)**:
   ```bash
   # Cliente novo com autenticação
   curl -H "Authorization: Bearer SUA_API_KEY" \
        http://servidor:5000/api/v1/client/domains?format=txt > blocklist.txt
   ```

### 2.6. Configurar Sincronização Automática

Crie um script no cliente DNS para sincronização periódica:

```bash
#!/bin/bash
# /usr/local/bin/br10-sync.sh

API_KEY="sua_api_key_aqui"
SERVER="http://servidor:5000"

# Iniciar sincronização
SYNC_ID=$(curl -s -H "Authorization: Bearer $API_KEY" \
  -X POST "$SERVER/api/v1/client/sync/start" | jq -r '.sync_id')

# Baixar domínios
curl -s -H "Authorization: Bearer $API_KEY" \
  "$SERVER/api/v1/client/domains?format=rpz" > /tmp/blocklist.rpz

# Aplicar no Unbound
cp /tmp/blocklist.rpz /etc/unbound/blocklist.rpz
unbound-control reload

# Reportar sucesso
curl -s -H "Authorization: Bearer $API_KEY" \
  -X POST "$SERVER/api/v1/client/sync/complete" \
  -H "Content-Type: application/json" \
  -d "{\"sync_id\": $SYNC_ID, \"domains_applied\": $(wc -l < /tmp/blocklist.rpz), \"status\": \"success\"}"
```

Agende no cron:
```bash
# Sincronizar a cada 1 hora
0 * * * * /usr/local/bin/br10-sync.sh
```

---

## 3. Verificação Pós-Migração

### 3.1. Checklist

- [ ] Todos os domínios foram importados?
  ```bash
  # Verificar contagem
  curl http://localhost:5000/api/v1/client/domains/count
  ```

- [ ] Clientes DNS estão cadastrados?
  - Acesse "Clientes DNS" no dashboard

- [ ] Clientes conseguem se autenticar?
  ```bash
  curl -H "Authorization: Bearer API_KEY_TESTE" \
       http://localhost:5000/api/v1/client/ping
  ```

- [ ] Upload de PDF funciona?
  - Teste fazendo upload de um PDF

- [ ] Histórico está sendo registrado?
  - Acesse "Histórico" no dashboard

### 3.2. Testes de Performance

```bash
# Teste de latência da API
time curl -s -H "Authorization: Bearer API_KEY" \
     http://localhost:5000/api/v1/client/domains/count

# Deve ser < 100ms com cache

# Teste de carga (com Apache Bench)
ab -n 1000 -c 10 -H "Authorization: Bearer API_KEY" \
   http://localhost:5000/api/v1/client/domains/count
```

---

## 4. Rollback (Se Necessário)

Se algo der errado, você pode voltar ao sistema antigo:

```bash
# Parar novo sistema
cd br10blockweb-v3
docker-compose down

# Voltar ao sistema antigo
cd ../br10blockweb-old
docker-compose up -d  # ou systemctl start br10blockweb

# Restaurar banco
cp database.db.backup database.db
```

---

## 5. Diferenças de API

| Endpoint Antigo | Endpoint Novo | Notas |
| :--- | :--- | :--- |
| `GET /domains` | `GET /api/v1/client/domains` | Requer API key |
| `GET /stats` | `GET /api/v1/admin/stats` | Requer autenticação admin |
| ❌ Não existia | `POST /api/v1/admin/domains/upload` | Upload de PDF |
| ❌ Não existia | `GET /api/v1/client/sync/history` | Histórico de syncs |

---

## 6. Suporte

Se encontrar problemas durante a migração:

1. Verifique os logs:
   ```bash
   docker-compose logs -f web
   ```

2. Verifique o status dos containers:
   ```bash
   docker-compose ps
   ```

3. Consulte a documentação completa:
   - [README.md](README.md)
   - [API_DOCS.md](API_DOCS.md)

---

*Boa migração! 🚀*
