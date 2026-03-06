#!/bin/bash
# =============================================================================
# BR10 Dashboard - Deploy do CLIENTE DNS via Docker Compose
# =============================================================================
# Uso:
#   sudo bash deploy_client.sh
#
# O script:
#   1. Instala Docker e Docker Compose (se necessário)
#   2. Solicita a URL do servidor BR10 e a API Key
#   3. Cria o arquivo .env
#   4. Sobe os containers (unbound, redis, sync, dashboard)
#
# Pré-requisito:
#   - Servidor BR10 Block Web já instalado e rodando
#   - API Key gerada no painel do servidor (Clientes → Novo Cliente)
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
    echo -e "${CYAN}"
    echo "  ██████╗ ██████╗  ██╗ ██████╗     ██████╗  █████╗ ███████╗██╗  ██╗"
    echo "  ██╔══██╗██╔══██╗███║██╔═████╗    ██╔══██╗██╔══██╗██╔════╝██║  ██║"
    echo "  ██████╔╝██████╔╝╚██║██║██╔██║    ██║  ██║███████║███████╗███████║"
    echo "  ██╔══██╗██╔══██╗ ██║████╔╝██║    ██║  ██║██╔══██║╚════██║██╔══██║"
    echo "  ██████╔╝██║  ██║ ██║╚██████╔╝    ██████╔╝██║  ██║███████║██║  ██║"
    echo "  ╚═════╝ ╚═╝  ╚═╝ ╚═╝ ╚═════╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝"
    echo -e "${NC}"
    echo "  Deploy do Cliente DNS — Docker Compose"
    echo "  ─────────────────────────────────────────────────────────────────────────"
}

check_root() {
    [[ $EUID -eq 0 ]] || error "Execute como root: sudo bash $0"
}

check_port_53() {
    step "Verificando porta 53"
    if ss -tulnp 2>/dev/null | grep -q ':53 ' || netstat -tulnp 2>/dev/null | grep -q ':53 '; then
        warn "A porta 53 já está em uso. Verificando qual processo..."
        ss -tulnp 2>/dev/null | grep ':53 ' || netstat -tulnp 2>/dev/null | grep ':53 ' || true

        # Desativar systemd-resolved se for ele
        if systemctl is-active systemd-resolved &>/dev/null; then
            info "Desativando systemd-resolved para liberar porta 53..."
            systemctl stop systemd-resolved
            systemctl disable systemd-resolved
            # Configurar DNS temporário
            echo "nameserver 8.8.8.8" > /etc/resolv.conf
            success "systemd-resolved desativado"
        else
            warn "Outro processo está usando a porta 53. O Unbound pode não iniciar."
            warn "Verifique com: ss -tulnp | grep ':53'"
        fi
    else
        success "Porta 53 disponível"
    fi
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
        warn "Arquivo .env já existe."
        read -rp "Deseja reconfigurar? [s/N]: " RECONF
        [[ "${RECONF,,}" == "s" ]] || return
    fi

    echo ""
    echo -e "${YELLOW}Informe os dados do servidor BR10 Block Web:${NC}"
    echo ""

    read -rp "  URL do servidor (ex: http://192.168.1.10:8084): " BR10_SERVER_URL
    [[ -n "${BR10_SERVER_URL}" ]] || error "URL do servidor é obrigatória"

    read -rp "  API Key (gerada em Clientes → Novo Cliente): " BR10_API_KEY
    [[ -n "${BR10_API_KEY}" ]] || error "API Key é obrigatória"

    SECRET_KEY="$(openssl rand -hex 32)"

    cat > "${SCRIPT_DIR}/.env" << EOF
# BR10 Dashboard - Configuração do Cliente DNS
# Gerado automaticamente em $(date '+%Y-%m-%d %H:%M:%S')

# Servidor central BR10 Block Web
BR10_SERVER_URL=${BR10_SERVER_URL}
BR10_API_KEY=${BR10_API_KEY}

# Flask
SECRET_KEY=${SECRET_KEY}

# Porta do dashboard (padrão: 8085)
DASHBOARD_PORT=8085
EOF

    success "Arquivo .env criado"

    # Testar conectividade com o servidor
    info "Testando conectividade com o servidor..."
    if curl -sf --max-time 10 "${BR10_SERVER_URL}/health" &>/dev/null; then
        success "Servidor BR10 acessível"
    else
        warn "Não foi possível conectar ao servidor em ${BR10_SERVER_URL}"
        warn "Verifique a URL e se o servidor está rodando. Continuando mesmo assim..."
    fi
}

build_and_start() {
    step "Construindo e iniciando containers"
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "${SCRIPT_DIR}"

    info "Fazendo build da imagem do dashboard..."
    docker compose build --no-cache

    info "Subindo containers..."
    docker compose up -d

    info "Aguardando containers iniciarem (60s)..."
    sleep 20

    docker compose ps
    success "Containers iniciados"
}

show_summary() {
    step "Implantação concluída"
    SERVER_IP=$(hostname -I | awk '{print $1}')
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    source "${SCRIPT_DIR}/.env" 2>/dev/null || true

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          BR10 Dashboard — Cliente DNS Ativo!                 ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${CYAN}Dashboard:${NC}      http://${SERVER_IP}:${DASHBOARD_PORT:-8085}"
    echo -e "  ${CYAN}DNS (Unbound):${NC}  ${SERVER_IP}:53"
    echo -e "  ${CYAN}Servidor BR10:${NC}  ${BR10_SERVER_URL:-não configurado}"
    echo ""
    echo -e "  ${CYAN}Comandos úteis:${NC}"
    echo -e "    docker compose ps                     # status"
    echo -e "    docker compose logs -f sync           # logs do sincronizador"
    echo -e "    docker compose logs -f dashboard      # logs do dashboard"
    echo -e "    docker compose exec sync /usr/local/bin/br10block_client.sh --force"
    echo -e "                                          # forçar sincronização"
    echo ""
    echo -e "  ${YELLOW}Configure os clientes da rede para usar ${SERVER_IP} como DNS${NC}"
    echo ""
}

main() {
    banner
    check_root
    check_port_53
    install_docker
    setup_env
    build_and_start
    show_summary
}

main "$@"
