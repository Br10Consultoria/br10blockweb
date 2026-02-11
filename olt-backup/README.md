# OLT Backup Docker

Sistema automatizado de backup de OLTs **Datacom**, **ZTE** e **ZTE Titan** via Telnet, com envio de notificações e arquivos para o **Telegram**. Executa dentro de um container Docker com agendamento via **cron** (13:00 e 22:00 diariamente).

---

## Estrutura do Projeto

```
olt-backup-docker/
├── backup_olts.py        # Script principal (backup + Telegram)
├── olts_config.py        # Configuração das OLTs (lê do .env)
├── crontab               # Agendamento cron (13h e 22h)
├── entrypoint.sh         # Script de inicialização do container
├── Dockerfile            # Imagem Docker
├── docker-compose.yml    # Orquestração do container
├── requirements.txt      # Dependências Python
├── .env                  # Credenciais reais (NÃO versionar)
├── .env.example          # Modelo de credenciais
├── .gitignore            # Ignora .env e arquivos sensíveis
└── .dockerignore         # Ignora arquivos desnecessários no build
```

---

## Pré-requisitos

- **Docker** e **Docker Compose** instalados no servidor.
- O servidor deve ter acesso de rede às OLTs (IPs `10.x.x.x`) e aos servidores TFTP/FTP.
- Usar `network_mode: host` no `docker-compose.yml` (já configurado) para que o container acesse a rede local.

---

## Instalação e Uso

### 1. Clonar o repositório

```bash
git clone https://github.com/Br10Consultoria/br10blockweb.git
cd br10blockweb
```

### 2. Configurar credenciais

```bash
cp .env.example .env
nano .env   # Preencha com as credenciais reais
```

### 3. Subir o container

```bash
docker compose up -d --build
```

### 4. Verificar logs

```bash
# Logs do container
docker compose logs -f olt-backup

# Logs do cron dentro do container
docker exec olt-backup tail -f /var/log/cron.log
```

### 5. Executar backup manualmente (teste)

```bash
docker exec olt-backup python3 /app/backup_olts.py
```

### 6. Parar o container

```bash
docker compose down
```

---

## Agendamento

O cron está configurado para executar o script de backup nos seguintes horários (timezone `America/Bahia`):

| Horário | Cron Expression       |
|---------|-----------------------|
| 13:00   | `0 13 * * *`          |
| 22:00   | `0 22 * * *`          |

Para alterar os horários, edite o arquivo `crontab` e reconstrua o container.

---

## OLTs Configuradas

| Nome                  | IP             | Tipo       |
|-----------------------|----------------|------------|
| OURICANGAS            | 10.100.10.210  | Datacom    |
| OURICANGUINHA         | 10.10.10.30    | Datacom    |
| POP_FORMIGA           | 10.10.10.6     | Datacom    |
| POP_SAO_FELIX         | 10.100.10.14   | Datacom    |
| POP_PEDRAO_GPON       | 10.100.10.26   | Datacom    |
| OLT_CATU_DATACOM      | 10.10.10.10    | Datacom    |
| POP_BARREIRO_02_38    | 10.10.10.38    | Datacom    |
| POP_BARREIRO_34       | 10.10.10.34    | Datacom    |
| CATU_04               | 10.10.10.242   | Datacom    |
| CATU_03               | 10.10.10.246   | Datacom    |
| PEDRO_BRAGA_NOVA      | 10.100.10.54   | Datacom    |
| ZTE_ARAMARI           | 10.100.11.2    | ZTE        |
| ZTE_CAMBUBE           | 10.11.10.30    | ZTE        |
| ZTE_TITAN_CANAVIEIRAS | 10.11.10.10    | ZTE Titan  |

---

## Notificações Telegram

Ao final de cada execução, o bot envia ao grupo/chat configurado:

- **Resumo** com a lista de OLTs com sucesso e falha.
- **Arquivos de backup** encontrados no diretório local `/app/backups` (se houver).

---

## Variáveis de Ambiente

Todas as credenciais e configurações sensíveis ficam no arquivo `.env`, que **não é versionado** no Git. Consulte `.env.example` para a lista completa de variáveis.
