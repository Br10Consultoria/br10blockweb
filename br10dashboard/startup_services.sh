#!/bin/bash

# Cores para formatação de saída
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Diretórios
DASHBOARD_DIR="/opt/br10dashboard"
API_DIR="/home/br10config"

# Configurações do Telegram
# Substitua os valores abaixo com seu token e chat_id
TELEGRAM_TOKEN="8033250693:AAGLlldhR5DIbnCMG5ELisQPYX8OAHFKYEk"
TELEGRAM_CHAT_ID="-4781569559"


# Função para verificar status
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[OK]${NC} $1"
        return 0
    else
        echo -e "${RED}[FALHA]${NC} $1"
        echo "Erro na etapa: $1. Verifique os logs para mais informações."
        return 1
    fi
}

# Função para mostrar progresso
show_progress() {
    echo -e "\n${YELLOW}>>> $1 <<<${NC}"
}

# Função para capturar logs da sessão tmux
capture_tmux_logs() {
    session_name=$1
    log_file="/tmp/${session_name}_log.txt"
    
    # Capturar a saída atual da sessão tmux
    tmux capture-pane -t "$session_name" -p > "$log_file"
    
    # Retornar o conteúdo do log
    cat "$log_file"
}

# Função para verificar se um processo está rodando e capturar erros
check_process_running() {
    service_name=$1
    check_string=$2
    max_attempts=$3
    session_name=$4
    
    show_progress "Verificando se $service_name está rodando..."
    
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if pgrep -f "$check_string" > /dev/null; then
            echo -e "${GREEN}[OK]${NC} $service_name está rodando (tentativa $attempt/$max_attempts)"
            return 0
        else
            echo -e "${YELLOW}[AGUARDANDO]${NC} $service_name ainda não está rodando (tentativa $attempt/$max_attempts)"
            
            # Se for a última tentativa, capturar os logs para diagnóstico
            if [ $attempt -eq $max_attempts ]; then
                logs=$(capture_tmux_logs "$session_name")
                echo -e "\n${YELLOW}Logs da sessão $session_name:${NC}"
                echo "$logs"
                
                # Verificar erros específicos nos logs
                if echo "$logs" | grep -q "ModuleNotFoundError"; then
                    missing_module=$(echo "$logs" | grep "ModuleNotFoundError" | grep -o "'[^']*'" | tr -d "'")
                    echo -e "${RED}[ERRO]${NC} Módulo Python faltando: $missing_module"
                    return 2  # Código de retorno específico para módulo faltando
                fi
            fi
            
            sleep 5
        fi
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}[FALHA]${NC} $service_name não iniciou após $max_attempts tentativas"
    return 1
}

# Função para enviar mensagem via Telegram
send_telegram_message() {
    message="$1"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" \
        -d text="${message}" \
        -d parse_mode="Markdown" > /dev/null
        
    check_status "Envio de mensagem via Telegram"
}

