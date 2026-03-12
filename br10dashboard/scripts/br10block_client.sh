#!/bin/bash
# =============================================================================
# BR10 Block Client - Script de Sincronização com Unbound
# =============================================================================
# Descrição:
#   Este script é executado no servidor cliente (onde o Unbound está rodando).
#   Ele busca a lista de domínios bloqueados no servidor BR10 Block Web,
#   gera o arquivo de zona RPZ para o Unbound e recarrega o serviço.
#
# Uso:
#   ./br10block_client.sh [--force] [--dry-run] [--debug]
#
# Opções:
#   --force     Força atualização mesmo sem mudanças
#   --dry-run   Simula sem aplicar mudanças
#   --debug     Habilita saída detalhada
#
# Instalação (crontab):
#   */5 * * * * /opt/br10dashboard/scripts/br10block_client.sh >> /var/log/br10block_client.log 2>&1
#
# Autor: BR10 Team
# Versão: 3.0.0
# =============================================================================

set -euo pipefail

# =============================================================================
# CONFIGURAÇÕES (ajuste conforme necessário)
# =============================================================================

# URL do servidor BR10 Block Web
BR10_SERVER_URL="${BR10_SERVER_URL:-http://SEU_SERVIDOR:8084}"

# API Key do cliente (gerada no painel admin do servidor)
BR10_API_KEY="${BR10_API_KEY:-SUA_API_KEY_AQUI}"

# Formato da lista: rpz (recomendado para Unbound) ou txt
BR10_FORMAT="${BR10_FORMAT:-rpz}"

# Arquivo de zona RPZ do Unbound
UNBOUND_ZONE_FILE="${UNBOUND_ZONE_FILE:-/var/lib/unbound/br10block-rpz.zone}"

# Arquivo de lista de domínios em texto plano
BLOCKED_DOMAINS_FILE="${BLOCKED_DOMAINS_FILE:-/var/lib/br10api/blocked_domains.txt}"

# Diretório de dados do cliente
DATA_DIR="${DATA_DIR:-/opt/br10dashboard/data}"

# Arquivo de log
LOG_FILE="${LOG_FILE:-/var/log/br10block_client.log}"

# Arquivo de estado (para detectar mudanças)
STATE_FILE="${DATA_DIR}/last_sync.json"

# Arquivo temporário para download
TMP_FILE="${DATA_DIR}/domains_new.tmp"

# Timeout para requisições HTTP (segundos)
HTTP_TIMEOUT="${HTTP_TIMEOUT:-30}"

# Número máximo de tentativas em caso de falha
MAX_RETRIES="${MAX_RETRIES:-3}"

# Intervalo entre tentativas (segundos)
RETRY_INTERVAL="${RETRY_INTERVAL:-10}"

# Redis (para cache de estatísticas no dashboard)
REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_DB="${REDIS_DB:-0}"

# =============================================================================
# VARIÁVEIS INTERNAS
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORCE_UPDATE=false
DRY_RUN=false
DEBUG=false
START_TIME=$(date +%s)
SCRIPT_VERSION="3.0.0"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo "${timestamp} [${level}] ${message}" >> "${LOG_FILE}"
    
    if [[ "${DEBUG}" == "true" ]] || [[ "${level}" != "DEBUG" ]]; then
        case "${level}" in
            "ERROR")   echo -e "${RED}[${level}]${NC} ${message}" ;;
            "WARN")    echo -e "${YELLOW}[${level}]${NC} ${message}" ;;
            "SUCCESS") echo -e "${GREEN}[${level}]${NC} ${message}" ;;
            "INFO")    echo -e "${BLUE}[${level}]${NC} ${message}" ;;
            "DEBUG")   [[ "${DEBUG}" == "true" ]] && echo -e "${CYAN}[${level}]${NC} ${message}" ;;
            *)         echo "[${level}] ${message}" ;;
        esac
    fi
}

log_info()    { log "INFO"    "$@"; }
log_warn()    { log "WARN"    "$@"; }
log_error()   { log "ERROR"   "$@"; }
log_success() { log "SUCCESS" "$@"; }
log_debug()   { log "DEBUG"   "$@"; }

die() {
    log_error "$*"
    exit 1
}

# Verificar dependências
check_dependencies() {
    local deps=("curl" "jq" "unbound-control")
    local missing=()
    
    for dep in "${deps[@]}"; do
        if ! command -v "${dep}" &>/dev/null; then
            missing+=("${dep}")
        fi
    done
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        die "Dependências faltando: ${missing[*]}. Instale com: apt-get install -y ${missing[*]}"
    fi
    
    log_debug "Todas as dependências encontradas"
}

