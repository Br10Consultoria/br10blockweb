#!/bin/bash
# Script para coletar estatísticas do Unbound e salvar no Redis
# BR10 DNS - Integration Script v2.0 (IPv4/IPv6 + RPZ + uptime)

LOG_FILE="/var/log/br10_unbound_redis.log"
REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-6379}"

log() {
    echo "$(date +"%Y-%m-%d %H:%M:%S") - $1" >> "$LOG_FILE"
}

redis_cmd() {
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" "$@" 2>/dev/null
}

log "Iniciando coleta de estatísticas do Unbound"

# Verificar Redis
if ! redis_cmd PING | grep -q PONG; then
    log "ERRO: Redis não está respondendo em $REDIS_HOST:$REDIS_PORT"
    exit 1
fi

# Localizar unbound-control
UNBOUND_CTRL=""
for bin in /usr/sbin/unbound-control /usr/bin/unbound-control /opt/unbound/sbin/unbound-control; do
    if [ -x "$bin" ]; then
        UNBOUND_CTRL="$bin"
        break
    fi
done

if [ -z "$UNBOUND_CTRL" ]; then
    log "ERRO: unbound-control não encontrado"
    redis_cmd HSET "unbound:stats:latest" "unbound_status" "down" "timestamp" "$(date +%s)" > /dev/null
    exit 1
fi

# Coletar estatísticas
STATS_OUTPUT=$($UNBOUND_CTRL stats 2>/dev/null)
STATUS_OUTPUT=$($UNBOUND_CTRL status 2>/dev/null)

if [ -z "$STATS_OUTPUT" ]; then
    log "ERRO: unbound-control stats retornou vazio"
    redis_cmd HSET "unbound:stats:latest" "unbound_status" "down" "timestamp" "$(date +%s)" > /dev/null
    exit 1
fi

# Extrair métricas
total_queries=$(echo "$STATS_OUTPUT" | grep "^total.num.queries="     | cut -d= -f2 | tr -d '[:space:]')
cache_hits=$(echo "$STATS_OUTPUT"    | grep "^total.num.cachehits="   | cut -d= -f2 | tr -d '[:space:]')
cache_miss=$(echo "$STATS_OUTPUT"    | grep "^total.num.cachemiss="   | cut -d= -f2 | tr -d '[:space:]')
rpz_hits=$(echo "$STATS_OUTPUT"      | grep "^total.num.rpz.action.nxdomain=" | cut -d= -f2 | tr -d '[:space:]')
ipv4_queries=$(echo "$STATS_OUTPUT"  | grep "^num.query.type.A="      | cut -d= -f2 | tr -d '[:space:]')
ipv6_queries=$(echo "$STATS_OUTPUT"  | grep "^num.query.type.AAAA="   | cut -d= -f2 | tr -d '[:space:]')

# Valores padrão
total_queries=${total_queries:-0}
cache_hits=${cache_hits:-0}
cache_miss=${cache_miss:-0}
rpz_hits=${rpz_hits:-0}
ipv4_queries=${ipv4_queries:-0}
ipv6_queries=${ipv6_queries:-0}

# Calcular percentuais
if [ "$total_queries" -gt 0 ] 2>/dev/null; then
    hit_ratio=$(awk "BEGIN {printf \"%.2f\", ($cache_hits/$total_queries)*100}")
    ipv4_hit_pct=$(awk "BEGIN {printf \"%.1f\", ($ipv4_queries/$total_queries)*100}")
    ipv6_hit_pct=$(awk "BEGIN {printf \"%.1f\", ($ipv6_queries/$total_queries)*100}")
else
    hit_ratio="0.00"
    ipv4_hit_pct="0.0"
    ipv6_hit_pct="0.0"
fi

# Uptime
uptime_str=$(echo "$STATUS_OUTPUT" | grep "uptime:" | sed 's/.*uptime: //' | tr -d '[:space:]')
uptime_str=${uptime_str:-"desconhecido"}

# Salvar no Redis
redis_cmd HSET "unbound:stats:latest" \
    "total_queries"  "$total_queries" \
    "cache_hits"     "$cache_hits" \
    "cache_miss"     "$cache_miss" \
    "hit_ratio"      "$hit_ratio" \
    "ipv4_queries"   "$ipv4_queries" \
    "ipv6_queries"   "$ipv6_queries" \
    "ipv4_hit_pct"   "$ipv4_hit_pct" \
    "ipv6_hit_pct"   "$ipv6_hit_pct" \
    "rpz_hits"       "$rpz_hits" \
    "uptime"         "$uptime_str" \
    "unbound_status" "up" \
    "timestamp"      "$(date +%s)" > /dev/null

# Série temporal (24h)
time_key=$(date +%s)
cutoff=$(( time_key - 86400 ))

redis_cmd ZADD "unbound:stats:history:queries"   "$time_key" "$total_queries" > /dev/null
redis_cmd ZADD "unbound:stats:history:hit_ratio" "$time_key" "$hit_ratio"     > /dev/null
redis_cmd ZADD "unbound:stats:history:ipv4"      "$time_key" "$ipv4_queries"  > /dev/null
redis_cmd ZADD "unbound:stats:history:ipv6"      "$time_key" "$ipv6_queries"  > /dev/null

redis_cmd ZREMRANGEBYSCORE "unbound:stats:history:queries"   0 "$cutoff" > /dev/null
redis_cmd ZREMRANGEBYSCORE "unbound:stats:history:hit_ratio" 0 "$cutoff" > /dev/null
redis_cmd ZREMRANGEBYSCORE "unbound:stats:history:ipv4"      0 "$cutoff" > /dev/null
redis_cmd ZREMRANGEBYSCORE "unbound:stats:history:ipv6"      0 "$cutoff" > /dev/null

log "OK: queries=$total_queries hits=$cache_hits miss=$cache_miss ipv4=$ipv4_queries ipv6=$ipv6_queries rpz=$rpz_hits uptime=$uptime_str"
exit 0
