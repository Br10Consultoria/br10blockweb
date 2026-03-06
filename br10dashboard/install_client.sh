#!/bin/bash
# =============================================================================
# BR10 Dashboard - Script de Instalação do CLIENTE
# =============================================================================
# Instala e configura o cliente BR10 Dashboard com Unbound
# Sistema: Ubuntu 22.04 / Debian 12
#
# Uso:
#   sudo bash install_client.sh
#
# Variáveis de ambiente opcionais:
#   BR10_SERVER_URL=http://IP_SERVIDOR:8084
#   BR10_API_KEY=sua_api_key
#
# Autor: BR10 Team
# Versão: 3.0.0
# =============================================================================

set -euo pipefail

# --- Cores ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- Configurações padrão ---
INSTALL_DIR="/opt/br10dashboard"
SERVICE_USER="br10dash"
DASHBOARD_PORT="8085"
SECRET_KEY="$(openssl rand -hex 32)"
ADMIN_USER="admin"
ADMIN_PASS="admin123"

# Configurações do servidor BR10 (podem ser passadas via env)
BR10_SERVER_URL="${BR10_SERVER_URL:-}"
BR10_API_KEY="${BR10_API_KEY:-}"

# Caminhos do Unbound
UNBOUND_ZONE_FILE="/var/lib/unbound/br10block-rpz.zone"
BLOCKED_DOMAINS_FILE="/var/lib/br10api/blocked_domains.txt"
UNBOUND_CONF_DIR="/etc/unbound/unbound.conf.d"

# --- Funções ---
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[AVISO]${NC} $*"; }
error()   { echo -e "${RED}[ERRO]${NC} $*"; exit 1; }
step()    { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }

banner() {
    echo -e "${BLUE}"
    echo "  ██████╗ ██████╗  ██╗ ██████╗     ██████╗  █████╗ ███████╗██╗  ██╗"
    echo "  ██╔══██╗██╔══██╗███║██╔═████╗    ██╔══██╗██╔══██╗██╔════╝██║  ██║"
    echo "  ██████╔╝██████╔╝╚██║██║██╔██║    ██║  ██║███████║███████╗███████║"
    echo "  ██╔══██╗██╔══██╗ ██║████╔╝██║    ██║  ██║██╔══██║╚════██║██╔══██║"
    echo "  ██████╔╝██║  ██║ ██║╚██████╔╝    ██████╔╝██║  ██║███████║██║  ██║"
    echo "  ╚═════╝ ╚═╝  ╚═╝ ╚═╝ ╚═════╝     ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝"
    echo -e "${NC}"
    echo -e "${GREEN}  BR10 Dashboard — Cliente DNS com Unbound${NC}"
    echo -e "${GREEN}  Versão 3.0.0${NC}"
    echo ""
}

check_root() {
    if [[ "$(id -u)" != "0" ]]; then
        error "Este script deve ser executado como root: sudo bash $0"
    fi
}

check_os() {
    if ! command -v apt-get &>/dev/null; then
        error "Sistema operacional não suportado. Use Ubuntu 22.04 ou Debian 12."
    fi
    info "Sistema operacional: $(lsb_release -ds 2>/dev/null || echo 'Linux')"
}

ask_config() {
    step "Configuração inicial"
    
    if [[ -z "${BR10_SERVER_URL}" ]]; then
        echo -e "${YELLOW}Digite a URL do servidor BR10 Block Web (ex: http://192.168.1.10:8084):${NC}"
        read -r BR10_SERVER_URL
    fi
    
    if [[ -z "${BR10_API_KEY}" ]]; then
        echo -e "${YELLOW}Digite a API Key do cliente (gerada no painel do servidor):${NC}"
        read -r BR10_API_KEY
    fi
    
    if [[ -z "${BR10_SERVER_URL}" ]] || [[ -z "${BR10_API_KEY}" ]]; then
        warn "BR10_SERVER_URL ou BR10_API_KEY não fornecidos."
        warn "Você pode configurá-los depois em ${INSTALL_DIR}/.env"
    fi
    
    info "Servidor: ${BR10_SERVER_URL:-'(não configurado)'}"
}

