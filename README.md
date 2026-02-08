# BR10 Block Web - v3.0.0

**Sistema de Gerenciamento Centralizado de Listas de Bloqueio de Domínios**

---

## 1. Visão Geral

O **BR10 Block Web** é um sistema robusto e centralizado para gerenciar listas de bloqueio de domínios (blocklists) e distribuí-las para múltiplos clientes DNS, como Unbound, BIND, ou qualquer sistema que possa consumir uma API REST. O sistema foi completamente refatorado para oferecer alta performance, escalabilidade e um conjunto completo de funcionalidades para automação e auditoria.

Esta nova versão (v3.0.0) substitui a implementação monolítica anterior por uma arquitetura moderna baseada em **Python/Flask**, **PostgreSQL** e **Redis**, totalmente containerizada com **Docker**.

### 1.1. Principais Funcionalidades

- **Dashboard Centralizado**: Interface web para gerenciamento completo de domínios, clientes, histórico e configurações.
- **Upload de PDF**: Extração automática de domínios a partir de arquivos PDF, com detecção de duplicatas e preview.
- **API REST para Clientes**: Endpoints seguros para clientes DNS buscarem a lista de domínios em diferentes formatos (JSON, TXT, RPZ).
- **API Administrativa**: Endpoints para automação de tarefas administrativas, como adicionar domínios, gerenciar clientes e consultar estatísticas.
- **Sincronização com Feedback**: Mecanismo de sincronização que rastreia o status de aplicação da lista em cada cliente.
- **Histórico e Auditoria**: Registro detalhado de todas as operações: adições/remoções de domínios, uploads de PDF, sincronizações de clientes e requisições da API.
- **Cache com Redis**: Cache de alta performance para listas de domínios e estatísticas, reduzindo a carga no banco de dados e garantindo baixa latência.
- **Rate Limiting**: Proteção contra abuso da API por cliente.
- **Gerenciamento de Clientes DNS**: Cadastro de clientes com geração de API keys individuais e monitoramento de status (online/offline).

## 2. Arquitetura do Sistema

O sistema é composto por três componentes principais que rodam em containers Docker, orquestrados pelo Docker Compose.

```mermaid
graph TD
    subgraph "Ambiente Docker"
        subgraph "Servidor Web (Flask)"
            A[Frontend - HTML/JS/CSS]
            B[Backend - Python/Flask]
            C[API REST]
        end

        subgraph "Banco de Dados"
            D[PostgreSQL 16]
        end

        subgraph "Cache & Fila"
            E[Redis 7]
        end
    end

    subgraph "Clientes DNS"
        F[Cliente 1 (Unbound)]
        G[Cliente 2 (BIND)]
        H[Cliente N...]
    end

    subgraph "Administrador"
        I[Admin Web Browser]
    end

    I -- HTTPS --> A
    B -- Conexão TCP --> D
    B -- Conexão TCP --> E
    C -- HTTPS/API Key --> F
    C -- HTTPS/API Key --> G
    C -- HTTPS/API Key --> H
```

| Componente | Tecnologia | Responsabilidade |
| :--- | :--- | :--- |
| **Servidor Web** | Python 3.11, Flask | Fornece a interface web (frontend), a lógica de negócio e as APIs (backend). |
| **Banco de Dados** | PostgreSQL 16 | Armazena de forma persistente todos os dados: domínios, usuários, clientes, histórico, etc. |
| **Cache** | Redis 7 | Armazena em memória a lista de domínios ativos, estatísticas e sessões para acesso rápido. |
| **Clientes DNS** | - | Sistemas externos (ex: Unbound) que consomem a API para obter a lista de bloqueio. |

### 2.1. Fluxo de Dados (Upload de PDF)

1.  **Upload**: O administrador faz o upload de um arquivo PDF pela interface web.
2.  **Validação**: O sistema valida o arquivo (tamanho, tipo) e o salva temporariamente.
3.  **Hash**: Um hash SHA-256 do arquivo é calculado para verificar se ele já foi processado.
4.  **Extração**: O serviço `PDFExtractor` usa `pdfplumber` (e `PyPDF2` como fallback) para extrair todos os domínios do texto do PDF.
5.  **Adição em Massa**: Os domínios extraídos são adicionados ao banco de dados PostgreSQL. O sistema detecta e ignora duplicatas.
6.  **Histórico**: Um registro do upload e de cada novo domínio adicionado é criado nas tabelas de histórico.
7.  **Invalidação de Cache**: O cache da lista de domínios no Redis é invalidado para forçar uma recarga na próxima requisição.