# Função principal
main() {
    show_progress "Iniciando script de configuração pós-reinicialização"
    
    # Obter hostname do servidor
    HOSTNAME=$(hostname)
    check_status "Obtendo hostname do servidor"
    
    # Status inicial para relatório
    STATUS_REPORT="*Status das sessões no servidor ${HOSTNAME}*\n\n"
    
    # Garantir que diretório inicial existe
    cd /home || {
        echo -e "${RED}[FALHA]${NC} Não foi possível acessar o diretório /home"
        STATUS_REPORT="${STATUS_REPORT}❌ Falha ao acessar o diretório /home\n"
        send_telegram_message "${STATUS_REPORT}"
        exit 1
    }
    
    # Instalar dependências do sistema
    show_progress "Instalando dependências do sistema"
    apt update
    if ! check_status "Atualização do apt"; then
        STATUS_REPORT="${STATUS_REPORT}❌ Falha na atualização do apt\n"
        send_telegram_message "${STATUS_REPORT}"
        exit 1
    fi
    
    apt install -y python3.11-venv tmux curl
    if ! check_status "Instalação do python3.11-venv, tmux e curl"; then
        STATUS_REPORT="${STATUS_REPORT}❌ Falha na instalação de dependências\n"
        send_telegram_message "${STATUS_REPORT}"
        exit 1
    fi
    
    # Encerrar sessões tmux existentes, se houver
    tmux kill-session -t br10api 2>/dev/null
    tmux kill-session -t web01 2>/dev/null
    
    # =============================================
    # Sessão 1: API
    # =============================================
    show_progress "Configurando sessão tmux para br10api"
    
    # Criar nova sessão tmux
    tmux new-session -d -s br10api
    if ! check_status "Criação da sessão tmux br10api"; then
        STATUS_REPORT="${STATUS_REPORT}❌ Falha ao criar sessão br10api\n"
        send_telegram_message "${STATUS_REPORT}"
        exit 1
    fi
    
    # Enviar comandos para a sessão
    tmux send-keys -t br10api "cd $API_DIR" C-m
    
    # Criar ambiente virtual Python
    tmux send-keys -t br10api "if [ ! -d \"$API_DIR/venv\" ]; then" C-m
    tmux send-keys -t br10api "    python3 -m venv \"$API_DIR/venv\"" C-m
    tmux send-keys -t br10api "    echo \"Criação do ambiente virtual Python concluída\"" C-m
    tmux send-keys -t br10api "else" C-m
    tmux send-keys -t br10api "    echo \"Ambiente virtual Python já existe\"" C-m
    tmux send-keys -t br10api "fi" C-m
    
    # Ativar ambiente virtual e instalar dependências
    tmux send-keys -t br10api "source \"$API_DIR/venv/bin/activate\"" C-m
    tmux send-keys -t br10api "pip install flask requests werkzeug requests psutil pycryptodome redis python-dotenv cryptography difflib" C-m
    
    # Iniciar o serviço
    tmux send-keys -t br10api "echo \"Iniciando br10api...\"" C-m
    tmux send-keys -t br10api "python3 $API_DIR/api_client.py" C-m
    
    # Aguardar e verificar se o serviço está rodando
    sleep 10
    api_status=$(check_process_running "br10api" "python3 $API_DIR/api_client.py" 6 "br10api")
    api_exit_code=$?
    
    if [ $api_exit_code -eq 0 ]; then
        STATUS_REPORT="${STATUS_REPORT}✅ Serviço br10api iniciado com sucesso\n"
    elif [ $api_exit_code -eq 2 ]; then
        # Módulo faltando detectado
        logs=$(capture_tmux_logs "br10api")
        missing_module=$(echo "$logs" | grep "ModuleNotFoundError" | grep -o "'[^']*'" | tr -d "'" | head -1)
        
        STATUS_REPORT="${STATUS_REPORT}❌ Falha ao iniciar serviço br10api: Módulo Python faltando: $missing_module\n"
        
        # Tentar corrigir o problema instalando o módulo faltando
        tmux send-keys -t br10api C-c
        sleep 2
        tmux send-keys -t br10api "pip install $missing_module" C-m
        sleep 5
        tmux send-keys -t br10api "python3 $API_DIR/api_client.py" C-m
        
        # Verificar novamente
        sleep 10
        if check_process_running "br10api" "python3 $API_DIR/api_client.py" 3 "br10api"; then
            STATUS_REPORT="${STATUS_REPORT}✅ Serviço br10api iniciado com sucesso após correção\n"
        else
            STATUS_REPORT="${STATUS_REPORT}❌ Falha ao iniciar serviço br10api mesmo após tentativa de correção\n"
            # Continuar com a próxima sessão mesmo com falha
        fi
    else
        logs=$(capture_tmux_logs "br10api")
        STATUS_REPORT="${STATUS_REPORT}❌ Falha ao iniciar serviço br10api\n\`\`\`\n${logs}\n\`\`\`\n"
        # Continuar com a próxima sessão mesmo com falha
    fi
    
    # =============================================
    # Sessão 2: Web01
    # =============================================
    show_progress "Configurando sessão tmux para web01"
    
    # Criar nova sessão tmux
    tmux new-session -d -s web01
    if ! check_status "Criação da sessão tmux web01"; then
        STATUS_REPORT="${STATUS_REPORT}❌ Falha ao criar sessão web01\n"
        send_telegram_message "${STATUS_REPORT}"
        exit 1
    fi
    
    # Enviar comandos para a sessão
    tmux send-keys -t web01 "cd $DASHBOARD_DIR" C-m
    
    # Criar ambiente virtual Python
    tmux send-keys -t web01 "if [ ! -d \"$DASHBOARD_DIR/venv\" ]; then" C-m
    tmux send-keys -t web01 "    python3 -m venv \"$DASHBOARD_DIR/venv\"" C-m
    tmux send-keys -t web01 "    echo \"Criação do ambiente virtual Python concluída\"" C-m
    tmux send-keys -t web01 "else" C-m
    tmux send-keys -t web01 "    echo \"Ambiente virtual Python já existe\"" C-m
    tmux send-keys -t web01 "fi" C-m
    
    # Ativar ambiente virtual e instalar dependências (adicionando python-dotenv)
    tmux send-keys -t web01 "source \"$DASHBOARD_DIR/venv/bin/activate\"" C-m
    tmux send-keys -t web01 "pip install flask requests werkzeug requests psutil pycryptodome redis python-dotenv cryptography difflib" C-m
    
    # Iniciar o serviço
    tmux send-keys -t web01 "echo \"Iniciando web01...\"" C-m
    tmux send-keys -t web01 "python3 $DASHBOARD_DIR/app.py" C-m
    
    # Aguardar e verificar se o serviço está rodando
    sleep 10
    web_status=$(check_process_running "web01" "python3 $DASHBOARD_DIR/app.py" 6 "web01")
    web_exit_code=$?
    
    if [ $web_exit_code -eq 0 ]; then
        STATUS_REPORT="${STATUS_REPORT}✅ Serviço web01 iniciado com sucesso\n"
    elif [ $web_exit_code -eq 2 ]; then
        # Módulo faltando detectado
        logs=$(capture_tmux_logs "web01")
        missing_module=$(echo "$logs" | grep "ModuleNotFoundError" | grep -o "'[^']*'" | tr -d "'" | head -1)
        
        STATUS_REPORT="${STATUS_REPORT}❌ Falha ao iniciar serviço web01: Módulo Python faltando: $missing_module\n"
        
        # Tentar corrigir o problema instalando o módulo faltando
        tmux send-keys -t web01 C-c
        sleep 2
        tmux send-keys -t web01 "pip install $missing_module" C-m
        sleep 5
        tmux send-keys -t web01 "python3 $DASHBOARD_DIR/app.py" C-m
        
        # Verificar novamente
        sleep 10
        if check_process_running "web01" "python3 $DASHBOARD_DIR/app.py" 3 "web01"; then
            STATUS_REPORT="${STATUS_REPORT}✅ Serviço web01 iniciado com sucesso após correção\n"
        else
            STATUS_REPORT="${STATUS_REPORT}❌ Falha ao iniciar serviço web01 mesmo após tentativa de correção\n"
        fi
    else
        logs=$(capture_tmux_logs "web01")
        STATUS_REPORT="${STATUS_REPORT}❌ Falha ao iniciar serviço web01\n\`\`\`\n${logs}\n\`\`\`\n"
    fi
    
    # Verificar e listar todas as sessões tmux
    show_progress "Verificando status final das sessões tmux"
    
    # Capturar saída do comando tmux ls
    TMUX_SESSIONS=$(tmux list-sessions 2>/dev/null || echo "Nenhuma sessão encontrada")
    
    # Verificar status atual dos processos
    BR10API_RUNNING=$(pgrep -f "python3 $API_DIR/api_client.py" > /dev/null && echo "✅ Rodando" || echo "❌ Parado")
    WEB01_RUNNING=$(pgrep -f "python3 $DASHBOARD_DIR/app.py" > /dev/null && echo "✅ Rodando" || echo "❌ Parado")
    
    # Adicionar informações das sessões ao relatório
    STATUS_REPORT="${STATUS_REPORT}\n*Status atual dos processos*:\n"
    STATUS_REPORT="${STATUS_REPORT}• br10api: ${BR10API_RUNNING}\n"
    STATUS_REPORT="${STATUS_REPORT}• web01: ${WEB01_RUNNING}\n"
    
    STATUS_REPORT="${STATUS_REPORT}\n*Lista de sessões tmux*:\n\`\`\`\n${TMUX_SESSIONS}\n\`\`\`"
    
    # Enviar relatório final via Telegram
    show_progress "Enviando relatório de status via Telegram"
    send_telegram_message "${STATUS_REPORT}"
    
    show_progress "Configuração concluída! Relatório enviado via Telegram."
}

# Executar a função principal
main