install_dependencies() {
    step "Instalando dependências do sistema"
    apt-get update -qq
    apt-get install -y -qq \
        python3 python3-pip python3-venv \
        python3.11 python3.11-venv python3.11-dev 2>/dev/null || true
    apt-get install -y -qq \
        unbound \
        redis-server \
        nginx \
        curl wget \
        jq \
        openssl \
        dnsutils \
        tcpdump \
        net-tools
    success "Dependências instaladas"

    # Determinar o interpretador Python a usar (preferência: 3.11 ou 3.12, evitar 3.13 por compatibilidade)
    if command -v python3.11 &>/dev/null; then
        PYTHON_BIN="python3.11"
    elif command -v python3.12 &>/dev/null; then
        PYTHON_BIN="python3.12"
    elif command -v python3.10 &>/dev/null; then
        PYTHON_BIN="python3.10"
    else
        PYTHON_BIN="python3"
    fi
    info "Python selecionado: ${PYTHON_BIN} ($(${PYTHON_BIN} --version 2>&1))"
    export PYTHON_BIN
}

setup_user() {
    step "Criando usuário do sistema"
    if ! id "${SERVICE_USER}" &>/dev/null; then
        useradd --system --home "${INSTALL_DIR}" --shell /bin/false "${SERVICE_USER}"
        success "Usuário '${SERVICE_USER}' criado"
    else
        info "Usuário '${SERVICE_USER}' já existe"
    fi
}

setup_unbound() {
    step "Configurando Unbound DNS"

    # Criar diretórios necessários
    mkdir -p "${UNBOUND_CONF_DIR}"
    mkdir -p "$(dirname "${UNBOUND_ZONE_FILE}")"
    mkdir -p "$(dirname "${BLOCKED_DOMAINS_FILE}")"

    # Criar arquivo de zona RPZ vazio se não existir
    if [[ ! -f "${UNBOUND_ZONE_FILE}" ]]; then
        cat > "${UNBOUND_ZONE_FILE}" << 'EOF'
; BR10 Block - RPZ Zone File
; Gerado automaticamente pelo br10block_client.sh
; Última atualização: nunca
$ORIGIN br10block.rpz.
$TTL 60
@ IN SOA localhost. root.localhost. (
    1 ; serial
    3600 ; refresh
    900 ; retry
    604800 ; expire
    60 ; minimum TTL
)
@ IN NS localhost.
; Domínios bloqueados serão inseridos abaixo
EOF
        chown unbound:unbound "${UNBOUND_ZONE_FILE}" 2>/dev/null || true
        chmod 644 "${UNBOUND_ZONE_FILE}"
        info "Arquivo de zona RPZ criado (vazio)"
    fi

    # Criar arquivo de lista TXT vazio se não existir
    if [[ ! -f "${BLOCKED_DOMAINS_FILE}" ]]; then
        touch "${BLOCKED_DOMAINS_FILE}"
        info "Arquivo de lista TXT criado (vazio)"
    fi

    # Configuração do Unbound com RPZ
    cat > "${UNBOUND_CONF_DIR}/br10block.conf" << EOF
# BR10 Block - Configuração do Unbound
# Arquivo gerado automaticamente

server:
    # Habilitar logging de queries (necessário para estatísticas)
    log-queries: yes
    log-replies: yes
    verbosity: 1
    
    # Interface de escuta (0.0.0.0 para todas as interfaces)
    interface: 0.0.0.0
    
    # Permitir consultas de qualquer IP (ajuste conforme necessário)
    access-control: 127.0.0.0/8 allow
    access-control: 10.0.0.0/8 allow
    access-control: 172.16.0.0/12 allow
    access-control: 192.168.0.0/16 allow
    
    # Zona de resposta de política (RPZ) para bloqueio
    local-zone: "br10block.rpz." nodefault

# Zona RPZ de bloqueio
auth-zone:
    name: "br10block.rpz."
    zonefile: "${UNBOUND_ZONE_FILE}"
    for-downstream: yes
    for-upstream: no

# Módulo de resposta de política
rpz:
    name: "br10block.rpz."
    action-override: nxdomain
    log: yes
    log-name: "br10block"
EOF

    # Verificar configuração do Unbound
    if unbound-checkconf 2>/dev/null; then
        success "Configuração do Unbound válida"
    else
        warn "Erro na configuração do Unbound. Verifique ${UNBOUND_CONF_DIR}/br10block.conf"
    fi

    # Habilitar e iniciar Unbound
    systemctl enable unbound
    systemctl restart unbound || warn "Falha ao reiniciar Unbound. Verifique a configuração."

    # Adicionar permissão para o usuário do serviço usar unbound-control
    if [[ -f /etc/unbound/unbound_server.key ]]; then
        chmod 640 /etc/unbound/unbound_server.key
        chgrp "${SERVICE_USER}" /etc/unbound/unbound_server.key 2>/dev/null || true
    fi

    success "Unbound configurado"
}

