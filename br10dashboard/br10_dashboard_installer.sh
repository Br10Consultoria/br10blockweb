#!/bin/bash
# BR10 Complete Setup - Docker + Nginx + SSL
# Integra Docker containers com Nginx host e SSL

# Define colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Banner
display_banner() {
    echo -e "${BLUE}"
    echo -e "888888b.          d888    .d8888b.    .d8888b.                      888                   888 "
    echo -e "888   Y88b        d8888   d88P  Y88b  d88P  Y88b                     888                   888 "
    echo -e "888    888          888         888         888                     888                   888 "
    echo -e "888   d88P  888d888 888       .d88P       .d88P    .d88b.  88888b.  888888 888d888 8888b.  888 "
    echo -e "8888888P\"   888P\"   888   .od888P\"    .od888P\"    d88\"\"88b 888 \"88b 888    888P\"      \"88b 888 "
    echo -e "888 T88b    888     888  d88P\"       d88P\"        888  888 888  888 888    888    .d888888 888 "
    echo -e "888  T88b   888     888  888\"        888\"         Y88..88P 888  888 Y88b.  888    888  888 888 "
    echo -e "888   T88b  888   8888888 888888888  888888888     \"Y88P\"  888  888  \"Y888 888    \"Y888888 888 "
    echo -e "${NC}"
    echo -e "${GREEN}=============================================================================${NC}"
    echo -e "${GREEN}   BR10 DNS Complete Setup - Docker Containers + Nginx + SSL/HTTPS          ${NC}"
    echo -e "${GREEN}=============================================================================${NC}"
    echo
}

# Function to check root permissions
check_root() {
    if [ "$(id -u)" != "0" ]; then
        echo -e "${RED}Este script deve ser executado como root (sudo).${NC}"
        exit 1
    fi
}

# Function to show progress
show_progress() {
    echo -e "${BLUE}>>> $1...${NC}"
}

# Function to check if a command was successful
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1${NC}"
    else
        echo -e "${RED}✗ $1${NC}"
        if [ "$2" = "critical" ]; then
            echo -e "${RED}Erro crítico. Abortando instalação.${NC}"
            exit 1
        fi
    fi
}

# Function to ask the user
ask() {
    read -p "$1 " answer
    echo $answer
}

# Verificar se Docker está instalado
check_docker() {
    show_progress "Verificando Docker"
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Docker não está instalado!${NC}"
        echo -e "${YELLOW}Instalando Docker...${NC}"
        
        # Instalar Docker
        apt-get update
        apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io
        
        # Instalar Docker Compose
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        
        check_status "Instalação do Docker" "critical"
    else
        echo -e "${GREEN}Docker já está instalado${NC}"
    fi
    
    # Verificar Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${YELLOW}Instalando Docker Compose...${NC}"
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        check_status "Instalação do Docker Compose"
    fi
    
    # Iniciar Docker
    systemctl start docker
    systemctl enable docker
    check_status "Inicialização do Docker"
}

# Instalar pré-requisitos para Nginx + SSL
install_nginx_requirements() {
    show_progress "Instalando pré-requisitos para Nginx e SSL"
    
    apt-get update -qq
    
    PACKAGES=(
        "nginx"
        "certbot"
        "python3-certbot-nginx"
        "curl"
        "wget"
    )
    
    for pkg in "${PACKAGES[@]}"; do
        if ! dpkg -s $pkg >/dev/null 2>&1; then
            echo -e "${YELLOW}Instalando $pkg...${NC}"
            apt-get install -y $pkg >/dev/null 2>&1
            check_status "Instalação $pkg"
        else
            echo -e "${GREEN}$pkg já está instalado${NC}"
        fi
    done
    
    # Configurar firewall
    if command -v ufw &> /dev/null; then
        echo -e "${YELLOW}Configurando firewall (UFW)...${NC}"
        ufw allow 'Nginx Full' || echo -e "${YELLOW}Falha ao configurar UFW${NC}"
        ufw allow 22/tcp || echo -e "${YELLOW}Falha ao configurar UFW para SSH${NC}"
        ufw allow 53/tcp || echo -e "${YELLOW}Falha ao configurar UFW para DNS${NC}"
        ufw allow 53/udp || echo -e "${YELLOW}Falha ao configurar UFW para DNS${NC}"
    fi
}