# Criar diretórios necessários
ensure_directories() {
    mkdir -p "${DATA_DIR}"
    mkdir -p "$(dirname "${LOG_FILE}")"
    mkdir -p "$(dirname "${UNBOUND_ZONE_FILE}")"
    mkdir -p "$(dirname "${BLOCKED_DOMAINS_FILE}")"
    log_debug "Diretórios criados/verificados"
}

# Verificar configuração
check_config() {
    if [[ "${BR10_SERVER_URL}" == "http://SEU_SERVIDOR:8084" ]]; then
        die "Configure BR10_SERVER_URL no script ou variável de ambiente"
    fi
    
    if [[ "${BR10_API_KEY}" == "SUA_API_KEY_AQUI" ]]; then
        die "Configure BR10_API_KEY no script ou variável de ambiente"
    fi
    
    log_debug "Configuração verificada: servidor=${BR10_SERVER_URL}"
}

# Fazer requisição HTTP com retry
http_request() {
    local url="$1"
    local output_file="${2:-}"
    local attempt=1
    
    while [[ ${attempt} -le ${MAX_RETRIES} ]]; do
        log_debug "Tentativa ${attempt}/${MAX_RETRIES}: GET ${url}"
        
        local curl_args=(
            --silent
            --show-error
            --fail
            --max-time "${HTTP_TIMEOUT}"
            --header "X-API-Key: ${BR10_API_KEY}"
            --header "User-Agent: BR10BlockClient/${SCRIPT_VERSION}"
        )
        
        if [[ -n "${output_file}" ]]; then
            curl_args+=(--output "${output_file}")
        fi
        
        if curl "${curl_args[@]}" "${url}"; then
            return 0
        else
            local exit_code=$?
            log_warn "Tentativa ${attempt} falhou (código ${exit_code})"
            
            if [[ ${attempt} -lt ${MAX_RETRIES} ]]; then
                log_info "Aguardando ${RETRY_INTERVAL}s antes de nova tentativa..."
                sleep "${RETRY_INTERVAL}"
            fi
        fi
        
        ((attempt++))
    done
    
    return 1
}

# Verificar conectividade com o servidor
check_server_connectivity() {
    log_info "Verificando conectividade com o servidor..."
    
    local ping_url="${BR10_SERVER_URL}/api/v1/client/ping"
    local response
    
    if response=$(http_request "${ping_url}" 2>&1); then
        local status
        status=$(echo "${response}" | jq -r '.status // "unknown"' 2>/dev/null || echo "ok")
        log_success "Servidor acessível: ${status}"
        return 0
    else
        log_error "Servidor inacessível: ${BR10_SERVER_URL}"
        return 1
    fi
}

# Buscar informações de status do servidor
get_server_status() {
    local status_url="${BR10_SERVER_URL}/api/v1/client/status"
    local response
    
    if response=$(http_request "${status_url}" 2>&1); then
        local total_domains
        total_domains=$(echo "${response}" | jq -r '.total_domains // 0' 2>/dev/null || echo "0")
        local last_update
        last_update=$(echo "${response}" | jq -r '.last_update // "unknown"' 2>/dev/null || echo "unknown")
        
        log_info "Servidor: ${total_domains} domínios, última atualização: ${last_update}"
        echo "${response}"
        return 0
    else
        log_warn "Não foi possível obter status do servidor"
        return 1
    fi
}

# Calcular hash do arquivo atual
get_file_hash() {
    local file="$1"
    if [[ -f "${file}" ]]; then
        sha256sum "${file}" | awk '{print $1}'
    else
        echo "none"
    fi
}

# Carregar estado anterior
load_state() {
    if [[ -f "${STATE_FILE}" ]]; then
        cat "${STATE_FILE}"
    else
        echo '{"last_sync": null, "domains_count": 0, "file_hash": "none"}'
    fi
}

# Salvar estado atual
save_state() {
    local domains_count="$1"
    local file_hash="$2"
    local timestamp
    timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    
    cat > "${STATE_FILE}" << EOF
{
    "last_sync": "${timestamp}",
    "domains_count": ${domains_count},
    "file_hash": "${file_hash}",
    "server_url": "${BR10_SERVER_URL}",
    "script_version": "${SCRIPT_VERSION}"
}
EOF
    log_debug "Estado salvo: ${domains_count} domínios, hash=${file_hash:0:8}..."
}