setup_redis() {
    step "Configurando Redis"
    systemctl start redis-server
    systemctl enable redis-server
    success "Redis configurado"
}

install_application() {
    step "Instalando BR10 Dashboard"

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Criar diretório de instalação
    mkdir -p "${INSTALL_DIR}"
    
    # Copiar arquivos
    if [[ -f "${SCRIPT_DIR}/app.py" ]]; then
        cp "${SCRIPT_DIR}/app.py" "${INSTALL_DIR}/"
        cp -r "${SCRIPT_DIR}/templates" "${INSTALL_DIR}/" 2>/dev/null || true
        cp -r "${SCRIPT_DIR}/scripts" "${INSTALL_DIR}/" 2>/dev/null || true
        cp -r "${SCRIPT_DIR}/config" "${INSTALL_DIR}/" 2>/dev/null || true
        [[ -f "${SCRIPT_DIR}/system_resources.py" ]] && cp "${SCRIPT_DIR}/system_resources.py" "${INSTALL_DIR}/"
        [[ -f "${SCRIPT_DIR}/requirements.txt" ]] && cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"
    else
        error "Arquivos do dashboard não encontrados em ${SCRIPT_DIR}"
    fi

    # Criar diretórios de dados
    mkdir -p "${INSTALL_DIR}/data/history"
    mkdir -p "${INSTALL_DIR}/logs"
    mkdir -p "${INSTALL_DIR}/config"
    mkdir -p "${INSTALL_DIR}/reports"
    mkdir -p /var/lib/br10api

    # Criar ambiente virtual Python (usando versão compatível)
    PYTHON_BIN="${PYTHON_BIN:-python3}"
    info "Criando venv com ${PYTHON_BIN}..."
    "${PYTHON_BIN}" -m venv "${INSTALL_DIR}/venv"
    "${INSTALL_DIR}/venv/bin/pip" install --upgrade pip setuptools wheel -q
    "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt" --no-cache-dir -q
    "${INSTALL_DIR}/venv/bin/pip" install gunicorn requests --no-cache-dir -q

    # Tornar scripts executáveis
    chmod +x "${INSTALL_DIR}/scripts/"*.sh 2>/dev/null || true

    # Ajustar permissões
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"
    chown -R "${SERVICE_USER}:${SERVICE_USER}" /var/lib/br10api
    
    # Permitir que o usuário do serviço execute unbound-control
    echo "${SERVICE_USER} ALL=(ALL) NOPASSWD: /usr/sbin/unbound-control, /bin/systemctl reload unbound, /bin/systemctl restart unbound" \
        > /etc/sudoers.d/br10dashboard
    chmod 440 /etc/sudoers.d/br10dashboard

    success "BR10 Dashboard instalado em ${INSTALL_DIR}"
}

