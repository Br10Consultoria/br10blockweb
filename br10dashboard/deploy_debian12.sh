#!/bin/bash
# =============================================================================
# BR10 Dashboard - Deploy para Debian 12 (Unbound no host)
# =============================================================================
# Arquitetura:
#   - Unbound DNS: roda NO HOST (instalado via apt-get install unbound)
#   - Sincronização: roda NO HOST via cron a cada 5 minutos
#   - Redis + Dashboard: containers Docker
#
# Uso:
#   sudo bash deploy_debian12.sh
#
# Pré-requisitos:
#   - Debian 12 (Bookworm)
#   - Docker + Docker Compose instalados
#   - IP do servidor BR10 Block Web
#   - API Key gerada no painel (Clientes DNS → Novo Cliente)
# =============================================================================
# Não usar set -e para que falhas do Unbound não abortem o deploy
set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_SCRIPT="${SCRIPT_DIR}/scripts/br10block_client.sh"
UNBOUND_CONF_DIR="/etc/unbound/unbound.conf.d"
UNBOUND_RPZ_CONF="${UNBOUND_CONF_DIR}/br10block-rpz.conf"
UNBOUND_ZONE_FILE="/var/lib/unbound/br10block-rpz.zone"
BR10API_DIR="/var/lib/br10api"
SYNC_DATA_DIR="/opt/br10dashboard/data"
SYNC_LOG="/var/log/br10block_client.log"

banner() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║       BR10 Dashboard — Deploy Debian 12                  ║${NC}"
    echo -e "${CYAN}║       (Unbound no host + cron de sincronização)          ║${NC}"
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

install_dependencies() {
    step "Instalando dependências"
    apt-get update -qq
    apt-get install -y curl jq
    success "curl e jq instalados"
}

install_unbound() {
    step "Verificando Unbound"
    if command -v unbound &>/dev/null; then
        success "Unbound já instalado: $(unbound -V 2>&1 | head -1)"
    else
        echo "  Instalando Unbound..."
        apt-get install -y unbound
        success "Unbound instalado"
    fi

    # Verificar unbound-control
    if command -v unbound-control &>/dev/null; then
        success "unbound-control disponível"
    else
        warn "unbound-control não encontrado. Tentando instalar..."
        apt-get install -y unbound || true
    fi
}

configure_unbound_rpz() {
    step "Configurando Unbound com RPZ"

    # Criar diretórios necessários
    mkdir -p "${UNBOUND_CONF_DIR}"
    mkdir -p "${BR10API_DIR}"
    mkdir -p "$(dirname "${UNBOUND_ZONE_FILE}")"

    # Criar arquivo de zona RPZ vazio se não existir
    if [[ ! -f "${UNBOUND_ZONE_FILE}" ]]; then
        cat > "${UNBOUND_ZONE_FILE}" << 'RPZEOF'
; BR10 Block Web - RPZ Zone File (vazio - aguardando primeira sincronização)
$ORIGIN br10block.rpz.
$TTL 60
@ IN SOA localhost. root.localhost. (1 3600 900 604800 60)
@ IN NS localhost.
RPZEOF
        chown unbound:unbound "${UNBOUND_ZONE_FILE}" 2>/dev/null || true
        chmod 644 "${UNBOUND_ZONE_FILE}"
        success "Arquivo de zona RPZ criado (vazio)"
    else
        success "Arquivo de zona RPZ já existe"
    fi

    # Criar configuração RPZ para Unbound
    # NOTA: não duplicar 'interface' e 'access-control' se já estiverem no unbound.conf principal
    cat > "${UNBOUND_RPZ_CONF}" << CONFEOF
# BR10 Block Web - Configuração RPZ
# Gerado em $(date '+%Y-%m-%d %H:%M:%S')
server:
    # Modulo respip OBRIGATORIO para RPZ
    module-config: "respip validator iterator"

    # Aceitar consultas de qualquer IP (rede interna)
    access-control: 0.0.0.0/0 allow

    # RPZ - Response Policy Zone
    rpz:
        name: "br10block.rpz"
        zonefile: "${UNBOUND_ZONE_FILE}"
        rpz-log: yes
        rpz-log-name: "br10block"
CONFEOF

    # Verificar se a configuração é válida
    if unbound-checkconf 2>/dev/null; then
        success "Configuração do Unbound válida"
    else
        warn "Verificação da configuração falhou — removendo configuração RPZ problemática"
        rm -f "${UNBOUND_RPZ_CONF}"
        warn "RPZ não configurado. Configure manualmente após o deploy."
        return 0
    fi

    # Reiniciar Unbound para aplicar RPZ (não aborta o deploy em caso de falha)
    if systemctl restart unbound 2>/dev/null; then
        sleep 2
        if systemctl is-active --quiet unbound; then
            success "Unbound reiniciado com suporte a RPZ"
        else
            warn "Unbound não ficou ativo após restart. Verifique: journalctl -u unbound -n 20"
        fi
    else
        warn "Falha ao reiniciar Unbound. O deploy continua sem interrupção."
        warn "Verifique manualmente: journalctl -u unbound -n 20"
    fi
}