# Baixar lista de domínios do servidor
download_domains() {
    local format="${BR10_FORMAT}"
    local url="${BR10_SERVER_URL}/api/v1/client/domains?format=${format}"
    
    log_info "Baixando lista de domínios (formato: ${format})..."
    
    if http_request "${url}" "${TMP_FILE}"; then
        local line_count
        line_count=$(wc -l < "${TMP_FILE}" 2>/dev/null || echo "0")
        log_success "Lista baixada: ${line_count} linhas"
        return 0
    else
        log_error "Falha ao baixar lista de domínios"
        rm -f "${TMP_FILE}"
        return 1
    fi
}

# Contar domínios no arquivo
count_domains() {
    local file="$1"
    local format="${BR10_FORMAT}"
    
    if [[ "${format}" == "rpz" ]]; then
        # Contar entradas RPZ (linhas que terminam com CNAME .)
        grep -c "CNAME \." "${file}" 2>/dev/null || echo "0"
    else
        # Contar linhas não-vazias e não-comentários
        grep -c "^[^#]" "${file}" 2>/dev/null || echo "0"
    fi
}

# Validar arquivo baixado
validate_download() {
    local file="$1"
    
    if [[ ! -f "${file}" ]]; then
        log_error "Arquivo de download não encontrado: ${file}"
        return 1
    fi
    
    local size
    size=$(stat -c%s "${file}" 2>/dev/null || echo "0")
    
    if [[ ${size} -eq 0 ]]; then
        log_error "Arquivo de download está vazio"
        return 1
    fi
    
    # Verificar se é JSON de erro
    if jq -e '.error' "${file}" &>/dev/null 2>&1; then
        local error_msg
        error_msg=$(jq -r '.error' "${file}")
        log_error "Servidor retornou erro: ${error_msg}"
        rm -f "${file}"
        return 1
    fi
    
    local domain_count
    domain_count=$(count_domains "${file}")
    
    if [[ ${domain_count} -eq 0 ]]; then
        log_warn "Arquivo baixado não contém domínios válidos"
        return 1
    fi
    
    log_debug "Arquivo validado: ${domain_count} domínios"
    return 0
}

# Aplicar lista no Unbound (formato RPZ)
apply_rpz_to_unbound() {
    local new_file="$1"
    
    log_info "Aplicando lista RPZ no Unbound..."
    
    # Backup do arquivo atual
    if [[ -f "${UNBOUND_ZONE_FILE}" ]]; then
        cp "${UNBOUND_ZONE_FILE}" "${UNBOUND_ZONE_FILE}.bak"
        log_debug "Backup criado: ${UNBOUND_ZONE_FILE}.bak"
    fi
    
    # Copiar novo arquivo
    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "[DRY-RUN] Simulando cópia para ${UNBOUND_ZONE_FILE}"
    else
        cp "${new_file}" "${UNBOUND_ZONE_FILE}"
        chown unbound:unbound "${UNBOUND_ZONE_FILE}" 2>/dev/null || true
        chmod 644 "${UNBOUND_ZONE_FILE}"
        log_debug "Arquivo copiado para ${UNBOUND_ZONE_FILE}"
    fi
    
    # Recarregar Unbound
    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "[DRY-RUN] Simulando reload do Unbound"
    else
        if unbound-control reload 2>/dev/null; then
            log_success "Unbound recarregado com sucesso"
        else
            log_warn "Falha ao recarregar Unbound via unbound-control, tentando systemctl..."
            if systemctl reload unbound 2>/dev/null || systemctl restart unbound 2>/dev/null; then
                log_success "Unbound reiniciado via systemctl"
            else
                log_error "Falha ao recarregar Unbound"
                # Restaurar backup
                if [[ -f "${UNBOUND_ZONE_FILE}.bak" ]]; then
                    cp "${UNBOUND_ZONE_FILE}.bak" "${UNBOUND_ZONE_FILE}"
                    unbound-control reload 2>/dev/null || true
                    log_warn "Backup restaurado"
                fi
                return 1
            fi
        fi
    fi
    
    return 0
}

# Salvar lista em texto plano (para o dashboard)
save_txt_list() {
    local source_file="$1"
    local format="${BR10_FORMAT}"
    
    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "[DRY-RUN] Simulando salvamento da lista TXT"
        return 0
    fi
    
    if [[ "${format}" == "rpz" ]]; then
        # Extrair domínios do RPZ (formato: domain CNAME .)
        grep "CNAME \." "${source_file}" | awk '{print $1}' | sed 's/\.$//' > "${BLOCKED_DOMAINS_FILE}"
    else
        # Já está em formato TXT
        cp "${source_file}" "${BLOCKED_DOMAINS_FILE}"
    fi
    
    local count
    count=$(wc -l < "${BLOCKED_DOMAINS_FILE}" 2>/dev/null || echo "0")
    log_debug "Lista TXT salva: ${count} domínios em ${BLOCKED_DOMAINS_FILE}"
}

