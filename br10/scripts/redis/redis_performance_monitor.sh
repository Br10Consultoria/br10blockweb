#!/bin/bash
# Script de monitoramento de desempenho do Redis
# Salva métricas de desempenho periodicamente para análise

LOG_FILE="/var/log/redis_performance.log"
LOG_DIR=$(dirname "$LOG_FILE")

# Criar diretório para logs se não existir
if [ ! -d "$LOG_DIR" ]; then
  mkdir -p "$LOG_DIR"
fi

# Adicionar separador para entrada de log
echo "===================================================" >> $LOG_FILE
echo "Date: $(date)" >> $LOG_FILE

# Coletar estatísticas do Redis
echo "----- Redis Stats -----" >> $LOG_FILE
redis-cli INFO stats | grep -E 'total_commands|keyspace_hits|keyspace_misses' >> $LOG_FILE

# Coletar uso de memória
echo "----- Memory Usage -----" >> $LOG_FILE
redis-cli INFO memory | grep -E 'used_memory_human|used_memory_peak_human|maxmemory_human' >> $LOG_FILE

# Coletar estatísticas do Unbound (se estiver instalado)
if command -v unbound-control &> /dev/null; then
  echo "----- Unbound Performance -----" >> $LOG_FILE
  unbound-control stats | grep -E 'total.num.queries|total.num.cachehits|total.num.cachemiss' >> $LOG_FILE
  
  # Calcular taxa de acerto do cache
  total_queries=$(unbound-control stats | grep "total.num.queries=" | cut -d= -f2)
  cache_hits=$(unbound-control stats | grep "total.num.cachehits=" | cut -d= -f2)
  
  if [ -n "$total_queries" ] && [ -n "$cache_hits" ] && [ "$total_queries" -gt 0 ]; then
    hit_ratio=$(awk "BEGIN {printf \"%.2f\", ($cache_hits/$total_queries)*100}")
    echo "Unbound Cache Hit Ratio: ${hit_ratio}%" >> $LOG_FILE
  fi
fi

# Coletar estatísticas de recursos do sistema
echo "----- System Resources -----" >> $LOG_FILE
free -m | head -n 2 >> $LOG_FILE

# Coletar informações de CPU para o processo Redis
echo "----- Redis CPU Usage -----" >> $LOG_FILE
top -b -n 1 -p $(pgrep redis-server) | tail -n 2 >> $LOG_FILE

# Testar latência básica do Redis
echo "----- Redis Latency -----" >> $LOG_FILE
redis-cli --raw ping | xargs -I{} echo "PING Response: {}" >> $LOG_FILE

# Testar latência média de 10 operações SET/GET
echo "Testing SET/GET Latency (average of 10 operations):" >> $LOG_FILE
total_time=0
for i in {1..10}; do
  start_time=$(date +%s%N)
  redis-cli SET test:latency:$i value:$i > /dev/null
  redis-cli GET test:latency:$i > /dev/null
  end_time=$(date +%s%N)
  operation_time=$(( ($end_time - $start_time) / 1000000 ))
  total_time=$(( $total_time + $operation_time ))
done
average_time=$(( $total_time / 10 ))
echo "Average SET/GET latency: ${average_time}ms" >> $LOG_FILE

echo "" >> $LOG_FILE
