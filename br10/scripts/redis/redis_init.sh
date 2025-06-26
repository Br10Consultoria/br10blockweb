#!/bin/bash
# Redis initialization script for BR10

LOG_FILE="/var/log/br10redis_init.log"

log() {
  echo "$(date +"%Y-%m-%d %H:%M:%S") - $1" >> "$LOG_FILE"
}

log "Starting Redis initialization script"

# Ensure the service is active
if ! systemctl is-active --quiet redis-server; then
  log "Redis is not active. Starting service..."
  systemctl start redis-server
fi

# Check data integrity
log "Checking data integrity..."
if redis-cli PING | grep -q "PONG"; then
  log "Redis responding normally"
else
  log "Problem connecting to Redis. Restarting service..."
  systemctl restart redis-server
  sleep 5
  
  if redis-cli PING | grep -q "PONG"; then
    log "Redis restored successfully"
  else
    log "ERROR: Failed to restore Redis"
  fi
fi

# Log memory statistics
mem_info=$(redis-cli INFO memory)
log "Memory statistics: $(echo "$mem_info" | grep used_memory_human)"

log "Redis initialization script completed"
exit 0
