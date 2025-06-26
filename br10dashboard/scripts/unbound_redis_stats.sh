#!/bin/bash
# Script to update Unbound statistics in Redis
# BR10 DNS - Integration Script

LOG_FILE="/var/log/br10_unbound_redis.log"

log() {
  echo "$(date +"%Y-%m-%d %H:%M:%S") - $1" >> "$LOG_FILE"
}

log "Starting Unbound statistics collection for Redis"

# Function to check if Redis is running
check_redis() {
  if ! redis-cli PING &>/dev/null; then
    log "ERROR: Redis is not responding"
    return 1
  fi
  return 0
}

# Function to collect Unbound statistics
collect_unbound_stats() {
  if ! command -v unbound-control &>/dev/null; then
    log "ERROR: unbound-control not found"
    return 1
  fi
  
  # Collect general statistics
  stats_output=$(unbound-control stats)
  if [ -z "$stats_output" ]; then
    log "ERROR: Could not get Unbound statistics"
    return 1
  fi
  
  # Extract main metrics
  total_queries=$(echo "$stats_output" | grep "total.num.queries=" | cut -d= -f2)
  cache_hits=$(echo "$stats_output" | grep "total.num.cachehits=" | cut -d= -f2)
  cache_miss=$(echo "$stats_output" | grep "total.num.cachemiss=" | cut -d= -f2)
  
  # Calculate hit ratio
  if [ "$total_queries" -gt 0 ]; then
    hit_ratio=$(awk "BEGIN {print ($cache_hits/$total_queries)*100}")
  else
    hit_ratio=0
  fi
  
  # Collect thread statistics
  thread_stats=$(echo "$stats_output" | grep "thread")
  
  # Collect query type statistics
  query_types=$(echo "$stats_output" | grep "num.query.type")
  
  # Save to Redis
  redis-cli HSET "unbound:stats:latest" "total_queries" "$total_queries" \
                                       "cache_hits" "$cache_hits" \
                                       "cache_miss" "$cache_miss" \
                                       "hit_ratio" "$hit_ratio" \
                                       "timestamp" "$(date +%s)"
  
  # Save time series (keep 24-hour history)
  time_key=$(date +%s)
  redis-cli ZADD "unbound:stats:history:queries" "$time_key" "$total_queries"
  redis-cli ZADD "unbound:stats:history:hit_ratio" "$time_key" "$hit_ratio"
  
  # Clean old data (more than 24 hours)
  cutoff=$(( $(date +%s) - 86400 ))
  redis-cli ZREMRANGEBYSCORE "unbound:stats:history:queries" 0 "$cutoff"
  redis-cli ZREMRANGEBYSCORE "unbound:stats:history:hit_ratio" 0 "$cutoff"
  
  log "Unbound statistics updated successfully in Redis"
  return 0
}

# Function to collect client statistics
collect_client_stats() {
  # Analyze Unbound logs to detect clients
  log_file="/var/log/unbound/unbound.log"
  
  if [ ! -f "$log_file" ]; then
    # Try common alternative
    log_file="/var/log/syslog"
    
    if [ ! -f "$log_file" ]; then
      log "WARNING: Could not find Unbound logs"
      return 1
    fi
  fi
  
  # Extract unique client IPs from the last lines of the log
  client_ips=$(grep -a "query:" "$log_file" | tail -1000 | awk '{print $5}' | sort | uniq)
  
  # Clear current set
  redis-cli DEL "unbound:clients:active" >/dev/null
  
  # Add to set
  for ip in $client_ips; do
    # Remove port (if present)
    ip_clean=$(echo "$ip" | cut -d '@' -f 1)
    
    # Add to set in Redis
    redis-cli SADD "unbound:clients:active" "$ip_clean" >/dev/null
    
    # Increment query count per client
    redis-cli HINCRBY "unbound:clients:queries" "$ip_clean" 1 >/dev/null
  done
  
  # Set expiration for counts (12 hours)
  redis-cli EXPIRE "unbound:clients:queries" 43200 >/dev/null
  
  log "Client statistics updated successfully in Redis"
  return 0
}

# Check if Redis is available
if ! check_redis; then
  log "Redis not available. Exiting."
  exit 1
fi

# Collect statistics
collect_unbound_stats
collect_client_stats

log "Statistics collection completed"
exit 0
