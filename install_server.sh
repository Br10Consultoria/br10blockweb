#!/bin/bash
# =============================================================================
# BR10 Block Web - Script de Instalação do SERVIDOR
# =============================================================================
# Instala e configura o servidor central BR10 Block Web
# Sistema: Ubuntu 22.04 / Debian 12
#
# Uso:
#   sudo bash install_server.sh
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
INSTALL_DIR="/opt/br10blockweb"
SERVICE_USER="br10"
SERVER_PORT="8084"
DB_NAME="br10blockweb"
DB_USER="br10user"
DB_PASS="$(openssl rand -hex 16)"
REDIS_PASS="$(openssl rand -hex 16)"
SECRET_KEY="$(openssl rand -hex 32)"
ADMIN_USER="admin"
ADMIN_PASS="$(openssl rand -hex 8)"

# --- Funções ---
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
    echo "  ╚═════╝ ╚═╝  ╚═╝ ╚═╝ ╚═════╝     ╚═════╝ ╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝"
    echo -e "${NC}"
    echo -e "${GREEN}  BR10 Block Web — Servidor Central de Bloqueio de Domínios${NC}"
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

install_dependencies() {
    step "Instalando dependências do sistema"
    apt-get update -qq
    apt-get install -y -qq \
        python3 python3-pip python3-venv \
        python3.11 python3.11-venv python3.11-dev 2>/dev/null || true
    apt-get install -y -qq \
        postgresql postgresql-contrib \
        redis-server \
        nginx \
        curl wget git \
        poppler-utils \
        libpq-dev python3-dev \
        openssl \
        supervisor \
        jq
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

setup_postgresql() {
    step "Configurando PostgreSQL"
    systemctl start postgresql
    systemctl enable postgresql

    # Criar banco e usuário
    sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';" 2>/dev/null || \
        sudo -u postgres psql -c "ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASS}';"
    
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" 2>/dev/null || \
        info "Banco '${DB_NAME}' já existe"
    
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
    
    success "PostgreSQL configurado: banco='${DB_NAME}', usuário='${DB_USER}'"
}

setup_redis() {
    step "Configurando Redis"
    systemctl start redis-server
    systemctl enable redis-server

    # Configurar senha no Redis
    if [[ -n "${REDIS_PASS}" ]]; then
        sed -i "s/^# requirepass .*/requirepass ${REDIS_PASS}/" /etc/redis/redis.conf
        sed -i "s/^requirepass .*/requirepass ${REDIS_PASS}/" /etc/redis/redis.conf
        systemctl restart redis-server
    fi

    success "Redis configurado"
}

install_application() {
    step "Instalando a aplicação BR10 Block Web"

    # Criar diretório de instalação
    mkdir -p "${INSTALL_DIR}"
    
    # Copiar arquivos da aplicação
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    if [[ -d "${SCRIPT_DIR}/backend" ]]; then
        cp -r "${SCRIPT_DIR}/backend" "${INSTALL_DIR}/"
        cp -r "${SCRIPT_DIR}/frontend" "${INSTALL_DIR}/"
        [[ -f "${SCRIPT_DIR}/app.py" ]] && cp "${SCRIPT_DIR}/app.py" "${INSTALL_DIR}/"
        [[ -f "${SCRIPT_DIR}/requirements.txt" ]] && cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"
        [[ -f "${SCRIPT_DIR}/init_db.py" ]] && cp "${SCRIPT_DIR}/init_db.py" "${INSTALL_DIR}/"
    else
        error "Arquivos da aplicação não encontrados em ${SCRIPT_DIR}. Execute este script a partir do diretório do projeto."
    fi

    # Criar ambiente virtual Python (usando versão compatível)
    PYTHON_BIN="${PYTHON_BIN:-python3}"
    info "Criando venv com ${PYTHON_BIN}..."
    "${PYTHON_BIN}" -m venv "${INSTALL_DIR}/venv"
    "${INSTALL_DIR}/venv/bin/pip" install --upgrade pip setuptools wheel -q
    "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt" --no-cache-dir -q

    # Criar diretórios necessários
    mkdir -p "${INSTALL_DIR}/data/uploads"
    mkdir -p "${INSTALL_DIR}/data/exports"
    mkdir -p "${INSTALL_DIR}/logs"
    mkdir -p /var/lib/br10api

    # Ajustar permissões
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"
    chown -R "${SERVICE_USER}:${SERVICE_USER}" /var/lib/br10api

    success "Aplicação instalada em ${INSTALL_DIR}"
}

create_env_file() {
    step "Criando arquivo de configuração .env"

    cat > "${INSTALL_DIR}/.env" << EOF
# BR10 Block Web - Configuração do Servidor
# Gerado automaticamente em $(date)

# Flask
FLASK_ENV=production
SECRET_KEY=${SECRET_KEY}
DEBUG=False
HOST=0.0.0.0
PORT=${SERVER_PORT}

# PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASS}

# Redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=${REDIS_PASS}

# Cache TTL (segundos)
CACHE_TTL_DOMAINS=300
CACHE_TTL_STATS=60
CACHE_TTL_CLIENTS=120

# Sessão
SESSION_LIFETIME_HOURS=24

# Upload
MAX_CONTENT_LENGTH=16777216

# Unbound
UNBOUND_ZONE_FILE=/var/lib/unbound/br10block-rpz.zone
BLOCKED_DOMAINS_PATH=/var/lib/br10api/blocked_domains.txt

# Logging
LOG_LEVEL=INFO
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

# Backup
BACKUP_ENABLED=True
BACKUP_INTERVAL_HOURS=24
BACKUP_RETENTION_DAYS=7
EOF

    chmod 600 "${INSTALL_DIR}/.env"
    chown "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}/.env"
    success "Arquivo .env criado"
}

initialize_database() {
    step "Inicializando banco de dados"
    
    cd "${INSTALL_DIR}"
    sudo -u "${SERVICE_USER}" "${INSTALL_DIR}/venv/bin/python" init_db.py \
        --admin-user "${ADMIN_USER}" \
        --admin-pass "${ADMIN_PASS}" 2>/dev/null || \
    sudo -u "${SERVICE_USER}" "${INSTALL_DIR}/venv/bin/python" -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}')
from backend.database.db import db
from backend.models.user import User
db.initialize()
User.create('${ADMIN_USER}', '${ADMIN_PASS}', 'admin')
print('Banco inicializado com sucesso')
" 2>/dev/null || warn "Inicialização do banco pode precisar ser feita manualmente"

    success "Banco de dados inicializado"
}