### 2.2. Fluxo de Dados (Sincronização de Cliente)

1.  **Requisição**: Um cliente DNS (ex: um script rodando em um servidor Unbound) faz uma requisição para `GET /api/v1/client/domains`.
2.  **Autenticação**: A API key enviada no header é validada. O cliente correspondente é identificado.
3.  **Cache Check**: O sistema verifica se a lista de domínios está no cache do Redis.
    -   **Cache Hit**: Se estiver, a lista é retornada instantaneamente.
    -   **Cache Miss**: Se não estiver, a lista é buscada no PostgreSQL, salva no Redis com um TTL (Time-To-Live) e então retornada.
4.  **Feedback (Opcional)**: O cliente pode informar o status da aplicação da lista através do endpoint `POST /api/v1/client/sync/complete`, permitindo auditoria sobre a distribuição.

## 3. Estrutura do Projeto

O projeto foi organizado de forma modular para facilitar a manutenção e o desenvolvimento.

```
/br10blockweb
├── backend/
│   ├── api/                # Blueprints da API (client e admin)
│   ├── database/           # Conexão com DB e migrações SQL
│   ├── models/             # Modelos de dados (classes Python)
│   ├── services/           # Lógica de negócio (PDF, cache, sync)
│   ├── utils/              # Funções auxiliares e validadores
│   ├── app.py              # Aplicação Flask principal
│   └── config.py           # Configurações
├── frontend/
│   ├── static/             # Arquivos CSS, JS, imagens
│   └── templates/          # Templates HTML (Jinja2)
├── data/
│   ├── uploads/            # PDFs enviados
│   └── exports/            # Arquivos exportados
├── .env.example            # Exemplo de variáveis de ambiente
├── docker-compose.yml      # Orquestração dos containers
├── Dockerfile              # Definição do container da aplicação
├── requirements.txt        # Dependências Python
├── README.md               # Esta documentação
└── API_DOCS.md             # Documentação da API
```

## 4. Como Executar (Ambiente de Desenvolvimento)

**Pré-requisitos**: Docker e Docker Compose instalados.

1.  **Clonar o Repositório**
    ```bash
    git clone https://github.com/Br10Consultoria/br10blockweb.git
    cd br10blockweb
    ```

2.  **Configurar Variáveis de Ambiente**
    Copie o arquivo de exemplo e edite-o se necessário. As senhas e a secret key são geradas aleatoriamente por padrão no `docker-compose.yml`.
    ```bash
    cp .env.example .env
    ```

3.  **Subir os Containers**
    Use o Docker Compose para construir e iniciar todos os serviços.
    ```bash
    docker-compose up --build -d
    ```
    O `-d` executa os containers em background.

4.  **Acessar a Aplicação**
    A aplicação estará disponível em [http://localhost:5000](http://localhost:5000).

5.  **Primeiro Acesso**
    -   O sistema não cria um usuário padrão. Você precisará criar um.
    -   Execute o seguinte comando para criar um usuário administrador:
        ```bash
        docker-compose exec web python3 -c "from backend.models.user import User; User.create(\"admin\", \"SENHA_FORTE_AQUI\", role=\"admin\")"
        ```
    -   **Substitua `SENHA_FORTE_AQUI` por uma senha segura.**
    -   Agora você pode fazer login com `admin` e a senha que você definiu.

6.  **Parar a Aplicação**
    ```bash
    docker-compose down
    ```

## 5. Documentação da API

A documentação detalhada da API foi movida para um arquivo separado. Por favor, consulte **[API_DOCS.md](API_DOCS.md)**.

## 6. Considerações de Segurança

- **Variáveis de Ambiente**: Nunca comite senhas ou chaves secretas no código. Use o arquivo `.env`.
- **Senhas de Usuário**: As senhas são armazenadas com hash (SHA-256).
- **API Keys**: Cada cliente DNS possui uma API key única e pode ser desativado a qualquer momento.
- **Validação de Uploads**: O sistema valida a extensão e o tamanho dos arquivos PDF para prevenir uploads maliciosos.
- **Cross-Site Scripting (XSS)**: O uso do motor de templates Jinja2 com auto-escaping padrão ajuda a mitigar riscos de XSS.

---

*Desenvolvido pelo BR10 Team - 2026*
