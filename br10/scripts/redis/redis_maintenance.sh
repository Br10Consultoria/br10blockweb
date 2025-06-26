#!/bin/bash
# Redis maintenance script for BR10
# Performs periodic cleanup and compaction of Redis

LOG_FILE="/var/log/br10redis_maintenance.log"

log() {
  echo "$(date +"%Y-%m-%d %H:%M:%S") - $1" >> "$LOG_FILE"
}

log "Starting Redis maintenance"

# Check if Redis is running
if ! systemctl is-active --quiet redis-server; then
  log "Redis is not running. Trying to start..."
  systemctl start redis-server
  sleep 5
fi

# Connect to Redis and execute BGSAVE
log "Executing BGSAVE..."
redis-cli BGSAVE
sleep 5

# Check memory usage
memory_usage=$(redis-cli INFO memory | grep "used_memory_human:" | cut -d ":" -f2 | tr -d '[:space:]')
log "Current memory usage: $memory_usage"

# Clear expired keys (non-blocking)
log "Running asynchronous cleanup of expired keys..."
redis-cli --raw SCAN 0 COUNT 1000 | while read -r cursor; do
  if [ "$cursor" != "0" ]; then
    redis-cli --raw SCAN $cursor COUNT 1000 | grep -v "^[0-9]*$" | xargs -r redis-cli TTL | awk '{if($1<0) print $1}' | wc -l | xargs -I{} echo "Checked {} keys"
  fi
  [ "$cursor" = "0" ] && break
done

log "Redis maintenance completed successfully"
exit 0