create_env_file() {
    step "Criando arquivo de configuração .env"

    cat > "${INSTALL_DIR}/.env" << EOF
# BR10 Dashboard - Configuração do Cliente
# Gerado automaticamente em $(date)

# Diretórios
BASE_DIR=${INSTALL_DIR}
BLOCKED_DOMAINS_PATH=${BLOCKED_DOMAINS_FILE}
HISTORY_DIR=${INSTALL_DIR}/data/history
LOG_DIR=${INSTALL_DIR}/logs
UNBOUND_ZONE_FILE=${UNBOUND_ZONE_FILE}
USERS_FILE=${INSTALL_DIR}/config/users.json

# Servidor BR10 Block Web (central)
BR10_SERVER_URL=${BR10_SERVER_URL}
BR10_API_KEY=${BR10_API_KEY}
BR10_SYNC_SCRIPT=${INSTALL_DIR}/scripts/br10block_client.sh

# Redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
CACHE_TTL=300

# Flask
SECRET_KEY=${SECRET_KEY}
SESSION_LIFETIME_HOURS=24
EOF

    chmod 600 "${INSTALL_DIR}/.env"
    chown "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}/.env"
    success "Arquivo .env criado"
}

setup_cron() {
    step "Configurando sincronização automática (cron)"

    if [[ -n "${BR10_SERVER_URL}" ]] && [[ -n "${BR10_API_KEY}" ]]; then
        # Criar script wrapper para o cron
        cat > /usr/local/bin/br10block-sync << EOF
#!/bin/bash
export BR10_SERVER_URL="${BR10_SERVER_URL}"
export BR10_API_KEY="${BR10_API_KEY}"
export BLOCKED_DOMAINS_PATH="${BLOCKED_DOMAINS_FILE}"
export UNBOUND_ZONE_FILE="${UNBOUND_ZONE_FILE}"
exec "${INSTALL_DIR}/scripts/br10block_client.sh" "\$@"
EOF
        chmod +x /usr/local/bin/br10block-sync

        # Adicionar ao crontab do root (a cada 5 minutos)
        (crontab -l 2>/dev/null | grep -v "br10block-sync"; echo "*/5 * * * * /usr/local/bin/br10block-sync >> /var/log/br10block_client.log 2>&1") | crontab -
        success "Cron configurado: sincronização a cada 5 minutos"
    else
        warn "BR10_SERVER_URL ou BR10_API_KEY não configurados. Configure o cron manualmente."
        info "Exemplo de crontab:"
        info "  */5 * * * * BR10_SERVER_URL=http://IP:8084 BR10_API_KEY=SUA_KEY ${INSTALL_DIR}/scripts/br10block_client.sh"
    fi
}

create_systemd_service() {
    step "Criando serviço systemd"

    cat > /etc/systemd/system/br10dashboard.service << EOF
[Unit]
Description=BR10 Dashboard - Cliente DNS
After=network.target redis-server.service unbound.service
Wants=redis-server.service unbound.service

[Service]
Type=exec
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/venv/bin/gunicorn \
    --workers 2 \
    --bind 0.0.0.0:${DASHBOARD_PORT} \
    --timeout 120 \
    --access-logfile ${INSTALL_DIR}/logs/access.log \
    --error-logfile ${INSTALL_DIR}/logs/error.log \
    --log-level info \
    "app:app"
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=br10dashboard

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable br10dashboard
    systemctl start br10dashboard

    success "Serviço br10dashboard criado e iniciado"
}

