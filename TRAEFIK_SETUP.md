# Guia de Configuração do Traefik - BR10 Block Web

Este guia explica como configurar o Traefik como proxy reverso para o BR10 Block Web com SSL automático via Let's Encrypt.

---

## 1. Pré-requisitos

- Docker e Docker Compose instalados
- Traefik já rodando no servidor (como serviço ou container)
- Rede `network_public` criada no Docker
- Domínio apontando para o servidor (ex: `block.br10ia.ia.br`)

---

## 2. Verificar Rede do Traefik

O Traefik precisa de uma rede externa compartilhada para se comunicar com os containers.

### Verificar se a rede existe:

```bash
docker network ls | grep network_public
```

### Se não existir, criar a rede:

```bash
docker network create network_public
```

---

## 3. Configurar Variáveis de Ambiente

Edite o arquivo `.env` e configure o domínio:

```bash
# Copiar exemplo se ainda não tiver
cp .env.example .env

# Editar
nano .env
```

**Adicione ou edite:**

```env
# Traefik (Proxy Reverso)
TRAEFIK_DOMAIN=block.br10ia.ia.br
```

**Substitua** `block.br10ia.ia.br` pelo seu domínio real.

---

## 4. Entender as Labels do Traefik

O `docker-compose.yml` já está configurado com as labels necessárias. Aqui está o que cada uma faz:

### **Habilitar Traefik**
```yaml
- traefik.enable=true
```
Informa ao Traefik que este container deve ser gerenciado.

### **Configurar Rede**
```yaml
- traefik.docker.network=network_public
```
Define qual rede o Traefik deve usar para se conectar ao container.

### **Router HTTP (Redirecionar para HTTPS)**
```yaml
- traefik.http.routers.br10blockweb-http.rule=Host(`block.br10ia.ia.br`)
- traefik.http.routers.br10blockweb-http.entrypoints=web
- traefik.http.routers.br10blockweb-http.middlewares=br10blockweb-redirect-https
```
Captura requisições HTTP e redireciona para HTTPS.

### **Middleware de Redirecionamento**
```yaml
- traefik.http.middlewares.br10blockweb-redirect-https.redirectscheme.scheme=https
- traefik.http.middlewares.br10blockweb-redirect-https.redirectscheme.permanent=true
```
Cria um middleware que força redirecionamento permanente (301) para HTTPS.

### **Router HTTPS**
```yaml
- traefik.http.routers.br10blockweb.rule=Host(`block.br10ia.ia.br`)
- traefik.http.routers.br10blockweb.entrypoints=websecure
- traefik.http.routers.br10blockweb.tls=true
- traefik.http.routers.br10blockweb.tls.certresolver=letsencrypt
```
Configura o router HTTPS com SSL automático via Let's Encrypt.

### **Service (Porta do Container)**
```yaml
- traefik.http.services.br10blockweb.loadbalancer.server.port=8084
- traefik.http.services.br10blockweb.loadbalancer.passhostheader=true
```
Define a porta interna do container (8084) e mantém o header Host original.

### **Middleware SSL Headers**
```yaml
- traefik.http.middlewares.br10blockweb-sslheader.headers.customrequestheaders.X-Forwarded-Proto=https
- traefik.http.middlewares.br10blockweb-sslheader.headers.customrequestheaders.X-Forwarded-Host=block.br10ia.ia.br
- traefik.http.middlewares.br10blockweb-sslheader.headers.customrequestheaders.X-Forwarded-Port=443
```
Adiciona headers para que o Flask saiba que está atrás de um proxy HTTPS.

### **Headers de Segurança (Opcional)**
```yaml
- traefik.http.middlewares.br10blockweb-security.headers.stsSeconds=31536000
- traefik.http.middlewares.br10blockweb-security.headers.stsIncludeSubdomains=true
- traefik.http.middlewares.br10blockweb-security.headers.contentTypeNosniff=true
- traefik.http.middlewares.br10blockweb-security.headers.browserXssFilter=true
- traefik.http.middlewares.br10blockweb-security.headers.frameDeny=true
```
Adiciona headers de segurança (HSTS, XSS Protection, etc).

---

## 5. Configuração do Traefik (Referência)

Se você ainda não tem o Traefik configurado, aqui está um exemplo básico:

### `docker-compose.yml` do Traefik:

```yaml
version: '3.8'

services:
  traefik:
    image: traefik:v2.10
    container_name: traefik
    command:
      # API e Dashboard
      - --api.dashboard=true
      - --api.insecure=false
      
      # Providers
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --providers.docker.network=network_public
      
      # Entrypoints
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      
      # Let's Encrypt
      - --certificatesresolvers.letsencrypt.acme.email=seu-email@exemplo.com
      - --certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json
      - --certificatesresolvers.letsencrypt.acme.httpchallenge=true
      - --certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web
      
      # Logs
      - --log.level=INFO
      - --accesslog=true
    
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"  # Dashboard (proteja em produção!)
    
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik-letsencrypt:/letsencrypt
    
    networks:
      - network_public
    
    restart: unless-stopped

networks:
  network_public:
    external: true

volumes:
  traefik-letsencrypt:
    driver: local
```

**Importante**: Substitua `seu-email@exemplo.com` pelo seu email real.

