#!/bin/bash
# =============================================================================
# BR10 Block Web - Deploy via Docker Swarm
# =============================================================================
# Uso:
#   sudo bash deploy_server.sh
#
# O script:
#   1. Verifica se o Swarm está ativo
#   2. Cria o arquivo .env com senhas geradas automaticamente
#   3. Faz o build da imagem br10blockweb:latest
#   4. Faz deploy do stack no Swarm (docker stack deploy)
#   5. Inicializa o banco de dados e cria o usuário admin
#
# Autor: BR10 Team
# Versão: 3.1.0
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[AVISO]${NC} $*"; }
error()   { echo -e "${RED}[ERRO]${NC} $*"; exit 1; }
step()    { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_NAME="br10blockweb"

check_root() {
    [[ $EUID -eq 0 ]] || error "Execute como root: sudo bash $0"
}

check_swarm() {
    step "Verificando Docker Swarm"
    if ! docker info 2>/dev/null | grep -q "Swarm: active"; then
        error "Docker Swarm não está ativo. Execute: docker swarm init"
    fi
    success "Docker Swarm ativo"
}

setup_env() {
    step "Configurando variáveis de ambiente"
    cd "${SCRIPT_DIR}"

    if [[ -f ".env" ]]; then
        warn "Arquivo .env já existe. Mantendo configurações atuais."
        source .env
        return
    fi

    DB_PASSWORD="$(openssl rand -hex 16)"
    SECRET_KEY="$(openssl rand -hex 32)"
    ADMIN_PASS="$(openssl rand -base64 12 | tr -dc 'A-Za-z0-9' | head -c12)"

    cat > .env << EOF
# BR10 Block Web - Configuração do Servidor
# Gerado automaticamente em $(date '+%Y-%m-%d %H:%M:%S')
FLASK_ENV=production
SECRET_KEY=${SECRET_KEY}
DEBUG=False
DB_PASSWORD=${DB_PASSWORD}
REDIS_PASSWORD=
LOG_LEVEL=INFO
TRAEFIK_DOMAIN=br10blockweb.br10consultoria.com.br
EOF

    cat > /root/br10blockweb_credentials.txt << EOF
=== BR10 Block Web - Credenciais ===
Gerado em: $(date '+%Y-%m-%d %H:%M:%S')

Painel Web:
  URL: https://br10blockweb.br10consultoria.com.br
  Usuário: admin
  Senha: ${ADMIN_PASS}

Banco de Dados:
  Senha: ${DB_PASSWORD}

GUARDE ESTE ARQUIVO EM LOCAL SEGURO!
EOF
    chmod 600 /root/br10blockweb_credentials.txt
    export ADMIN_PASS DB_PASSWORD SECRET_KEY
    success "Arquivo .env criado — credenciais em /root/br10blockweb_credentials.txt"
}

build_image() {
    step "Fazendo build da imagem br10blockweb:latest"
    cd "${SCRIPT_DIR}"
    docker build -t br10blockweb:latest .
    success "Imagem construída"
}

deploy_stack() {
    step "Fazendo deploy do stack no Swarm"
    cd "${SCRIPT_DIR}"

    # Exportar variáveis do .env para o stack.yml
    set -a
    source .env
    set +a

    docker stack deploy -c stack.yml "${STACK_NAME}" --with-registry-auth
    success "Stack '${STACK_NAME}' deployado"

    info "Aguardando serviços iniciarem (60s)..."
    sleep 60
    docker stack services "${STACK_NAME}"
}

init_database() {
    step "Inicializando banco de dados"

    # Ler senha do admin
    ADMIN_PASS="${ADMIN_PASS:-$(grep 'Senha:' /root/br10blockweb_credentials.txt 2>/dev/null | head -1 | awk '{print $NF}')}"

    if [[ -z "${ADMIN_PASS:-}" ]]; then
        read -rp "Digite a senha para o usuário admin: " ADMIN_PASS
    fi

    # Aguardar o container do app estar rodando
    local retries=0
    local app_container=""
    while [[ $retries -lt 12 ]]; do
        app_container=$(docker ps -q -f "name=${STACK_NAME}_app" 2>/dev/null | head -1)
        [[ -n "${app_container}" ]] && break
        info "Aguardando container app... (${retries}/12)"
        sleep 10
        retries=$((retries + 1))
    done

    [[ -z "${app_container}" ]] && error "Container app não encontrado após 120s. Verifique: docker service ps ${STACK_NAME}_app"

    docker exec "${app_container}" \
        python init_db.py --admin-user admin --admin-pass "${ADMIN_PASS}" \
        && success "Banco de dados inicializado" \
        || warn "Banco pode já estar inicializado (normal em redeploys)"
}

show_summary() {
    step "Deploy concluído"
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          BR10 Block Web — Stack Swarm Ativo!                 ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${CYAN}Painel Web:${NC}  https://br10blockweb.br10consultoria.com.br"
    echo -e "  ${YELLOW}Credenciais:${NC} /root/br10blockweb_credentials.txt"
    echo ""
    echo -e "  ${CYAN}Comandos úteis:${NC}"
    echo -e "    docker stack services ${STACK_NAME}              # status dos serviços"
    echo -e "    docker service logs -f ${STACK_NAME}_app         # logs da aplicação"
    echo -e "    docker stack rm ${STACK_NAME}                    # remover stack"
    echo -e "    bash deploy_server.sh                            # redeploy"
    echo ""
}

main() {
    check_root
    check_swarm
    setup_env
    build_image
    deploy_stack
    init_database
    show_summary
}

main "$@"
