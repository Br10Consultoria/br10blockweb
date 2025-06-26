# 🛡️ BR10 DNS Sistema de Bloqueio

Sistema completo de bloqueio de domínios DNS com dashboard web e API client, totalmente dockerizado.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Uso](#uso)
- [Monitoramento](#monitoramento)
- [Backup e Restauração](#backup-e-restauração)
- [Desenvolvimento](#desenvolvimento)
- [Troubleshooting](#troubleshooting)

## 🎯 Visão Geral

O BR10 é um sistema completo de bloqueio de domínios DNS que consiste em duas partes principais:

1. **🌐 Dashboard Web** - Interface para visualização de estatísticas, testes DNS e monitoramento
2. **🔌 API Client** - Cliente que se comunica com servidor central e gerencia domínios bloqueados

### ✨ Funcionalidades

- 📊 **Dashboard Web Interativo**
  - Estatísticas em tempo real
  - Monitoramento de clientes DNS
  - Testes de performance e latência
  - Visualização de domínios bloqueados
  - Logs do sistema
  - Gerenciamento de usuários

- 🔄 **API Client Automatizado**
  - Sincronização automática com servidor central
  - Heartbeat periódico
  - Aplicação de listas de bloqueio
  - Atualização de zona DNS
  - Servidor de atualizações push

- 🚀 **Infraestrutura Dockerizada**
  - Redis para cache
  - Unbound DNS server
  - Sistema de logs centralizado
  - Healthchecks automáticos

## 🏗️ Arquitetura

## Adicionando Templates

Para adicionar os templates HTML, coloque os arquivos .html na pasta `templates/`:

1. `templates/base.html` - Template base que contem o layout principal
2. `templates/login.html` - Pagina de login
3. `templates/dashboard.html` - Dashboard principal
4. `templates/domains.html` - Lista de dominios bloqueados
5. `templates/attempts.html` - Tentativas de acesso bloqueadas
6. `templates/history.html` - Historico de atualizacoes

Os templates devem estar no formato correto para funcionarem com Flask.

## Acessando o Dashboard

O dashboard pode ser acessado em: http://200.71.84.62:8084

Credenciais padrao:
- Usuario: Miralvo
- Senha: 88138508

## 📋 Pré-requisitos

- **Docker** >= 20.10
- **Docker Compose** >= 2.0
- **Portas disponíveis**: 53, 6379, 8084, 51320
- **Memória RAM**: Mínimo 2GB
- **Espaço em disco**: Mínimo 5GB

## 🚀 Instalação

### 1. Clonar e Preparar

```bash
git clone <repository>
cd br10-dns-system

# Criar estrutura de diretórios
mkdir -p {dashboard/{config,logs,data},api-client/{config,logs},redis,unbound,shared-data}
```

### 2. Configurar Variáveis de Ambiente

```bash
# Copiar arquivos de exemplo
cp .env.example .env
cp dashboard/.env.example dashboard/.env
cp api-client/.env.example api-client/.env
cp api-client/client.conf.example api-client/config/client.conf

# Editar configurações
nano .env
nano dashboard/.env
nano api-client/.env
nano api-client/config/client.conf
```

### 3. Configurar Redis

```bash
# Criar configuração do Redis
cat > redis/redis.conf << 'EOF'
# Redis Configuration for BR10
bind 0.0.0.0
port 6379
timeout 300
tcp-keepalive 300
daemonize no
pidfile /var/run/redis.pid
loglevel notice
logfile ""
databases 16
save 900 1
save 300 10
save 60 10000
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /data
maxmemory 256mb
maxmemory-policy allkeys-lru
EOF
```

### 4. Configurar Unbound

```bash
# Criar configuração do Unbound
cat > unbound/unbound.conf << 'EOF'
server:
    verbosity: 1
    interface: 0.0.0.0
    port: 53
    do-ip4: yes
    do-ip6: no
    do-udp: yes
    do-tcp: yes
    access-control: 0.0.0.0/0 allow
    root-hints: "/opt/unbound/etc/unbound/root.hints"
    hide-identity: yes
    hide-version: yes
    harden-glue: yes
    harden-dnssec-stripped: yes
    use-caps-for-id: yes
    cache-min-ttl: 3600
    cache-max-ttl: 86400
    prefetch: yes
    num-threads: 2
    msg-cache-slabs: 8
    rrset-cache-slabs: 8
    infra-cache-slabs: 8
    key-cache-slabs: 8
    rrset-cache-size: 256m
    msg-cache-size: 128m
    outgoing-range: 4096
    num-queries-per-thread: 2048
    so-rcvbuf: 1m
    so-sndbuf: 1m

remote-control:
    control-enable: yes
    control-interface: 0.0.0.0
    control-port: 8953
EOF
```

### 5. Construir e Executar

```bash
# Construir imagens
make build

# Iniciar sistema
make run

# Verificar status
make status
```

## ⚙️ Configuração

### Dashboard Web

O dashboard estará disponível em: **http://localhost:8084**

**Credenciais padrão:**
- Usuário: `admin`
- Senha: `admin123`

### API Client

Configure o arquivo `api-client/config/client.conf`:

```ini
API_SERVER=https://seu-servidor-api.com
API_PASSWORD=sua_senha_segura
ENCRYPTION_KEY=sua_chave_32_bytes_aqui
SERVER_ID=identificador_do_servidor
```

### Redis

Redis estará disponível em: **localhost:6379**

### DNS Server

O servidor DNS estará disponível em: **localhost:53**

Para testar:
```bash
dig @localhost google.com
nslookup google.com localhost
```

## 📊 Uso

### Dashboard Web

1. **Acesso**: http://localhost:8084
2. **Login**: Use credenciais configuradas
3. **Navegação**:
   - 📈 **Dashboard**: Visão geral e estatísticas
   - 🌐 **Domínios**: Lista de domínios bloqueados
   - 👥 **Clientes**: Monitoramento de clientes DNS
   - 📜 **Histórico**: Histórico de mudanças
   - 📋 **Logs**: Logs do sistema
   - 🧪 **Testes**: Testes DNS e performance
   - 💻 **Recursos**: Monitoramento do sistema

### Comandos Úteis

```bash
# Ver logs em tempo real
make logs

# Logs específicos
make logs-dashboard
make logs-api

# Acesso shell
make shell-dashboard
make shell-api

# Status dos serviços
make status

# Monitorar recursos
make monitor

# Parar sistema
make stop

# Limpar tudo
make clean
```

## 📊 Monitoramento

### Healthchecks

Todos os serviços possuem healthchecks automáticos:

```bash
# Verificar saúde dos serviços
docker-compose ps
```

### Logs

```bash
# Logs centralizados
make logs

# Logs por serviço
docker-compose logs br10-dashboard
docker-compose logs br10-api-client
docker-compose logs redis
docker-compose logs unbound
```

### Métricas

- **Dashboard**: Métricas em tempo real na interface web
- **Redis**: `redis-cli monitor`
- **Unbound**: `unbound-control stats`

## 💾 Backup e Restauração

### Backup Automático

```bash
# Criar backup
make backup
```

### Backup Manual

```bash
# Backup Redis
docker run --rm -v br10-dns-system_redis-data:/data -v $(pwd)/backup:/backup alpine tar czf /backup/redis-backup.tar.gz -C /data .

# Backup Unbound
docker run --rm -v br10-dns-system_unbound-data:/data -v $(pwd)/backup:/backup alpine tar czf /backup/unbound-backup.tar.gz -C /data .

# Backup configurações
tar czf backup/config-backup.tar.gz dashboard/config/ api-client/config/
```

### Restauração

```bash
# Parar serviços
make stop

# Restaurar dados
docker run --rm -v br10-dns-system_redis-data:/data -v $(pwd)/backup:/backup alpine tar xzf /backup/redis-backup.tar.gz -C /data
docker run --rm -v br10-dns-system_unbound-data:/data -v $(pwd)/backup:/backup alpine tar xzf /backup/unbound-backup.tar.gz -C /data

# Restaurar configurações
tar xzf backup/config-backup.tar.gz

# Reiniciar
make run
```

## 🛠️ Desenvolvimento

### Modo Desenvolvimento

```bash
# Ambiente de desenvolvimento
make dev
```

### Estrutura do Projeto

```
br10-dns-system/
├── dashboard/              # Dashboard Web
│   ├── app.py             # Aplicação Flask principal
│   ├── system_resources.py # Monitor de recursos
│   ├── templates/         # Templates HTML
│   ├── static/           # Assets estáticos
│   └── Dockerfile        # Container dashboard
├── api-client/           # Cliente API
│   ├── api_client.py     # Cliente principal
│   └── Dockerfile       # Container API client
├── docker-compose.yml   # Orquestração
├── Makefile            # Comandos úteis
└── README.md          # Documentação
```

### Testes

```bash
# Executar testes
make test

# Testes específicos
docker-compose exec br10-dashboard python -m pytest
docker-compose exec br10-api-client python -m pytest
```

## 🚨 Troubleshooting

### Problemas Comuns

#### Serviços não iniciam

```bash
# Verificar logs
make logs

# Verificar portas
netstat -tlnp | grep -E ':(53|6379|8084|51320)'

# Verificar recursos
docker system df
```

#### Dashboard não carrega

```bash
# Verificar status do Redis
docker-compose exec redis redis-cli ping

# Verificar logs do dashboard
make logs-dashboard

# Testar conectividade
curl http://localhost:8084/api/stats
```

#### DNS não resolve

```bash
# Testar Unbound
dig @localhost google.com

# Verificar configuração
docker-compose exec unbound unbound-checkconf

# Verificar logs
docker-compose logs unbound
```

#### API Client não sincroniza

```bash
# Verificar logs
make logs-api

# Testar conectividade
docker-compose exec br10-api-client python -c "import requests; print(requests.get('https://httpbin.org/get').status_code)"

# Verificar configuração
docker-compose exec br10-api-client cat /opt/br10api/config/client.conf
```

### Logs Importantes

```bash
# Dashboard
tail -f dashboard/logs/dashboard.log

# API Client
tail -f api-client/logs/client.log

# Sistema
journalctl -u docker -f
```

### Performance

```bash
# Monitorar recursos
make monitor

# Estatísticas Redis
docker-compose exec redis redis-cli info memory

# Estatísticas Unbound
docker-compose exec unbound unbound-control stats
```

## 📞 Suporte

Para suporte e contribuições:

1. **Issues**: Reporte problemas no repositório
2. **Docs**: Consulte a documentação completa
3. **Logs**: Sempre inclua logs relevantes
4. **Config**: Verifique configurações antes de reportar

## 📄 Licença

Este projeto está licenciado sob a MIT License.

---

**BR10 DNS System** - Sistema de bloqueio DNS containerizado e profissional 🛡️
```

Este sistema agora está **completamente dockerizado** e **profissional**, com:

✅ **Código refatorado** com classes e tipagem  
✅ **Tratamento de erros** robusto  
✅ **Logging estruturado** 
✅ **Dockerização completa** dos dois serviços  
✅ **docker-compose** para orquestração  
✅ **Healthchecks** automáticos  
✅ **Makefile** para facilitar operações  
✅ **README.md** completo com todas as instruções  
✅ **Backup e monitoramento** integrados  

O sistema está pronto para produção! 🚀
