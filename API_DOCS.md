# BR10 Block Web - Documentação da API v3.0.0

Esta documentação descreve os endpoints da API REST para o sistema BR10 Block Web. A API é dividida em duas seções: **API do Cliente** (para clientes DNS) e **API Administrativa** (para gerenciamento do sistema).

---

## 1. Autenticação

### 1.1. Autenticação de Cliente DNS

A API do Cliente requer uma **API Key** para autenticação. A chave deve ser enviada em uma das seguintes formas:

- **Header `Authorization` (Recomendado)**:
  ```
  Authorization: Bearer <SUA_API_KEY>
  ```
- **Header `X-API-Key`**:
  ```
  X-API-Key: <SUA_API_KEY>
  ```
- **Query Parameter `api_key`** (Menos seguro):
  ```
  GET /api/v1/client/ping?api_key=<SUA_API_KEY>
  ```

### 1.2. Autenticação Administrativa

A API Administrativa utiliza a **sessão de login** da interface web. O usuário deve estar autenticado no dashboard para acessar esses endpoints, geralmente através de um cliente de API que mantém a sessão (como um navegador).

---

## 2. API do Cliente (`/api/v1/client`)

Estes endpoints são projetados para serem consumidos por clientes DNS (Unbound, BIND, etc.) para obter a lista de bloqueio e reportar seu status.

### `GET /ping`

Verifica a conectividade com o servidor e funciona como um **heartbeat** para o cliente.

- **Resposta de Sucesso (200 OK)**:
  ```json
  {
    "success": true,
    "message": "pong",
    "client": {
      "id": 1,
      "name": "DNS-Server-01",
      "status": "online"
    },
    "server_time": "2026-02-08T20:00:00.123456"
  }
  ```

### `GET /domains`

Retorna a lista completa de domínios ativos para bloqueio.

- **Query Parameters**:
  - `format` (opcional): Formato da resposta. Padrão: `json`.
    - `json`: Lista de domínios em um objeto JSON.
    - `txt`: Lista de domínios em texto plano, um por linha.
    - `rpz`: Lista no formato RPZ (Response Policy Zone) para Unbound/BIND.
  - `metadata` (opcional): Se `true`, inclui metadados na resposta JSON. Padrão: `false`.

- **Resposta de Sucesso (JSON - 200 OK)**:
  ```json
  {
    "success": true,
    "total": 15234,
    "domains": [
      "domain1.com",
      "domain2.net",
      "...
    ],
    "timestamp": "2026-02-08T20:05:00.123456"
  }
  ```

- **Resposta de Sucesso (TXT - 200 OK)**:
  ```text
  domain1.com
  domain2.net
  ...
  ```

- **Resposta de Sucesso (RPZ - 200 OK)**:
  ```text
  domain1.com CNAME .
  domain2.net CNAME .
  ...
  ```

### `GET /domains/count`

Retorna apenas a contagem de domínios ativos. É mais leve que o endpoint `/domains`.

- **Resposta de Sucesso (200 OK)**:
  ```json
  {
    "success": true,
    "count": 15234,
    "timestamp": "2026-02-08T20:10:00.123456"
  }
  ```

### `POST /sync/start`

Inicia um processo de sincronização. O servidor registra o início e retorna um ID de sincronização para rastreamento.

- **Resposta de Sucesso (200 OK)**:
  ```json
  {
    "success": true,
    "sync_id": 123,
    "domains_count": 15234,
    "message": "Sincronização iniciada. Use /sync/complete para finalizar."
  }
  ```

### `POST /sync/complete`

Enviado pelo cliente para finalizar o processo de sincronização, informando o resultado.

- **Corpo da Requisição (JSON)**:
  ```json
  {
    "sync_id": 123,
    "domains_applied": 15230,
    "status": "success", // "success", "failed", "partial"
    "message": "Sincronização concluída com sucesso",
    "error_details": null, // Detalhes em caso de falha
    "duration_seconds": 45
  }
  ```

- **Resposta de Sucesso (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Sincronização registrada com sucesso",
    "client_status": "online"
  }
  ```

### `GET /sync/history`

Retorna o histórico de sincronizações do cliente autenticado.

- **Query Parameters**:
  - `limit` (opcional): Número de registros. Padrão: `50`.
  - `offset` (opcional): Deslocamento para paginação. Padrão: `0`.

- **Resposta de Sucesso (200 OK)**:
  ```json
  {
    "success": true,
    "client_id": 1,
    "client_name": "DNS-Server-01",
    "history": [
      {
        "id": 123,
        "status": "success",
        "domains_sent": 15234,
        "domains_applied": 15230,
        "synced_at": "2026-02-08T20:15:00.123456",
        ...
      }
    ],
    "total": 1
  }
  ```

### `GET /status`

Retorna um status detalhado sobre o cliente.

- **Resposta de Sucesso (200 OK)**:
  ```json
  {
    "success": true,
    "client": {
      "id": 1,
      "name": "DNS-Server-01",
      "status": "online",
      "last_heartbeat": "2026-02-08T20:00:00.123456",
      "last_sync": "2026-02-08T20:15:00.123456"
    },
    "last_sync": { ... }, // Objeto completo da última sincronização
    "current_domains_count": 15234,
    "server_time": "2026-02-08T20:20:00.123456"
  }
  ```

---

## 3. API Administrativa (`/api/v1/admin`)

Estes endpoints são para gerenciamento do sistema e requerem autenticação de administrador.

### 3.1. Gerenciamento de Domínios

- `GET /domains`: Lista domínios com paginação e busca.
- `POST /domains`: Adiciona um novo domínio.
- `POST /domains/bulk`: Adiciona múltiplos domínios de uma vez.
- `DELETE /domains/<int:domain_id>`: Remove um domínio (soft ou hard delete).
- `POST /domains/upload`: Faz upload de um arquivo PDF para extração de domínios.

### 3.2. Gerenciamento de Clientes DNS

- `GET /clients`: Lista todos os clientes DNS cadastrados.
- `POST /clients`: Cria um novo cliente DNS e gera uma API key.
- `GET /clients/<int:client_id>`: Obtém detalhes de um cliente específico.
- `POST /clients/<int:client_id>/regenerate-key`: Gera uma nova API key para um cliente.

### 3.3. Histórico e Estatísticas

- `GET /history/domains`: Retorna o histórico de alterações em domínios.
- `GET /history/syncs`: Retorna o histórico de todas as sincronizações de clientes.
- `GET /history/uploads`: Retorna o histórico de todos os uploads de PDF.
- `GET /stats`: Retorna estatísticas gerais do sistema (contagem de domínios, clientes, etc.).

---

## 4. Códigos de Erro Comuns

| Código | Mensagem | Descrição |
| :--- | :--- | :--- |
| `400 Bad Request` | `Domínio não fornecido` | Faltam dados obrigatórios na requisição. |
| `401 Unauthorized` | `API key inválida` | A API key está incorreta, ausente ou o cliente está inativo. |
| `403 Forbidden` | `Permissão negada` | O usuário autenticado não tem permissão para a ação. |
| `404 Not Found` | `Endpoint não encontrado` | A rota da API não existe. |
| `429 Too Many Requests` | `Rate limit exceeded` | O cliente excedeu o número de requisições permitidas por minuto. |
| `500 Internal Server Error` | `Erro interno do servidor` | Ocorreu um erro inesperado no servidor. Verificador. Verifique os logs. |
