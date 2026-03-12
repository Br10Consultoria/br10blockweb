#!/bin/bash
# =============================================================================
# BR10 Dashboard - Deploy Rápido para Debian 12
# =============================================================================
# Uso:
#   sudo bash deploy_debian12.sh
#
# Pré-requisitos:
#   - Debian 12 (Bookworm)
#   - Docker + Docker Compose instalados
#   - Unbound instalado (se usar modo nativo, não Docker)
#   - IP do servidor BR10 Block Web
#   - API Key gerada no painel (Clientes DNS → Novo Cliente)
#
# O que este script faz:
#   1. Cria o arquivo .env com as configurações fornecidas
#   2. Sobe os containers via docker compose
#   3. Aguarda a inicialização e exibe o resumo
# =============================================================================
set -euo pipefail

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

banner() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║       BR10 Dashboard — Deploy Debian 12                  ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

step()    { echo -e "\n${CYAN}▶ $*${NC}"; }
success() { echo -e "${GREEN}✔ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $*${NC}"; }
error()   { echo -e "${RED}✘ $*${NC}"; exit 1; }

check_root() {
    [[ $EUID -eq 0 ]] || error "Execute como root: sudo bash $0"
}

check_docker() {
    step "Verificando Docker"
    command -v docker &>/dev/null || error "Docker não encontrado. Instale com: curl -fsSL https://get.docker.com | bash"
    docker compose version &>/dev/null 2>&1 || error "Docker Compose não encontrado. Atualize o Docker."
    success "Docker $(docker --version | cut -d' ' -f3 | tr -d ',') disponível"
}

check_port_53() {
    step "Verificando porta 53"
    if ss -tulnp 2>/dev/null | grep -q ':53 '; then
        warn "Porta 53 em uso. Verificando o processo..."
        PROC=$(ss -tulnp 2>/dev/null | grep ':53 ' | head -1)
        echo "  $PROC"

        # Desativar systemd-resolved se for o culpado
        if echo "$PROC" | grep -q "systemd-resolve"; then
            warn "Desativando systemd-resolved para liberar porta 53..."
            systemctl stop systemd-resolved
            systemctl disable systemd-resolved
            # Configurar DNS temporário
            echo "nameserver 8.8.8.8" > /etc/resolv.conf
            success "systemd-resolved desativado"
        else
            warn "Outro processo usa a porta 53. O Unbound (container) pode não iniciar."
            warn "Verifique com: ss -tulnp | grep ':53'"
        fi
    else
        success "Porta 53 disponível"
    fi
}

setup_env() {
    step "Configurando variáveis de ambiente"

    if [[ -f "${SCRIPT_DIR}/.env" ]]; then
        warn "Arquivo .env já existe."
        read -rp "  Reconfigurar? [s/N]: " RECONF
        [[ "${RECONF,,}" == "s" ]] || { success "Mantendo .env existente"; return; }
    fi

    echo ""
    echo -e "${YELLOW}Informe os dados do servidor BR10 Block Web:${NC}"
    echo ""

    read -rp "  URL do servidor (ex: https://br10blockweb.seudominio.com.br): " BR10_SERVER_URL
    [[ -n "${BR10_SERVER_URL}" ]] || error "URL do servidor é obrigatória"

    read -rp "  API Key (gerada em Clientes DNS → Novo Cliente): " BR10_API_KEY
    [[ -n "${BR10_API_KEY}" ]] || error "API Key é obrigatória"

    read -rp "  Porta do Dashboard [8085]: " DASHBOARD_PORT
    DASHBOARD_PORT="${DASHBOARD_PORT:-8085}"

    SECRET_KEY="$(openssl rand -hex 32)"

    cat > "${SCRIPT_DIR}/.env" << EOF
# BR10 Dashboard - Configuração do Cliente DNS
# Gerado em $(date '+%Y-%m-%d %H:%M:%S')

# Servidor central BR10 Block Web
BR10_SERVER_URL=${BR10_SERVER_URL}
BR10_API_KEY=${BR10_API_KEY}

# Flask
SECRET_KEY=${SECRET_KEY}

# Porta do dashboard
DASHBOARD_PORT=${DASHBOARD_PORT}
EOF

    success "Arquivo .env criado"

    # Testar conectividade
    step "Testando conectividade com o servidor"
    if curl -sf --max-time 10 "${BR10_SERVER_URL}/health" &>/dev/null; then
        success "Servidor BR10 acessível em ${BR10_SERVER_URL}"
    else
        warn "Não foi possível conectar em ${BR10_SERVER_URL}/health"
        warn "Verifique a URL e se o servidor está rodando. Continuando mesmo assim..."
    fi
}

build_and_start() {
    step "Construindo e iniciando containers"
    cd "${SCRIPT_DIR}"

    echo "  Fazendo build da imagem do dashboard..."
    docker compose build --no-cache

    echo "  Subindo containers..."
    docker compose up -d

    echo "  Aguardando inicialização (30s)..."
    sleep 30

    docker compose ps
    success "Containers iniciados"
}

force_first_sync() {
    step "Executando primeira sincronização"
    cd "${SCRIPT_DIR}"

    echo "  Aguardando Unbound ficar pronto (15s)..."
    sleep 15

    docker compose exec -T sync /usr/local/bin/br10block_client.sh --force && \
        success "Primeira sincronização concluída!" || \
        warn "Sincronização inicial falhou. Execute manualmente: docker compose exec sync /usr/local/bin/br10block_client.sh --force"
}

show_summary() {
    step "Deploy concluído"
    SERVER_IP=$(hostname -I | awk '{print $1}')
    source "${SCRIPT_DIR}/.env" 2>/dev/null || true

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║         BR10 Dashboard — Cliente DNS Ativo!              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${CYAN}Dashboard:${NC}      http://${SERVER_IP}:${DASHBOARD_PORT:-8085}"
    echo -e "  ${CYAN}DNS (Unbound):${NC}  ${SERVER_IP}:53"
    echo -e "  ${CYAN}Servidor BR10:${NC}  ${BR10_SERVER_URL:-não configurado}"
    echo ""
    echo -e "  ${CYAN}Comandos úteis:${NC}"
    echo -e "    cd ${SCRIPT_DIR}"
    echo -e "    docker compose ps                          # status dos containers"
    echo -e "    docker compose logs -f sync                # logs do sincronizador"
    echo -e "    docker compose logs -f dashboard           # logs do dashboard"
    echo -e "    docker compose exec sync /usr/local/bin/br10block_client.sh --force"
    echo -e "                                               # forçar sincronização"
    echo ""
    echo -e "  ${YELLOW}Configure os clientes da rede para usar ${SERVER_IP} como DNS${NC}"
    echo ""
}

main() {
    banner
    check_root
    check_docker
    check_port_53
    setup_env
    build_and_start
    force_first_sync
    show_summary
}

main "$@"
