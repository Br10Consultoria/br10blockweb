#!/bin/bash
# =============================================================================
# BR10 Block Web - Deploy do SERVIDOR via Docker Compose
# =============================================================================
# Uso:
#   sudo bash deploy_server.sh
#
# O script:
#   1. Instala Docker e Docker Compose (se necessário)
#   2. Cria o arquivo .env com senhas geradas automaticamente
#   3. Sobe os containers (postgres, redis, app, nginx)
#   4. Inicializa o banco de dados e cria o usuário admin
#
# Autor: BR10 Team
# Versão: 3.0.1
# =============================================================================

set -euo pipefail

# --- Cores ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[AVISO]${NC} $*"; }
error()   { echo -e "${RED}[ERRO]${NC} $*"; exit 1; }
step()    { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }

banner() {
    echo -e "${BLUE}"
    echo "  ██████╗ ██████╗  ██╗ ██████╗     ██████╗ ██╗      ██████╗  ██████╗██╗  ██╗"
    echo "  ██╔══██╗██╔══██╗███║██╔═████╗    ██╔══██╗██║     ██╔═══██╗██╔════╝██║ ██╔╝"
    echo "  ██████╔╝██████╔╝╚██║██║██╔██║    ██████╔╝██║     ██║   ██║██║     █████╔╝ "
    echo "  ██╔══██╗██╔══██╗ ██║████╔╝██║    ██╔══██╗██║     ██║   ██║██║     ██╔═██╗ "
    echo "  ██████╔╝██║  ██║ ██║╚██████╔╝    ██████╔╝███████╗╚██████╔╝╚██████╗██║  ██╗"
    echo "  ╚═════╝ ╚═╝  ╚═╝ ╚═╝ ╚═════╝    ╚═════╝ ╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝"
    echo -e "${NC}"
    echo "  Deploy do Servidor Central — Docker Compose"
    echo "  ─────────────────────────────────────────────────────────────────────────"
}

check_root() {
    [[ $EUID -eq 0 ]] || error "Execute como root: sudo bash $0"
}

install_docker() {
    step "Verificando Docker"
    if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
        success "Docker $(docker --version | cut -d' ' -f3 | tr -d ',') já instalado"
        return
    fi

    info "Instalando Docker..."
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg lsb-release

    # Adicionar repositório oficial do Docker
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null || \
    curl -fsSL https://download.docker.com/linux/debian/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    DISTRO_ID=$(. /etc/os-release && echo "$ID")
    DISTRO_CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME")

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/${DISTRO_ID} ${DISTRO_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    systemctl enable docker
    systemctl start docker
    success "Docker instalado com sucesso"
}

setup_env() {
    step "Configurando variáveis de ambiente"
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    if [[ -f "${SCRIPT_DIR}/.env" ]]; then
        warn "Arquivo .env já existe. Mantendo configurações atuais."
        return
    fi

    # Gerar senhas aleatórias
    DB_PASS="$(openssl rand -hex 16)"
    REDIS_PASS="$(openssl rand -hex 16)"
    SECRET_KEY="$(openssl rand -hex 32)"
    ADMIN_PASS="$(openssl rand -base64 12 | tr -dc 'A-Za-z0-9' | head -c12)"

    cat > "${SCRIPT_DIR}/.env" << EOF
# BR10 Block Web - Configuração do Servidor
# Gerado automaticamente em $(date '+%Y-%m-%d %H:%M:%S')

# Flask
FLASK_ENV=production
SECRET_KEY=${SECRET_KEY}
DEBUG=False

# PostgreSQL
DB_NAME=br10blockweb
DB_USER=br10user
DB_PASSWORD=${DB_PASS}

# Redis
REDIS_PASSWORD=${REDIS_PASS}

# Portas (altere se necessário)
NGINX_PORT=80
APP_PORT=8084

# Log
LOG_LEVEL=INFO
EOF

    # Salvar credenciais do admin
    cat > /root/br10blockweb_credentials.txt << EOF
=== BR10 Block Web - Credenciais de Acesso ===
Gerado em: $(date '+%Y-%m-%d %H:%M:%S')

Painel Web:
  URL: http://$(hostname -I | awk '{print $1}')
  Usuário: admin
  Senha: ${ADMIN_PASS}

Banco de Dados:
  Host: localhost (via Docker)
  Banco: br10blockweb
  Usuário: br10user
  Senha: ${DB_PASS}

Redis:
  Senha: ${REDIS_PASS}

GUARDE ESTE ARQUIVO EM LOCAL SEGURO!
EOF
    chmod 600 /root/br10blockweb_credentials.txt

    # Exportar para uso no script
    export ADMIN_PASS
    success "Arquivo .env criado"
}

build_and_start() {
    step "Construindo e iniciando containers"
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "${SCRIPT_DIR}"

    info "Fazendo build da imagem..."
    docker compose build --no-cache

    info "Subindo containers..."
    docker compose up -d

    info "Aguardando containers ficarem saudáveis (até 120s)..."
    local timeout=120
    local elapsed=0
    while [[ $elapsed -lt $timeout ]]; do
        if docker compose ps | grep -q "healthy" && \
           ! docker compose ps | grep -q "starting"; then
            break
        fi
        sleep 5
        elapsed=$((elapsed + 5))
        echo -n "."
    done
    echo ""

    success "Containers iniciados"
    docker compose ps
}

init_database() {
    step "Inicializando banco de dados"
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "${SCRIPT_DIR}"

    # Aguardar app estar pronto
    info "Aguardando aplicação estar pronta..."
    sleep 10

    # Ler senha do admin do arquivo de credenciais
    ADMIN_PASS="${ADMIN_PASS:-$(grep 'Senha:' /root/br10blockweb_credentials.txt 2>/dev/null | head -1 | awk '{print $2}')}"

    if [[ -z "${ADMIN_PASS:-}" ]]; then
        warn "Não foi possível determinar a senha do admin automaticamente."
        read -rp "Digite a senha para o usuário admin: " ADMIN_PASS
    fi

    docker compose exec -T app python init_db.py \
        --admin-user admin \
        --admin-pass "${ADMIN_PASS}" \
        && success "Banco de dados inicializado" \
        || warn "Banco pode já estar inicializado ou ocorreu um erro (verifique os logs)"
}

show_summary() {
    step "Implantação concluída"
    SERVER_IP=$(hostname -I | awk '{print $1}')

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          BR10 Block Web — Servidor Ativo!                    ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${CYAN}Painel Web:${NC}    http://${SERVER_IP}"
    echo -e "  ${CYAN}API direta:${NC}    http://${SERVER_IP}:8084"
    echo ""
    echo -e "  ${YELLOW}Credenciais salvas em:${NC} /root/br10blockweb_credentials.txt"
    echo ""
    echo -e "  ${CYAN}Comandos úteis:${NC}"
    echo -e "    docker compose ps                  # status dos containers"
    echo -e "    docker compose logs -f app         # logs da aplicação"
    echo -e "    docker compose restart app         # reiniciar aplicação"
    echo -e "    docker compose down                # parar tudo"
    echo ""
    echo -e "  ${YELLOW}Próximos passos:${NC}"
    echo -e "    1. Acesse o painel e faça login"
    echo -e "    2. Vá em 'Clientes' → 'Novo Cliente' → copie a API Key"
    echo -e "    3. No servidor DNS cliente, execute: bash deploy_client.sh"
    echo ""
}

main() {
    banner
    check_root
    install_docker
    setup_env
    build_and_start
    init_database
    show_summary
}

main "$@"
