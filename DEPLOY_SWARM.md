# Deploy no Docker Swarm - BR10 Block Web

Guia completo para fazer deploy do BR10 Block Web em um cluster Docker Swarm com Traefik.

---

## 🐝 Pré-requisitos

- Docker Swarm inicializado
- Traefik rodando como serviço no Swarm
- Rede `network_public` criada no Swarm
- Domínio apontando para o servidor

---

## 1. Preparar o Ambiente

### Verificar se o Swarm está ativo:

```bash
docker info | grep Swarm
# Deve retornar: Swarm: active
```

### Se não estiver ativo, inicializar:

```bash
docker swarm init
```

### Verificar a rede `network_public`:

```bash
docker network ls | grep network_public
```

### Se não existir, criar:

```bash
docker network create \
  --driver overlay \
  --attachable \
  network_public
```

---

## 2. Construir a Imagem

Antes de fazer deploy no Swarm, você precisa construir a imagem:

```bash
cd /home/br10blockweb

# Construir a imagem
docker build -t br10blockweb:latest .

# Verificar
docker images | grep br10blockweb
```

**Importante**: Se você tem múltiplos nós no Swarm, a imagem precisa estar disponível em todos os nós. Opções:

1. **Docker Registry privado** (recomendado para produção)
2. **Docker Hub**
3. **Construir em cada nó** (para testes)

---

## 3. Configurar Variáveis de Ambiente

```bash
# Criar arquivo .env se não existir
cp .env.example .env

# Editar
nano .env
```

**Configurações importantes:**

```env
# Flask
FLASK_ENV=production
SECRET_KEY=sua_chave_super_secreta_aqui_mude
DEBUG=False

# Traefik
TRAEFIK_DOMAIN=block.br10ia.ia.br

# PostgreSQL
DB_NAME=br10blockweb
DB_USER=br10user
DB_PASSWORD=senha_forte_aqui

# Redis (deixe em branco se não tiver senha)
REDIS_PASSWORD=
```

---

## 4. Deploy da Stack

### Fazer deploy usando o arquivo Swarm:

```bash
docker stack deploy -c docker-compose.swarm.yml br10
```

### Verificar o status:

```bash
# Listar serviços
docker stack services br10

# Listar containers
docker stack ps br10

# Logs do dashboard
docker service logs -f br10_dashboard
```

---

## 5. Verificar Deployment

### Verificar se todos os serviços estão rodando:

```bash
docker stack services br10
```

Você deve ver algo como:

```
ID             NAME              MODE         REPLICAS   IMAGE                    PORTS
abc123         br10_postgres     replicated   1/1        postgres:16-alpine
def456         br10_redis        replicated   1/1        redis:7-alpine
ghi789         br10_dashboard    replicated   1/1        br10blockweb:latest
```

### Verificar logs:

```bash
# Dashboard
docker service logs br10_dashboard

# PostgreSQL
docker service logs br10_postgres

# Redis
docker service logs br10_redis
```

### Verificar healthcheck:

```bash
# Obter o ID do container do dashboard
CONTAINER_ID=$(docker ps | grep br10_dashboard | awk '{print $1}')

# Verificar health
docker inspect $CONTAINER_ID | grep -A 10 Health
```

---

## 6. Inicializar o Banco de Dados

Após o deploy, você precisa inicializar o banco:

```bash
# Obter o ID do container do dashboard
CONTAINER_ID=$(docker ps | grep br10_dashboard | awk '{print $1}')

# Executar script de inicialização
docker exec -it $CONTAINER_ID python3 init_db.py
```

Isso vai:
- Criar as tabelas
- Criar usuário admin padrão (admin/admin)
- Popular dados iniciais

**⚠️ IMPORTANTE**: Mude a senha do admin após o primeiro login!

---

## 7. Testar Acesso

### Via curl:

```bash
# HTTP (deve redirecionar para HTTPS)
curl -I http://block.br10ia.ia.br

# HTTPS
curl -I https://block.br10ia.ia.br

# Healthcheck
curl https://block.br10ia.ia.br/health
```

### Via navegador:

Acesse: `https://block.br10ia.ia.br`

Login padrão:
- **Usuário**: admin
- **Senha**: admin

---

## 8. Atualizar a Stack

Quando você fizer mudanças no código:

```bash
# 1. Reconstruir a imagem
docker build -t br10blockweb:latest .

# 2. Atualizar o serviço
docker service update --image br10blockweb:latest br10_dashboard

# Ou atualizar toda a stack
docker stack deploy -c docker-compose.swarm.yml br10
```

---

## 9. Escalar Serviços

### Escalar o dashboard (múltiplas réplicas):

```bash
docker service scale br10_dashboard=3
```

### Verificar:

```bash
docker service ps br10_dashboard
```