configure_nginx() {
    step "Configurando Nginx como proxy reverso"

    SERVER_IP=$(hostname -I | awk '{print $1}')

    cat > /etc/nginx/sites-available/br10dashboard << EOF
server {
    listen 80;
    server_name ${SERVER_IP} _;

    location / {
        proxy_pass http://127.0.0.1:${DASHBOARD_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/br10dashboard /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default

    nginx -t && systemctl reload nginx
    success "Nginx configurado"
}

configure_firewall() {
    step "Configurando firewall"
    
    if command -v ufw &>/dev/null; then
        ufw allow 22/tcp comment "SSH" 2>/dev/null || true
        ufw allow 53/tcp comment "DNS TCP" 2>/dev/null || true
        ufw allow 53/udp comment "DNS UDP" 2>/dev/null || true
        ufw allow 80/tcp comment "HTTP" 2>/dev/null || true
        ufw allow "${DASHBOARD_PORT}/tcp" comment "BR10 Dashboard" 2>/dev/null || true
        info "Regras de firewall adicionadas (ufw)"
    fi
}

run_first_sync() {
    step "Executando primeira sincronização"
    
    if [[ -n "${BR10_SERVER_URL}" ]] && [[ -n "${BR10_API_KEY}" ]]; then
        info "Tentando sincronizar com o servidor BR10..."
        if /usr/local/bin/br10block-sync --force 2>/dev/null; then
            success "Primeira sincronização concluída"
        else
            warn "Primeira sincronização falhou. O cron tentará novamente em 5 minutos."
        fi
    else
        warn "Sincronização pulada (servidor não configurado)"
    fi
}

print_summary() {
    SERVER_IP=$(hostname -I | awk '{print $1}')
    
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║       BR10 DASHBOARD - INSTALAÇÃO CONCLUÍDA!                 ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}  Acesso ao Dashboard:${NC}"
    echo -e "  URL:      ${GREEN}http://${SERVER_IP}${NC}"
    echo -e "  Usuário:  ${GREEN}${ADMIN_USER}${NC}"
    echo -e "  Senha:    ${GREEN}${ADMIN_PASS}${NC}"
    echo ""
    echo -e "${CYAN}  Servidor BR10 Block Web:${NC}"
    echo -e "  URL:      ${BR10_SERVER_URL:-'(não configurado)'}"
    echo -e "  API Key:  ${BR10_API_KEY:-'(não configurada)'}"
    echo ""
    echo -e "${CYAN}  Unbound DNS:${NC}"
    echo -e "  Status:   $(systemctl is-active unbound 2>/dev/null || echo 'desconhecido')"
    echo -e "  Zona RPZ: ${UNBOUND_ZONE_FILE}"
    echo ""
    echo -e "${CYAN}  Sincronização Automática:${NC}"
    echo -e "  Frequência: a cada 5 minutos (cron)"
    echo -e "  Log:        /var/log/br10block_client.log"
    echo ""
    echo -e "${CYAN}  Comandos úteis:${NC}"
    echo -e "  Status dashboard:  systemctl status br10dashboard"
    echo -e "  Status unbound:    systemctl status unbound"
    echo -e "  Sync manual:       br10block-sync --force"
    echo -e "  Log sync:          tail -f /var/log/br10block_client.log"
    echo -e "  Logs dashboard:    journalctl -u br10dashboard -f"
    echo ""
    
    if [[ -z "${BR10_SERVER_URL}" ]] || [[ -z "${BR10_API_KEY}" ]]; then
        echo -e "${YELLOW}  ATENÇÃO: Configure BR10_SERVER_URL e BR10_API_KEY em:${NC}"
        echo -e "${YELLOW}  ${INSTALL_DIR}/.env${NC}"
        echo -e "${YELLOW}  Depois reinicie: systemctl restart br10dashboard${NC}"
        echo ""
    fi
}

# --- Execução principal ---
banner
check_root
check_os
ask_config
install_dependencies
setup_user
setup_unbound
setup_redis
install_application
create_env_file
setup_cron
create_systemd_service
configure_nginx
configure_firewall
run_first_sync
print_summary