create_systemd_service() {
    step "Criando serviço systemd"

    cat > /etc/systemd/system/br10blockweb.service << EOF
[Unit]
Description=BR10 Block Web - Servidor Central
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=exec
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/venv/bin/gunicorn \
    --workers 4 \
    --bind 0.0.0.0:${SERVER_PORT} \
    --timeout 120 \
    --access-logfile ${INSTALL_DIR}/logs/access.log \
    --error-logfile ${INSTALL_DIR}/logs/error.log \
    --log-level info \
    "backend.app:app"
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=br10blockweb

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable br10blockweb
    systemctl start br10blockweb

    success "Serviço br10blockweb criado e iniciado"
}

configure_nginx() {
    step "Configurando Nginx como proxy reverso"

    SERVER_IP=$(hostname -I | awk '{print $1}')

    cat > /etc/nginx/sites-available/br10blockweb << EOF
server {
    listen 80;
    server_name ${SERVER_IP} _;

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:${SERVER_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    location /static/ {
        alias ${INSTALL_DIR}/frontend/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

    ln -sf /etc/nginx/sites-available/br10blockweb /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default

    nginx -t && systemctl reload nginx
    success "Nginx configurado"
}

configure_firewall() {
    step "Configurando firewall"
    
    if command -v ufw &>/dev/null; then
        ufw allow 22/tcp comment "SSH" 2>/dev/null || true
        ufw allow 80/tcp comment "HTTP" 2>/dev/null || true
        ufw allow 443/tcp comment "HTTPS" 2>/dev/null || true
        ufw allow "${SERVER_PORT}/tcp" comment "BR10 Block Web" 2>/dev/null || true
        info "Regras de firewall adicionadas (ufw)"
    else
        info "ufw não encontrado, configure o firewall manualmente"
    fi
}

print_summary() {
    SERVER_IP=$(hostname -I | awk '{print $1}')
    
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║         BR10 BLOCK WEB - INSTALAÇÃO CONCLUÍDA!               ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}  Acesso ao Painel:${NC}"
    echo -e "  URL:      ${GREEN}http://${SERVER_IP}${NC}"
    echo -e "  Usuário:  ${GREEN}${ADMIN_USER}${NC}"
    echo -e "  Senha:    ${GREEN}${ADMIN_PASS}${NC}"
    echo ""
    echo -e "${CYAN}  Banco de Dados:${NC}"
    echo -e "  Host:     localhost:5432"
    echo -e "  Banco:    ${DB_NAME}"
    echo -e "  Usuário:  ${DB_USER}"
    echo -e "  Senha:    ${DB_PASS}"
    echo ""
    echo -e "${CYAN}  Redis:${NC}"
    echo -e "  Host:     localhost:6379"
    echo -e "  Senha:    ${REDIS_PASS}"
    echo ""
    echo -e "${YELLOW}  IMPORTANTE: Salve estas credenciais em local seguro!${NC}"
    echo -e "${YELLOW}  Arquivo de configuração: ${INSTALL_DIR}/.env${NC}"
    echo ""
    echo -e "${CYAN}  Próximos passos:${NC}"
    echo -e "  1. Acesse o painel e faça login"
    echo -e "  2. Vá em 'Clientes' e crie um cliente para cada servidor DNS"
    echo -e "  3. Copie a API Key gerada para usar no cliente (br10dashboard)"
    echo -e "  4. Faça upload de um PDF com a lista de domínios"
    echo ""
    echo -e "${CYAN}  Comandos úteis:${NC}"
    echo -e "  Status:   systemctl status br10blockweb"
    echo -e "  Logs:     journalctl -u br10blockweb -f"
    echo -e "  Restart:  systemctl restart br10blockweb"
    echo ""

    # Salvar credenciais em arquivo
    cat > /root/br10blockweb_credentials.txt << EOF
BR10 Block Web - Credenciais de Instalação
==========================================
Data: $(date)

Painel Web:
  URL: http://${SERVER_IP}
  Usuário: ${ADMIN_USER}
  Senha: ${ADMIN_PASS}

PostgreSQL:
  Host: localhost:5432
  Banco: ${DB_NAME}
  Usuário: ${DB_USER}
  Senha: ${DB_PASS}

Redis:
  Host: localhost:6379
  Senha: ${REDIS_PASS}

Arquivo de configuração: ${INSTALL_DIR}/.env
EOF
    chmod 600 /root/br10blockweb_credentials.txt
    info "Credenciais salvas em /root/br10blockweb_credentials.txt"
}

# --- Execução principal ---
banner
check_root
check_os
install_dependencies
setup_user
setup_postgresql
setup_redis
install_application
create_env_file
initialize_database
create_systemd_service
configure_nginx
configure_firewall
print_summary