**Nota**: O PostgreSQL e Redis não devem ser escalados dessa forma (use replicação nativa).

---

## 10. Backup e Restore

### Backup do PostgreSQL:

```bash
# Obter o ID do container do postgres
POSTGRES_ID=$(docker ps | grep br10_postgres | awk '{print $1}')

# Fazer backup
docker exec $POSTGRES_ID pg_dump -U br10user br10blockweb > backup_$(date +%Y%m%d).sql

# Ou usar o diretório de backups montado
docker exec $POSTGRES_ID pg_dump -U br10user br10blockweb > /backups/backup_$(date +%Y%m%d).sql
```

### Restore:

```bash
# Restaurar backup
docker exec -i $POSTGRES_ID psql -U br10user br10blockweb < backup_20260208.sql
```

---

## 11. Remover a Stack

```bash
# Remover todos os serviços
docker stack rm br10

# Verificar
docker stack ls
```

**Nota**: Os volumes persistem após remover a stack. Para remover volumes:

```bash
docker volume ls | grep br10
docker volume rm br10_postgres-data
docker volume rm br10_redis-data
```

---

## 12. Troubleshooting

### Serviço não inicia:

```bash
# Ver logs detalhados
docker service logs --tail 100 br10_dashboard

# Ver eventos
docker service ps --no-trunc br10_dashboard
```

### Container reiniciando constantemente:

```bash
# Verificar healthcheck
docker inspect $(docker ps -q -f name=br10_dashboard) | grep -A 20 Health

# Verificar se o banco está acessível
docker exec -it $(docker ps -q -f name=br10_dashboard) ping postgres
```

### Traefik não encontra o serviço:

```bash
# Verificar se o container está na rede correta
docker inspect $(docker ps -q -f name=br10_dashboard) | grep -A 10 Networks

# Verificar labels
docker service inspect br10_dashboard | grep -A 50 Labels

# Ver logs do Traefik
docker service logs traefik | grep br10blockweb
```

### Certificado SSL não é gerado:

```bash
# Verificar logs do Traefik
docker service logs traefik | grep -i acme

# Verificar se o domínio resolve
nslookup block.br10ia.ia.br

# Verificar se a porta 80 está acessível
curl -I http://block.br10ia.ia.br/.well-known/acme-challenge/test
```

---

## 13. Monitoramento

### Ver recursos utilizados:

```bash
# CPU e memória de todos os serviços
docker stats

# Apenas o dashboard
docker stats $(docker ps -q -f name=br10_dashboard)
```

### Ver logs em tempo real:

```bash
# Todos os serviços
docker service logs -f br10_dashboard
docker service logs -f br10_postgres
docker service logs -f br10_redis
```

---

## 14. Configuração de Produção

### Recomendações:

1. **Secrets do Docker** para senhas:

```bash
# Criar secret
echo "senha_super_secreta" | docker secret create db_password -

# Usar no docker-compose.swarm.yml
secrets:
  - db_password

environment:
  DB_PASSWORD_FILE: /run/secrets/db_password
```

2. **Limites de recursos**:

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
    reservations:
      cpus: '0.5'
      memory: 512M
```

3. **Placement constraints**:

```yaml
deploy:
  placement:
    constraints:
      - node.role == worker
      - node.labels.type == web
```

4. **Update config**:

```yaml
deploy:
  update_config:
    parallelism: 1
    delay: 10s
    failure_action: rollback
    order: start-first
```

---

## 15. Checklist de Deploy

- [ ] Swarm inicializado
- [ ] Rede `network_public` criada
- [ ] Traefik rodando
- [ ] Imagem construída
- [ ] Arquivo `.env` configurado
- [ ] Domínio apontando para o servidor
- [ ] Stack deployed: `docker stack deploy -c docker-compose.swarm.yml br10`
- [ ] Banco inicializado: `docker exec ... python3 init_db.py`
- [ ] Senha do admin alterada
- [ ] Backup configurado
- [ ] Monitoramento ativo
- [ ] SSL funcionando

---

## 16. Comandos Úteis

```bash
# Ver todas as stacks
docker stack ls

# Ver serviços de uma stack
docker stack services br10

# Ver containers de uma stack
docker stack ps br10

# Ver logs de um serviço
docker service logs -f br10_dashboard

# Atualizar um serviço
docker service update br10_dashboard

# Escalar um serviço
docker service scale br10_dashboard=3

# Remover uma stack
docker stack rm br10

# Ver redes
docker network ls

# Inspecionar rede
docker network inspect network_public

# Ver volumes
docker volume ls

# Limpar volumes não usados
docker volume prune
```

---

**Pronto!** Seu BR10 Block Web está rodando no Docker Swarm com alta disponibilidade. 🚀

---

*Desenvolvido pelo BR10 Team - 2026*