# Atualizar estatísticas no Redis
update_redis_stats() {
    local domains_count="$1"
    local sync_status="$2"
    local timestamp
    timestamp=$(date +%s)
    
    if ! command -v redis-cli &>/dev/null; then
        log_debug "redis-cli não disponível, pulando atualização de stats"
        return 0
    fi
    
    if ! redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" -n "${REDIS_DB}" PING &>/dev/null 2>&1; then
        log_debug "Redis não disponível, pulando atualização de stats"
        return 0
    fi
    
    log_debug "Atualizando estatísticas no Redis..."
    
    redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" -n "${REDIS_DB}" \
        HSET "br10block:sync:latest" \
            "domains_count" "${domains_count}" \
            "sync_status" "${sync_status}" \
            "last_sync" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
            "server_url" "${BR10_SERVER_URL}" \
            "timestamp" "${timestamp}" \
        &>/dev/null
    
    # Histórico de sincronizações (últimas 100)
    redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" -n "${REDIS_DB}" \
        LPUSH "br10block:sync:history" \
        "{\"timestamp\":${timestamp},\"domains\":${domains_count},\"status\":\"${sync_status}\"}" \
        &>/dev/null
    
    redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" -n "${REDIS_DB}" \
        LTRIM "br10block:sync:history" 0 99 \
        &>/dev/null
    
    log_debug "Estatísticas Redis atualizadas"
}

# Iniciar sincronização no servidor (obtém sync_id para rastreamento)
start_sync_on_server() {
    local start_url="${BR10_SERVER_URL}/api/v1/client/sync/start"
    local response
    
    log_debug "Registrando início de sincronização no servidor..."
    
    response=$(curl --silent --max-time "${HTTP_TIMEOUT}" \
        --header "X-API-Key: ${BR10_API_KEY}" \
        --header "Content-Type: application/json" \
        --request POST \
        "${start_url}" 2>/dev/null || echo "{}")
    
    local sync_id
    sync_id=$(echo "${response}" | jq -r '.sync_id // empty' 2>/dev/null || echo "")
    
    if [[ -n "${sync_id}" ]]; then
        log_debug "sync_id obtido: ${sync_id}"
        echo "${sync_id}"
    else
        log_warn "Não foi possível obter sync_id (não crítico)"
        echo ""
    fi
}

# Notificar servidor sobre sincronização concluída
notify_server() {
    local domains_applied="$1"
    local status="$2"
    local duration="$3"
    local sync_id="${4:-}"
    
    local notify_url="${BR10_SERVER_URL}/api/v1/client/sync/complete"
    local payload
    
    if [[ -n "${sync_id}" ]]; then
        payload="{\"sync_id\": ${sync_id}, \"domains_applied\": ${domains_applied}, \"status\": \"${status}\", \"duration_seconds\": ${duration}, \"message\": \"Sincronização concluída pelo cliente\"}"
    else
        payload="{\"domains_applied\": ${domains_applied}, \"status\": \"${status}\", \"duration_seconds\": ${duration}, \"message\": \"Sincronização concluída pelo cliente\"}"
    fi
    
    log_debug "Notificando servidor sobre sincronização..."
    
    if curl --silent --fail --max-time "${HTTP_TIMEOUT}" \
        --header "X-API-Key: ${BR10_API_KEY}" \
        --header "Content-Type: application/json" \
        --data "${payload}" \
        --request POST \
        "${notify_url}" &>/dev/null; then
        log_debug "Servidor notificado com sucesso"
    else
        log_warn "Falha ao notificar servidor (não crítico)"
    fi
}

# Verificar se atualização é necessária
needs_update() {
    local state
    state=$(load_state)
    
    local last_sync
    last_sync=$(echo "${state}" | jq -r '.last_sync // "null"' 2>/dev/null || echo "null")
    
    if [[ "${last_sync}" == "null" ]]; then
        log_info "Primeira sincronização"
        return 0
    fi
    
    if [[ "${FORCE_UPDATE}" == "true" ]]; then
        log_info "Atualização forçada"
        return 0
    fi
    
    # Verificar hash do arquivo atual
    local current_hash
    current_hash=$(get_file_hash "${UNBOUND_ZONE_FILE}")
    local saved_hash
    saved_hash=$(echo "${state}" | jq -r '.file_hash // "none"' 2>/dev/null || echo "none")
    
    if [[ "${current_hash}" != "${saved_hash}" ]]; then
        log_info "Arquivo local modificado externamente, sincronizando..."
        return 0
    fi
    
    # Verificar status no servidor
    local status_url="${BR10_SERVER_URL}/api/v1/client/status"
    local response
    if response=$(http_request "${status_url}" 2>&1); then
        local server_domains
        server_domains=$(echo "${response}" | jq -r '.total_domains // 0' 2>/dev/null || echo "0")
        local saved_domains
        saved_domains=$(echo "${state}" | jq -r '.domains_count // 0' 2>/dev/null || echo "0")
        
        if [[ "${server_domains}" != "${saved_domains}" ]]; then
            log_info "Servidor tem ${server_domains} domínios, local tem ${saved_domains}. Atualizando..."
            return 0
        fi
    fi
    
    log_info "Lista já está atualizada (${last_sync})"
    return 1
}

# Processar argumentos da linha de comando
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force)
                FORCE_UPDATE=true
                log_debug "Modo force ativado"
                ;;
            --dry-run)
                DRY_RUN=true
                log_debug "Modo dry-run ativado"
                ;;
            --debug)
                DEBUG=true
                log_debug "Modo debug ativado"
                ;;
            --help|-h)
                echo "Uso: $0 [--force] [--dry-run] [--debug]"
                echo ""
                echo "Opções:"
                echo "  --force    Força atualização mesmo sem mudanças"
                echo "  --dry-run  Simula sem aplicar mudanças"
                echo "  --debug    Habilita saída detalhada"
                exit 0
                ;;
            *)
                log_warn "Argumento desconhecido: $1"
                ;;
        esac
        shift
    done
}

# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

main() {
    parse_args "$@"
    
    log_info "=============================================="
    log_info "BR10 Block Client v${SCRIPT_VERSION} iniciado"
    log_info "=============================================="
    log_info "Servidor: ${BR10_SERVER_URL}"
    log_info "Formato: ${BR10_FORMAT}"
    [[ "${DRY_RUN}" == "true" ]] && log_warn "MODO DRY-RUN ATIVO - Nenhuma mudança será aplicada"
    
    # Verificações iniciais
    check_dependencies
    ensure_directories
    check_config
    
    # Verificar conectividade
    if ! check_server_connectivity; then
        update_redis_stats "0" "connection_error"
        die "Não foi possível conectar ao servidor BR10"
    fi
    
    # Verificar se atualização é necessária
    if ! needs_update; then
        log_success "Nenhuma atualização necessária"
        exit 0
    fi
    
    # Registrar início no servidor e obter sync_id
    SYNC_ID=$(start_sync_on_server || echo "")
    
    # Obter status do servidor
    get_server_status || true
    
    # Baixar nova lista
    if ! download_domains; then
        update_redis_stats "0" "download_error"
        die "Falha ao baixar lista de domínios"
    fi
    
    # Validar download
    if ! validate_download "${TMP_FILE}"; then
        rm -f "${TMP_FILE}"
        update_redis_stats "0" "validation_error"
        die "Arquivo baixado inválido"
    fi
    
    # Contar domínios
    DOMAIN_COUNT=$(count_domains "${TMP_FILE}")
    log_info "Domínios na nova lista: ${DOMAIN_COUNT}"
    
    # Aplicar no Unbound
    if ! apply_rpz_to_unbound "${TMP_FILE}"; then
        rm -f "${TMP_FILE}"
        update_redis_stats "${DOMAIN_COUNT}" "apply_error"
        die "Falha ao aplicar lista no Unbound"
    fi
    
    # Salvar lista TXT para o dashboard
    save_txt_list "${TMP_FILE}"
    
    # Calcular duração
    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - START_TIME))
    
    # Salvar estado
    local new_hash
    new_hash=$(get_file_hash "${UNBOUND_ZONE_FILE}")
    save_state "${DOMAIN_COUNT}" "${new_hash}"
    
    # Atualizar Redis
    update_redis_stats "${DOMAIN_COUNT}" "success"
    
    # Notificar servidor
    notify_server "${DOMAIN_COUNT}" "success" "${duration}" "${SYNC_ID:-}"
    
    # Limpar arquivo temporário
    rm -f "${TMP_FILE}"
    
    log_success "=============================================="
    log_success "Sincronização concluída em ${duration}s"
    log_success "Domínios aplicados: ${DOMAIN_COUNT}"
    log_success "=============================================="
    
    exit 0
}

# Capturar erros não tratados
trap 'log_error "Erro inesperado na linha $LINENO. Código: $?"; update_redis_stats "0" "unexpected_error"; exit 1' ERR

# Executar
main "$@"