setup_env() {
    step "Configurando variáveis de ambiente"

    if [[ -f "${SCRIPT_DIR}/.env" ]]; then
        warn "Arquivo .env já existe."
        read -rp "  Reconfigurar? [s/N]: " RECONF
        [[ "${RECONF,,}" == "s" ]] || { success "Mantendo .env existente"; source "${SCRIPT_DIR}/.env"; return; }
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

setup_sync_script() {
    step "Configurando script de sincronização no host"

    # Criar diretório de dados
    mkdir -p "${SYNC_DATA_DIR}"
    mkdir -p "${BR10API_DIR}"
    touch "${SYNC_LOG}"

    # Tornar o script executável
    chmod +x "${SYNC_SCRIPT}"

    # Criar wrapper com as variáveis de ambiente configuradas
    source "${SCRIPT_DIR}/.env"

    cat > /usr/local/bin/br10block-sync << EOF
#!/bin/bash
# BR10 Block - Wrapper de sincronização com variáveis de ambiente
export BR10_SERVER_URL="${BR10_SERVER_URL}"
export BR10_API_KEY="${BR10_API_KEY}"
export BR10_FORMAT="rpz"
export UNBOUND_ZONE_FILE="${UNBOUND_ZONE_FILE}"
export BLOCKED_DOMAINS_FILE="${BR10API_DIR}/blocked_domains.txt"
export DATA_DIR="${SYNC_DATA_DIR}"
export LOG_FILE="${SYNC_LOG}"
export REDIS_HOST="127.0.0.1"
export REDIS_PORT="6379"
export HTTP_TIMEOUT="30"
export MAX_RETRIES="3"

exec "${SYNC_SCRIPT}" "\$@"
EOF
    chmod +x /usr/local/bin/br10block-sync
    success "Wrapper /usr/local/bin/br10block-sync criado"

    # Configurar cron (a cada 5 minutos)
    CRON_LINE="*/5 * * * * root /usr/local/bin/br10block-sync >> ${SYNC_LOG} 2>&1"
    CRON_FILE="/etc/cron.d/br10block-sync"

    echo "${CRON_LINE}" > "${CRON_FILE}"
    chmod 644 "${CRON_FILE}"
    success "Cron configurado: ${CRON_FILE} (a cada 5 minutos)"
}

build_and_start() {
    step "Construindo e iniciando containers (Redis + Dashboard)"
    cd "${SCRIPT_DIR}"

    # Parar containers antigos se existirem
    docker compose down --remove-orphans 2>/dev/null || true

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
    step "Executando primeira sincronização no host"

    if /usr/local/bin/br10block-sync --force; then
        success "Primeira sincronização concluída!"
    else
        warn "Sincronização inicial falhou. Execute manualmente: /usr/local/bin/br10block-sync --force"
        warn "Verifique o log: tail -f ${SYNC_LOG}"
    fi
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
    echo -e "  ${CYAN}DNS (Unbound):${NC}  ${SERVER_IP}:53  (serviço do host)"
    echo -e "  ${CYAN}Servidor BR10:${NC}  ${BR10_SERVER_URL:-não configurado}"
    echo -e "  ${CYAN}Sincronização:${NC}  a cada 5 minutos via cron"
    echo ""
    echo -e "  ${CYAN}Comandos úteis:${NC}"
    echo -e "    systemctl status unbound                   # status do DNS"
    echo -e "    /usr/local/bin/br10block-sync --force      # forçar sincronização"
    echo -e "    tail -f ${SYNC_LOG}    # log de sincronização"
    echo -e "    cd ${SCRIPT_DIR}"
    echo -e "    docker compose ps                          # status dos containers"
    echo -e "    docker compose logs -f dashboard           # logs do dashboard"
    echo ""
    echo -e "  ${YELLOW}Configure os clientes da rede para usar ${SERVER_IP} como DNS${NC}"
    echo ""
}

main() {
    banner
    check_root
    check_docker
    install_dependencies
    install_unbound
    configure_unbound_rpz
    setup_env
    setup_sync_script
    build_and_start
    force_first_sync
    show_summary
}

main "$@"