# Configurar Nginx com SSL (INTERATIVO) - VERSÃO CORRIGIDA
setup_nginx_ssl() {
    show_progress "Configurando Nginx com SSL/HTTPS"
    
    echo
    echo -e "${YELLOW}==========================================${NC}"
    echo -e "${YELLOW}  CONFIGURAÇÃO DE DOMÍNIO E CERTIFICADO  ${NC}"
    echo -e "${YELLOW}==========================================${NC}"
    echo
    echo -e "${BLUE}Para configurar HTTPS, você precisa de um domínio válido.${NC}"
    echo -e "${BLUE}Exemplos: meusite.com, dns.meudominio.com.br${NC}"
    echo
    
    # Solicitar domínio (INTERATIVO)
    DOMAIN=""
    while [ -z "$DOMAIN" ]; do
        DOMAIN=$(ask "Digite o domínio para o certificado SSL (ex: dns.meusite.com):")
        if [ -z "$DOMAIN" ]; then
            echo -e "${RED}Domínio não pode estar vazio!${NC}"
        fi
    done
    
    echo
    echo -e "${GREEN}Domínio selecionado: $DOMAIN${NC}"
    
    # Solicitar email (INTERATIVO) - CORRIGIDO AQUI
    EMAIL=""
    while [ -z "$EMAIL" ]; do
        EMAIL=$(ask "Digite seu email para o certificado SSL (ex: admin@meusite.com):")
        if [ -z "$EMAIL" ]; then
            echo -e "${RED}Email não pode estar vazio!${NC}"
        fi
    done
    
    echo -e "${GREEN}Email selecionado: $EMAIL${NC}"
    echo
    
    # Verificar se é IP (não funciona com Let's Encrypt)
    if [[ $DOMAIN =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo -e "${RED}ERRO: Você inseriu um endereço IP ($DOMAIN)${NC}"
        echo -e "${YELLOW}Let's Encrypt requer um nome de domínio válido, não IP.${NC}"
        echo -e "${YELLOW}Configure um domínio que aponte para este servidor primeiro.${NC}"
        return 1
    fi
    
    # Criar configuração Nginx
    show_progress "Criando configuração Nginx para $DOMAIN"
    
    cat > /etc/nginx/sites-available/br10dashboard << EOF
# BR10 Dashboard - Nginx Configuration
# Proxy reverso para container Docker

server {
    listen 80;
    server_name $DOMAIN;
    
    # Logs
    access_log /var/log/nginx/br10_access.log;
    error_log /var/log/nginx/br10_error.log;
    
    # Proxy para container Docker
    location / {
        proxy_pass http://127.0.0.1:8084;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$server_name;
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
}
EOF
    
    # Habilitar site
    ln -sf /etc/nginx/sites-available/br10dashboard /etc/nginx/sites-enabled/
    
    # Testar configuração Nginx
    nginx -t || {
        echo -e "${RED}Configuração Nginx inválida!${NC}"
        return 1
    }
    
    # Reiniciar Nginx
    systemctl restart nginx || {
        echo -e "${RED}Falha ao reiniciar Nginx!${NC}"
        return 1
    }
    
    check_status "Configuração Nginx"
    
    # Obter certificado SSL com Let's Encrypt
    show_progress "Obtendo certificado SSL para $DOMAIN"
    
    echo
    echo -e "${BLUE}Obtendo certificado SSL com Let's Encrypt...${NC}"
    echo -e "${YELLOW}Isso pode levar alguns minutos.${NC}"
    echo
    
    # Tentar obter certificado (USANDO EMAIL CORRETO)
    if certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email $EMAIL --redirect; then
        echo
        echo -e "${GREEN}✓ Certificado SSL obtido com sucesso!${NC}"
        echo -e "${GREEN}✓ HTTPS configurado e ativo!${NC}"
        echo -e "${GREEN}✓ Redirecionamento HTTP → HTTPS ativado!${NC}"
    else
        echo
        echo -e "${YELLOW}⚠ Falha ao obter certificado SSL automaticamente.${NC}"
        echo -e "${YELLOW}Possíveis causas:${NC}"
        echo -e "${YELLOW}- Domínio não aponta para este servidor${NC}"
        echo -e "${YELLOW}- Firewall bloqueando porta 80/443${NC}"
        echo -e "${YELLOW}- Problemas de conectividade${NC}"
        echo
        echo -e "${BLUE}Você pode tentar manualmente depois:${NC}"
        echo -e "${BLUE}sudo certbot --nginx -d $DOMAIN --email $EMAIL${NC}"
        echo
        return 1
    fi
    
    # Configurar renovação automática
    echo "0 12 * * * /usr/bin/certbot renew --quiet" | crontab -
    check_status "Configuração de renovação automática SSL"
    
    # Salvar configurações para referência
    cat > /etc/br10_ssl.conf << EOF
DOMAIN=$DOMAIN
EMAIL=$EMAIL
CONFIGURED_DATE=$(date '+%Y-%m-%d %H:%M:%S')
EOF
    check_status "Salvamento de configurações SSL"
    
    return 0
}

# Iniciar containers Docker
start_docker_containers() {
    show_progress "Iniciando containers Docker BR10"
    
    # Verificar se estamos no diretório correto
    if [ ! -f "docker-compose.yml" ]; then
        echo -e "${RED}Arquivo docker-compose.yml não encontrado!${NC}"
        echo -e "${YELLOW}Certifique-se de executar este script no diretório br10dashboard${NC}"
        return 1
    fi
    
    # Parar containers existentes
    echo -e "${BLUE}Parando containers existentes...${NC}"
    docker-compose down 2>/dev/null || true
    
    # Construir e iniciar containers
    echo -e "${BLUE}Construindo imagens Docker...${NC}"
    docker-compose build
    check_status "Build das imagens Docker"
    
    echo -e "${BLUE}Iniciando containers...${NC}"
    docker-compose up -d
    check_status "Inicialização dos containers"
    
    # Aguardar containers ficarem prontos
    echo -e "${BLUE}Aguardando containers ficarem prontos...${NC}"
    sleep 30
    
    # Verificar status dos containers
    echo -e "${BLUE}Status dos containers:${NC}"
    docker-compose ps
    
    # Testar conectividade
    echo -e "${BLUE}Testando conectividade interna...${NC}"
    sleep 5
    if curl -s --max-time 10 http://127.0.0.1:8084 >/dev/null; then
        echo -e "${GREEN}✓ Dashboard respondendo na porta 8084${NC}"
    else
        echo -e "${YELLOW}⚠ Dashboard ainda não está respondendo${NC}"
        echo -e "${YELLOW}Aguarde alguns minutos para os containers inicializarem completamente${NC}"
    fi
}

# Configurar reinicio automático dos serviços
setup_auto_restart() {
    show_progress "Configurando reinício automático dos serviços"
    
    # Criar script de inicialização
    cat > /etc/systemd/system/br10-dashboard.service << EOF
[Unit]
Description=BR10 Dashboard Docker Service
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/br10dashboard
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
    
    # Se o diretório atual é br10dashboard, usar ele
    if [ -f "./docker-compose.yml" ]; then
        sed -i "s|/opt/br10dashboard|$(pwd)|g" /etc/systemd/system/br10-dashboard.service
    fi
    
    # Habilitar serviço
    systemctl daemon-reload
    systemctl enable br10-dashboard.service
    check_status "Configuração de inicialização automática"
}

# Função para exibir informações finais
show_final_info() {
    # Obter IP do servidor
    SERVER_IP=$(hostname -I | awk '{print $1}')
    
    # Verificar se SSL foi configurado
    if [ -f /etc/br10_ssl.conf ]; then
        source /etc/br10_ssl.conf
        HTTPS_AVAILABLE=true
    else
        HTTPS_AVAILABLE=false
    fi
    
    echo
    echo -e "${GREEN}=============================================================================${NC}"
    echo -e "${GREEN}               🎉 BR10 DNS SISTEMA INSTALADO COM SUCESSO! 🎉                ${NC}"
    echo -e "${GREEN}=============================================================================${NC}"
    echo
    echo -e "${BLUE}📊 INFORMAÇÕES DE ACESSO:${NC}"
    echo
    
    if [ "$HTTPS_AVAILABLE" = true ]; then
        echo -e "${GREEN}🔒 HTTPS (Recomendado):${NC}"
        echo -e "${GREEN}   https://$DOMAIN${NC}"
        echo
        echo -e "${BLUE}🌐 HTTP (Alternativo):${NC}"
        echo -e "${BLUE}   http://$DOMAIN${NC}"
        echo -e "${BLUE}   http://$SERVER_IP:8084${NC}"
    else
        echo -e "${BLUE}🌐 Acesso via IP:${NC}"
        echo -e "${BLUE}   http://$SERVER_IP:8084${NC}"
    fi
    
    echo
    echo -e "${YELLOW}👤 CREDENCIAIS PADRÃO:${NC}"
    echo -e "${YELLOW}   Usuário: admin${NC}"
    echo -e "${YELLOW}   Senha: admin123${NC}"
    echo
    echo -e "${PURPLE}🐳 COMANDOS DOCKER ÚTEIS:${NC}"
    echo -e "${PURPLE}   Ver logs: docker-compose logs -f${NC}"
    echo -e "${PURPLE}   Parar: docker-compose down${NC}"
    echo -e "${PURPLE}   Reiniciar: docker-compose restart${NC}"
    echo -e "${PURPLE}   Status: docker-compose ps${NC}"
    echo -e "${PURPLE}   Rebuild: docker-compose build --no-cache${NC}"
    echo
    echo -e "${BLUE}📁 DIRETÓRIOS IMPORTANTES:${NC}"
    echo -e "${BLUE}   Logs: ./logs/${NC}"
    echo -e "${BLUE}   Config: ./config/${NC}"
    echo -e "${BLUE}   Dados: ./data/${NC}"
    echo
    
    if [ "$HTTPS_AVAILABLE" = true ]; then
        echo -e "${GREEN}🔐 CERTIFICADO SSL:${NC}"
        echo -e "${GREEN}   ✓ Domínio: $DOMAIN${NC}"
        echo -e "${GREEN}   ✓ Email: $EMAIL${NC}"
        echo -e "${GREEN}   ✓ Renovação automática ativada${NC}"
        echo
    fi
    
    echo -e "${BLUE}🔄 SERVIÇOS AUTOMÁTICOS:${NC}"
    echo -e "${BLUE}   ✓ Docker containers iniciam automaticamente${NC}"
    echo -e "${BLUE}   ✓ Nginx proxy configurado${NC}"
    if [ "$HTTPS_AVAILABLE" = true ]; then
        echo -e "${BLUE}   ✓ Renovação SSL automática (cron)${NC}"
    fi
    echo
    
    echo -e "${YELLOW}⚠ IMPORTANTE:${NC}"
    echo -e "${YELLOW}   - Altere a senha padrão após o primeiro login${NC}"
    echo -e "${YELLOW}   - Configure backup dos dados em ./data/${NC}"
    if [ "$HTTPS_AVAILABLE" = false ]; then
        echo -e "${YELLOW}   - Configure um domínio para habilitar HTTPS${NC}"
    fi
    echo -e "${YELLOW}   - Sistema reinicia automaticamente após reboot${NC}"
    echo
    echo -e "${GREEN}✨ Sistema BR10 DNS pronto para uso em PRODUÇÃO! ✨${NC}"
    echo
}

# Função principal
main() {
    display_banner
    check_root
    
    echo -e "${GREEN}Bem-vindo ao Setup Completo do Sistema BR10 DNS!${NC}"
    echo
    echo -e "${BLUE}Este script irá:${NC}"
    echo -e " ${GREEN}1.${NC} Verificar e instalar Docker + Docker Compose"
    echo -e " ${GREEN}2.${NC} Instalar e configurar Nginx como proxy reverso"
    echo -e " ${GREEN}3.${NC} Configurar SSL/HTTPS com Let's Encrypt (INTERATIVO)"
    echo -e " ${GREEN}4.${NC} Iniciar containers Docker do BR10"
    echo -e " ${GREEN}5.${NC} Configurar integração completa e reinício automático"
    echo
    echo -e "${YELLOW}⚠ REQUISITOS:${NC}"
    echo -e "${YELLOW}   - Domínio válido apontando para este servidor (para HTTPS)${NC}"
    echo -e "${YELLOW}   - Portas 80, 443 e 53 abertas no firewall${NC}"
    echo -e "${YELLOW}   - Acesso root (sudo)${NC}"
    echo
    
    read -p "Deseja continuar com a instalação? (S/n): " confirm
    if [[ "$confirm" == [Nn] ]]; then
        echo -e "${YELLOW}Instalação cancelada pelo usuário${NC}"
        exit 0
    fi
    
    echo
    echo -e "${BLUE}🚀 Iniciando instalação...${NC}"
    
    # Executar etapas
    check_docker
    install_nginx_requirements
    start_docker_containers
    
    # Configurar Nginx + SSL (INTERATIVO)
    echo
    echo -e "${BLUE}Configurando Nginx e SSL...${NC}"
    if setup_nginx_ssl; then
        SSL_SUCCESS=true
        echo -e "${GREEN}✓ SSL configurado com sucesso!${NC}"
    else
        SSL_SUCCESS=false
        echo -e "${YELLOW}Continuando sem SSL. Você pode configurar depois.${NC}"
    fi
    
    # Configurar reinício automático
    setup_auto_restart
    
    # Informações finais
    show_final_info
    
    echo -e "${GREEN}🎯 Instalação concluída!${NC}"
    
    # Mostrar próximos passos
    echo -e "${BLUE}📋 PRÓXIMOS PASSOS:${NC}"
    echo -e "${BLUE}1. Acesse o dashboard via HTTPS${NC}"
    echo -e "${BLUE}2. Faça login com as credenciais padrão${NC}"
    echo -e "${BLUE}3. Altere a senha do admin${NC}"
    echo -e "${BLUE}4. Configure o cliente API em br10config/${NC}"
    echo
}

# Executar função principal
main "$@"