---

## 6. Subir o BR10 Block Web

Agora que tudo está configurado, suba o BR10 Block Web:

```bash
cd /caminho/para/br10blockweb

# Parar se estiver rodando
docker-compose down

# Subir com as novas configurações
docker-compose up -d

# Verificar logs
docker-compose logs -f dashboard
```

---

## 7. Verificar Configuração

### Verificar se o container está na rede correta:

```bash
docker inspect br10-dashboard | grep -A 10 Networks
```

Você deve ver tanto `br10-network` quanto `network_public`.

### Verificar logs do Traefik:

```bash
docker logs traefik | grep br10blockweb
```

Você deve ver mensagens sobre o router e service sendo criados.

### Testar acesso:

```bash
# HTTP (deve redirecionar para HTTPS)
curl -I http://block.br10ia.ia.br

# HTTPS
curl -I https://block.br10ia.ia.br
```

---

## 8. Configurar Flask para Proxy

O Flask precisa saber que está atrás de um proxy. Adicione ao `backend/app.py`:

```python
from werkzeug.middleware.proxy_fix import ProxyFix

# Após criar a app
app = create_app()

# Adicionar ProxyFix
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_port=1,
    x_prefix=0
)
```

Isso já está incluído no código refatorado, mas verifique se está presente.

---

## 9. Troubleshooting

### Problema: "Gateway Timeout" ou "Bad Gateway"

**Causa**: Traefik não consegue se conectar ao container.

**Solução**:
```bash
# Verificar se o container está rodando
docker ps | grep br10-dashboard

# Verificar healthcheck
docker inspect br10-dashboard | grep -A 5 Health

# Verificar logs
docker-compose logs dashboard
```

### Problema: Certificado SSL não é gerado

**Causa**: Let's Encrypt não consegue validar o domínio.

**Solução**:
- Verifique se o domínio aponta para o IP do servidor
- Verifique se a porta 80 está acessível externamente
- Verifique logs do Traefik: `docker logs traefik | grep acme`

### Problema: Redirecionamento infinito

**Causa**: Flask não reconhece que está atrás de HTTPS.

**Solução**:
- Verifique se o `ProxyFix` está configurado no Flask
- Verifique se os headers `X-Forwarded-*` estão sendo enviados

### Problema: "404 Not Found"

**Causa**: Traefik não encontrou o router.

**Solução**:
```bash
# Verificar labels do container
docker inspect br10-dashboard | grep -A 50 Labels

# Verificar se o domínio no .env está correto
cat .env | grep TRAEFIK_DOMAIN

# Recriar container
docker-compose up -d --force-recreate dashboard
```

---

## 10. Remover Exposição de Portas (Opcional)

Após configurar o Traefik, você pode remover a exposição direta das portas no `docker-compose.yml`:

**Antes:**
```yaml
ports:
  - "8084:8084"
```

**Depois (comentar ou remover):**
```yaml
# ports:
#   - "8084:8084"
```

Isso garante que o acesso só seja possível via Traefik.

---

## 11. Configuração para Docker Swarm

Se você está usando Docker Swarm (indicado pelo `traefik.swarm.network` no seu exemplo), use:

```yaml
labels:
  - traefik.enable=true
  - traefik.swarm.network=network_public
  - traefik.http.routers.br10blockweb.rule=Host(`block.br10ia.ia.br`)
  - traefik.http.routers.br10blockweb.entrypoints=websecure
  - traefik.http.routers.br10blockweb.tls.certresolver=letsencrypt
  - traefik.http.routers.br10blockweb.service=br10blockweb
  - traefik.http.services.br10blockweb.loadbalancer.server.port=8084
  - traefik.http.services.br10blockweb.loadbalancer.passhostheader=true
  - traefik.http.middlewares.br10blockweb-sslheader.headers.customrequestheaders.X-Forwarded-Proto=https
  - traefik.http.routers.br10blockweb.middlewares=br10blockweb-sslheader@swarm
```

**Diferenças para Swarm**:
- Use `traefik.swarm.network` em vez de `traefik.docker.network`
- Adicione `@swarm` ao final dos middlewares: `middleware-name@swarm`

---

## 12. Resumo dos Passos

1. ✅ Criar rede `network_public`
2. ✅ Configurar `TRAEFIK_DOMAIN` no `.env`
3. ✅ Adicionar labels do Traefik no `docker-compose.yml` (já feito)
4. ✅ Subir o container: `docker-compose up -d`
5. ✅ Verificar logs e acesso
6. ✅ Testar HTTP → HTTPS redirect
7. ✅ Verificar certificado SSL

---

## 13. Checklist de Segurança

- [ ] Domínio configurado corretamente
- [ ] Certificado SSL válido (Let's Encrypt)
- [ ] Redirecionamento HTTP → HTTPS funcionando
- [ ] Headers de segurança configurados
- [ ] Porta 8084 não exposta diretamente (opcional)
- [ ] Dashboard do Traefik protegido (se habilitado)
- [ ] Logs sendo monitorados

---

**Pronto!** Seu BR10 Block Web agora está acessível via HTTPS com certificado SSL automático. 🎉

---

*Desenvolvido pelo BR10 Team - 2026*
