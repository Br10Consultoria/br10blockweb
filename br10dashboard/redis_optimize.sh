#!/bin/bash
# BR10 Redis Optimization Script
# Version: 2.0 - 09/04/2025
# Description: Script to install and optimize Redis for BR10 DNS system with clean configuration

# Define colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Initial banner
display_banner() {
    echo -e "${BLUE}"
    echo "  ____  ____  _ ___   ____           _ _"
    echo " |  _ \|  _ \/ |__ \ |  _ \ ___  ___| (_)___"
    echo " | |_) | |_) | |  ) || |_) / _ \/ __| | / __|"
    echo " |  _ <|  _ <| | / / |  _ <  __/ (__| | \__ \\"
    echo " |_| \_\_| \_\_|/___||_| \_\___|\___|_|_|___/"
    echo ""
    echo " Optimization and Configuration for High Performance"
    echo -e "${NC}"
}

# Global variables
REDIS_CONFIG="/etc/redis/redis.conf"
REDIS_SERVICE="redis-server"
LOG_FILE="/var/log/br10redis_install.log"
BACKUP_DIR="/opt/br10/backups/redis"
SCRIPTS_DIR="/opt/br10/scripts/redis"

# Log functions
log() {
    echo "$(date +"%Y-%m-%d %H:%M:%S") - INFO: $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo "$(date +"%Y-%m-%d %H:%M:%S") - SUCCESS: $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo "$(date +"%Y-%m-%d %H:%M:%S") - ERROR: $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo "$(date +"%Y-%m-%d %H:%M:%S") - WARNING: $1" | tee -a "$LOG_FILE"
}

# Function to check root permissions
check_root() {
    if [ "$(id -u)" != "0" ]; then
        echo -e "${RED}This script must be run as root.${NC}"
        exit 1
    fi
}

# Function to create necessary directories
create_directories() {
    log "Creating necessary directories..."
    
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$SCRIPTS_DIR"
    mkdir -p "/var/lib/redis/backup"
    
    chmod 755 "$BACKUP_DIR"
    chmod 755 "$SCRIPTS_DIR"
    
    log_success "Directories created successfully"
}

# Function to detect system resources
detect_system_resources() {
    log "Detecting system resources for automatic optimization"
    echo -e "${BLUE}Detecting system resources for optimization...${NC}"
    
    # Detect number of CPUs
    NUM_CPUS=$(nproc)
    
    # Detect total memory in MB
    TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    TOTAL_MEM=$((TOTAL_MEM_KB / 1024))
    
    # Detect available disk space
    ROOT_DISK_SPACE=$(df -m / | awk 'NR==2 {print $4}')
    
    # Show results
    echo -e "${GREEN}Detected resources:${NC}"
    echo -e " - ${BLUE}CPUs:${NC} $NUM_CPUS"
    echo -e " - ${BLUE}Memory:${NC} $TOTAL_MEM MB"
    echo -e " - ${BLUE}Disk space:${NC} $ROOT_DISK_SPACE MB"
    
    # Calculate optimal Redis settings
    calculate_redis_settings
}

# Function to calculate optimized Redis settings
calculate_redis_settings() {
    log "Calculating optimal settings for Redis"
    
    # Calculate maximum memory size (adjusted for DNS cache)
    if [ "$TOTAL_MEM" -gt 4096 ]; then
        # For servers with more than 4GB of RAM
        REDIS_MEMORY=512
    elif [ "$TOTAL_MEM" -gt 2048 ]; then
        # For servers with 2-4GB of RAM
        REDIS_MEMORY=256
    else
        # For smaller servers
        REDIS_MEMORY=$((TOTAL_MEM / 8))
    fi
    
    # Ensure a reasonable minimum
    if [ "$REDIS_MEMORY" -lt 64 ]; then
        REDIS_MEMORY=64
    fi
    
    # Maximum number of connections (optimized for dashboard)
    if [ "$NUM_CPUS" -gt 4 ]; then
        MAX_CLIENTS=2000
    elif [ "$NUM_CPUS" -gt 2 ]; then
        MAX_CLIENTS=1000
    else
        MAX_CLIENTS=500
    fi
    
    # For DNS cache, fewer databases are needed
    DATABASES=2
    
    # Persistence time - adjusted for DNS cache
    # Fewer disk saves = better performance
    SAVE_SETTINGS="save 900 1\nsave 300 10\nsave 60 10000"
    
    # Disable AOF for better cache performance
    USE_AOF="no"
    
    # Eviction policy for cache (always LRU)
    EVICTION_POLICY="allkeys-lru"
    
    # Optimized timeout and keepalive values
    TCP_KEEPALIVE=60
    TIMEOUT=300
    
    # Configure data compression
    RDB_COMPRESSION="yes"
    
    # Calculate optimal I/O threads based on CPU count
    if [ "$NUM_CPUS" -gt 8 ]; then
        IO_THREADS=4
    elif [ "$NUM_CPUS" -gt 4 ]; then
        IO_THREADS=2
    else
        IO_THREADS=1
    fi
    
    log "Settings calculated successfully"
    
    # Display settings
    echo -e "\n${GREEN}Optimized settings for DNS cache:${NC}"
    echo -e " - ${BLUE}Maximum memory:${NC} ${REDIS_MEMORY}MB"
    echo -e " - ${BLUE}Maximum clients:${NC} $MAX_CLIENTS"
    echo -e " - ${BLUE}Databases:${NC} $DATABASES"
    echo -e " - ${BLUE}AOF persistence:${NC} $USE_AOF"
    echo -e " - ${BLUE}Eviction policy:${NC} $EVICTION_POLICY"
    echo -e " - ${BLUE}TCP Keepalive:${NC} $TCP_KEEPALIVE seconds"
    echo -e " - ${BLUE}I/O Threads:${NC} $IO_THREADS"
}

# Function to install Redis
install_redis() {
    log "Starting Redis installation..."
    echo -e "${BLUE}Starting Redis installation...${NC}"
    
    # Check if Redis is already installed
    if command -v redis-server &>/dev/null; then
        log "Redis is already installed. Checking version..."
        REDIS_VERSION=$(redis-server --version | cut -d " " -f 3 | cut -d "=" -f 2)
        echo -e "${YELLOW}Redis version $REDIS_VERSION is already installed.${NC}"
        
        # Get the latest version from repository
        apt-get update -qq
        LATEST_VERSION=$(apt-cache show redis-server | grep Version | head -1 | awk '{print $2}' | cut -d ":" -f 2)
        
        # Compare versions (simple string comparison)
        if [[ "$REDIS_VERSION" == "$LATEST_VERSION" ]]; then
            log "Redis is already at the latest version. Skipping reinstallation."
            echo -e "${GREEN}Redis is already at the latest version. Skipping reinstallation.${NC}"
            return 0
        else
            # Ask if we should reinstall
            echo -e "${YELLOW}A newer version ($LATEST_VERSION) may be available.${NC}"
            read -p "Do you want to reinstall or update Redis? (y/N): " reinstall
            if [[ "$reinstall" != "y" && "$reinstall" != "Y" ]]; then
                log "Reinstallation canceled by user."
                echo -e "${YELLOW}Reinstallation canceled. Continuing with configuration...${NC}"
                return 0
            fi
        fi
    fi
    
    # Update repositories
    log "Updating repositories..."
    echo -e "${YELLOW}Updating repositories...${NC}"
    apt-get update -qq
    
    # Install Redis with recommended dependencies
    log "Installing Redis..."
    echo -e "${YELLOW}Installing Redis and dependencies...${NC}"
    apt_output=$(DEBIAN_FRONTEND=noninteractive apt-get install -y redis-server redis-tools 2>&1)
    log "APT output: $apt_output"
    echo -e "${YELLOW}$apt_output${NC}"
    
    # Check if installation was successful
    if ! command -v redis-server &>/dev/null; then
        log_error "Failed to install Redis"
        echo -e "${RED}Failed to install Redis. Check the log for details.${NC}"
        return 1
    fi
    
    # Get installed version
    REDIS_VERSION=$(redis-server --version | cut -d " " -f 3 | cut -d "=" -f 2)
    log_success "Redis version $REDIS_VERSION installed successfully"
    echo -e "${GREEN}Redis version $REDIS_VERSION installed successfully!${NC}"
    
    return 0
}

# Function to create a new Redis configuration
create_redis_config() {
    log "Creating new optimized Redis configuration for DNS cache..."
    echo -e "${BLUE}Creating new optimized Redis configuration for DNS cache...${NC}"
    
    # Create backup of the original configuration if it exists
    if [ -f "$REDIS_CONFIG" ]; then
        BACKUP_FILE="$BACKUP_DIR/redis.conf.bak.$(date +%Y%m%d%H%M%S)"
        log "Creating backup of original configuration in $BACKUP_FILE"
        mkdir -p "$BACKUP_DIR"
        cp "$REDIS_CONFIG" "$BACKUP_FILE"
    fi
    
    # Determine Redis directories
    REDIS_DATA_DIR=$(dirname $(redis-cli CONFIG GET dir | awk 'NR==2 {print $1}' 2>/dev/null) || echo "/var/lib/redis")
    REDIS_LOG_DIR=$(dirname $(redis-cli CONFIG GET logfile | awk 'NR==2 {print $1}' 2>/dev/null) || echo "/var/log/redis")
    REDIS_PID_DIR=$(dirname $(redis-cli CONFIG GET pidfile | awk 'NR==2 {print $1}' 2>/dev/null) || echo "/var/run/redis")
    
    # Ensure directories exist
    mkdir -p "$REDIS_DATA_DIR" "$REDIS_LOG_DIR" "$REDIS_PID_DIR"
    chown redis:redis "$REDIS_DATA_DIR" "$REDIS_LOG_DIR" "$REDIS_PID_DIR"
    
    log "Creating new configuration file from scratch..."
    echo -e "${YELLOW}Creating new configuration file from scratch...${NC}"
    
    # Create a new configuration file
    cat > "$REDIS_CONFIG" << EOL
# Redis configuration file for BR10 DNS
# Generated by BR10 Redis Optimization Script v2.0
# Date: $(date)

################################## NETWORK #####################################

# Listen on localhost only
bind 127.0.0.1 ::1

# Port to listen on
port 6379

# TCP keepalive
tcp-keepalive ${TCP_KEEPALIVE}

# Connection timeout in seconds
timeout ${TIMEOUT}

# Close connection after a client is idle for N seconds
timeout ${TIMEOUT}

# TCP backlog settings
tcp-backlog 511

# TLS/SSL is disabled for this configuration
tls-port 0

################################# GENERAL #####################################

# Run as daemon
daemonize yes

# Set the number of databases
databases ${DATABASES}

# Set process title
set-proc-title yes
proc-title-template "{title} {listen-addr} {server-mode}"

# PID file
pidfile /var/run/redis/redis-server.pid

# Log level (notice, warning, verbose, debug)
loglevel notice

# Log file
logfile /var/log/redis/redis-server.log

# Supervised by systemd
supervised systemd

################################ SNAPSHOTTING ################################

# Save the DB to disk
save 900 1
save 300 10
save 60 10000

# Stop accepting writes if RDB snapshots can't be persisted
stop-writes-on-bgsave-error yes

# Compress string objects using LZF
rdbcompression ${RDB_COMPRESSION}

# Checksum for RDB files
rdbchecksum yes

# RDB filename
dbfilename dump.rdb

# Remove RDB files used by replication
rdb-del-sync-files no

# Working directory
dir ${REDIS_DATA_DIR}

################################## SECURITY ###################################

# Client output buffer limits
client-output-buffer-limit normal 0 0 0
client-output-buffer-limit replica 256mb 64mb 60
client-output-buffer-limit pubsub 32mb 8mb 60

# Maximum number of clients
maxclients ${MAX_CLIENTS}

################################### LIMITS ####################################

# Max memory policy
maxmemory ${REDIS_MEMORY}mb
maxmemory-policy ${EVICTION_POLICY}
maxmemory-samples 5

################################### APPEND ONLY MODE ##########################

# Append only mode (disabled for DNS cache performance)
appendonly ${USE_AOF}

################################ THREADED I/O #################################

# Threading can improve performance with multiple cores
io-threads ${IO_THREADS}
io-threads-do-reads no

################################## ADVANCED CONFIG ############################

# Rehashing uses 1 millisecond every 100 milliseconds
activerehashing yes

# Favor latency or throughput or both
dynamic-hz yes
hz 10

# Enable fast memory reclamation
lazyfree-lazy-eviction yes
lazyfree-lazy-expire yes
lazyfree-lazy-server-del yes
replica-lazy-flush no

# Disable Redis persistence to disk for better performance (optional)
# save ""

# Reducing memory usage
activedefrag no
jemalloc-bg-thread yes

################################## BR10 CUSTOM ###############################

# Specific BR10 DNS Cache optimizations
# Allow writes with replicas attached
slave-serve-stale-data yes

# Low latency for DNS cache
latency-monitor-threshold 100

# Set client query buffer limit
client-query-buffer-limit 1mb

# Prevent the server from advertising capabilities that we don't need
cluster-enabled no
cluster-announce-bus-port 0

# Disable protected mode if Redis is not exposed externally
protected-mode yes

# Configuration for handling script cache
lua-time-limit 5000

# Enable LFU with decay time in minutes
lfu-log-factor 10
lfu-decay-time 1

EOL

    # Set proper permissions
    chown redis:redis "$REDIS_CONFIG"
    chmod 640 "$REDIS_CONFIG"
    
    log_success "New Redis configuration created successfully"
    echo -e "${GREEN}New Redis configuration created successfully!${NC}"
    
    # Verify the configuration
    log "Verifying new configuration..."
    echo -e "${YELLOW}Verifying new configuration...${NC}"
    
    echo -e "${YELLOW}Testing configuration syntax...${NC}"
    verify_output=$(redis-server -t "$REDIS_CONFIG" 2>&1)
    verify_status=$?

    if [ $verify_status -eq 0 ]; then
        log_success "Configuration syntax verified successfully"
        echo -e "${GREEN}Configuration syntax verified successfully!${NC}"
    else
        log_error "Error in Redis configuration syntax: $verify_output"
        echo -e "${RED}Error in Redis configuration syntax. Check the logs for details.${NC}"
        echo -e "${YELLOW}Error details: $verify_output${NC}"
    
        if [ -f "$BACKUP_FILE" ]; then
            log_warning "Restoring backup configuration..."
            echo -e "${YELLOW}Restoring backup configuration...${NC}"
            cp "$BACKUP_FILE" "$REDIS_CONFIG"
        fi
        return 1
    fi
}

# Function to create maintenance scripts
create_maintenance_scripts() {
    log "Creating Redis maintenance scripts..."
    echo -e "${BLUE}Creating Redis maintenance scripts...${NC}"
    
    mkdir -p "$SCRIPTS_DIR"
    
    # Create maintenance script
    cat > "$SCRIPTS_DIR/redis_maintenance.sh" << 'EOL'
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
EOL

    chmod +x "$SCRIPTS_DIR/redis_maintenance.sh"
    
    # Create initialization script
    cat > "$SCRIPTS_DIR/redis_init.sh" << 'EOL'
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
EOL

    chmod +x "$SCRIPTS_DIR/redis_init.sh"
    
    # Configure cron for periodic maintenance
    cron_file="/etc/cron.d/br10redis"
    echo "# BR10 Redis Maintenance Tasks" > "$cron_file"
    echo "0 3 * * * root $SCRIPTS_DIR/redis_maintenance.sh > /dev/null 2>&1" >> "$cron_file"
    echo "@reboot root $SCRIPTS_DIR/redis_init.sh > /dev/null 2>&1" >> "$cron_file"
    
    chmod 644 "$cron_file"
    
    log_success "Maintenance scripts created successfully"
    echo -e "${GREEN}Maintenance scripts created successfully!${NC}"
    
    return 0
}

# Integrate Redis with Unbound service
integrate_with_unbound() {
    log "Starting integration with Unbound..."
    echo -e "${BLUE}Starting integration with Unbound...${NC}"
    
    # Check if Unbound is installed
    if ! command -v unbound &>/dev/null; then
        log_warning "Unbound not found. Skipping integration."
        echo -e "${YELLOW}Unbound not found. Skipping integration.${NC}"
        return 0
    fi
    
    # Check if the dashboard scripts exist
    DASHBOARD_DIR="/opt/br10dashboard"
    if [ ! -d "$DASHBOARD_DIR" ]; then
        log_warning "Dashboard not found. Creating directory for scripts..."
        mkdir -p "$DASHBOARD_DIR/scripts"
    fi
    
    # Create script to feed Redis with Unbound data
    UNBOUND_SCRIPT="$DASHBOARD_DIR/scripts/unbound_redis_stats.sh"
    
    log "Creating Unbound-Redis integration script..."
    
    cat > "$UNBOUND_SCRIPT" << 'EOL'
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
EOL

    chmod +x "$UNBOUND_SCRIPT"
    
    # Configure cron for periodic collection
    CRON_FILE="/etc/cron.d/br10unbound_redis"
    
    echo "# BR10 Unbound-Redis Integration" > "$CRON_FILE"
    echo "*/5 * * * * root $UNBOUND_SCRIPT > /dev/null 2>&1" >> "$CRON_FILE"
    
    chmod 644 "$CRON_FILE"
    
    log_success "Unbound integration configured successfully"
    echo -e "${GREEN}Unbound integration configured successfully!${NC}"
    
    return 0
}

# Function to integrate Redis with blocking API
integrate_with_api() {
    log "Starting integration with blocking API..."
    echo -e "${BLUE}Starting integration with blocking API...${NC}"
    
    # Check if the API is installed
    API_DIR="/opt/br10api"
    if [ ! -d "$API_DIR" ]; then
        log_warning "Blocking API not found. Skipping integration."
        echo -e "${YELLOW}Blocking API not found. Skipping integration.${NC}"
        return 0
    fi
    
    # Create script for API integration
    API_SCRIPT="$API_DIR/scripts/api_redis_cache.py"
    
    # Create directory if it doesn't exist
    mkdir -p "$API_DIR/scripts"
    mkdir -p "$API_DIR/logs"
    
    log "Creating API-Redis integration script..."
    
    cat > "$API_SCRIPT" << 'EOL'
#!/usr/bin/env python3
# Script for integrating the blocking API with Redis
# BR10 DNS - Redis Integration

import redis
import json
import os
import time
import hashlib
import logging
from datetime import datetime, timedelta

# Configure logging
log_dir = '/opt/br10api/logs'
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'redis_integration.log')

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Redis configuration
redis_client = redis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)

# Constants
DOMAINS_FILE = "/var/lib/br10api/blocked_domains.txt"
CACHE_TTL = 3600  # 1 hour
CACHE_PREFIX = "br10:blocklist:"

def log(message, level='info'):
    """Function to log messages"""
    if level == 'info':
        logging.info(message)
    elif level == 'error':
        logging.error(message)
    elif level == 'warning':
        logging.warning(message)

def calculate_checksum(data):
    """Calculate MD5 checksum of a string or list"""
    if isinstance(data, list):
        data = "\n".join(data)
    return hashlib.md5(data.encode()).hexdigest()

def cache_domains_list():
    """Store the domain list in Redis cache"""
    try:
        if not os.path.exists(DOMAINS_FILE):
            log(f"Domain file not found: {DOMAINS_FILE}", "warning")
            return False
            
        # Read the domain list
        with open(DOMAINS_FILE, 'r') as f:
            domains = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            
        if not domains:
            log("Empty domain list", "warning")
            return False
            
        # Calculate checksum
        checksum = calculate_checksum(domains)
        
        # Check if the checksum changed
        current_checksum = redis_client.get(f"{CACHE_PREFIX}checksum")
        if current_checksum == checksum:
            # Only update TTL if content hasn't changed
            redis_client.expire(f"{CACHE_PREFIX}domains", CACHE_TTL)
            redis_client.expire(f"{CACHE_PREFIX}checksum", CACHE_TTL)
            log(f"Domain list hasn't changed (checksum: {checksum}). TTL updated.")
            return True
            
        # Store the complete list
        pipeline = redis_client.pipeline()
        
        # Store as a set for fast lookup
        pipeline.delete(f"{CACHE_PREFIX}set")
        for domain in domains:
            pipeline.sadd(f"{CACHE_PREFIX}set", domain)
            
        # Store as string for complete retrieval
        pipeline.set(f"{CACHE_PREFIX}domains", json.dumps(domains))
        pipeline.set(f"{CACHE_PREFIX}checksum", checksum)
        
        # Set expiration time
        pipeline.expire(f"{CACHE_PREFIX}set", CACHE_TTL)
        pipeline.expire(f"{CACHE_PREFIX}domains", CACHE_TTL)
        pipeline.expire(f"{CACHE_PREFIX}checksum", CACHE_TTL)
        
        # Store metadata
        pipeline.hset(f"{CACHE_PREFIX}meta", mapping={
            "count": len(domains),
            "updated_at": datetime.now().isoformat(),
            "source": DOMAINS_FILE
        })
        pipeline.expire(f"{CACHE_PREFIX}meta", CACHE_TTL)
        
        # Execute all operations
        pipeline.execute()
        
        log(f"Domain list in cache updated successfully. Total: {len(domains)} domains.")
        return True
        
    except Exception as e:
        log(f"Error storing domain list in cache: {str(e)}", "error")
        return False

def cache_historical_data():
    """Store historical data for statistics"""
    try:
        history_dir = "/opt/br10dashboard/data/history"
        if not os.path.exists(history_dir):
            log(f"History directory not found: {history_dir}", "warning")
            return False
            
        # Get most recent history files
        history_files = []
        for filename in os.listdir(history_dir):
            if filename.startswith("blocklist_") and filename.endswith(".json"):
                file_path = os.path.join(history_dir, filename)
                file_time = os.path.getmtime(file_path)
                history_files.append((file_path, file_time))
                
        # Sort by time (most recent first)
        history_files.sort(key=lambda x: x[1], reverse=True)
        
        # Limit to 10 most recent
        recent_files = history_files[:10]
        
        # Store data in Redis
        pipeline = redis_client.pipeline()
        
        # Clear current list
        pipeline.delete(f"{CACHE_PREFIX}history")
        
        for file_path, _ in recent_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    # Convert to JSON string
                    pipeline.rpush(f"{CACHE_PREFIX}history", json.dumps(data))
            except Exception as e:
                log(f"Error processing history file {file_path}: {str(e)}", "error")
                
        # Set expiration
        pipeline.expire(f"{CACHE_PREFIX}history", CACHE_TTL * 24)  # 24 hours
        
        # Execute operations
        pipeline.execute()
        
        log(f"Historical data in cache updated. Total: {len(recent_files)} records.")
        return True
        
    except Exception as e:
        log(f"Error storing historical data in cache: {str(e)}", "error")
        return False

def check_redis_connection():
    """Check if Redis is available"""
    try:
        return redis_client.ping()
    except Exception as e:
        log(f"Error connecting to Redis: {str(e)}", "error")
        return False

def main():
    """Main function"""
    log("Starting API-Redis integration script")
    
    if not check_redis_connection():
        log("Redis is not available. Exiting.", "error")
        return
        
    # Store domain list in cache
    cache_domains_list()
    
    # Store historical data
    cache_historical_data()
    
    log("API-Redis integration script completed successfully")

if __name__ == "__main__":
    main()
	
	chmod +x "$API_SCRIPT"
    
    # Configure cron for periodic execution
    CRON_FILE="/etc/cron.d/br10api_redis"
    
    echo "# BR10 API-Redis Integration" > "$CRON_FILE"
    echo "*/15 * * * * root $API_SCRIPT > /dev/null 2>&1" >> "$CRON_FILE"
    
    chmod 644 "$CRON_FILE"
    
    # Create script for API cache maintenance and cleanup
    MAINT_SCRIPT="$API_DIR/scripts/redis_api_maintenance.sh"
    
    cat > "$MAINT_SCRIPT" << 'EOL'
#!/bin/bash
# Redis cache maintenance script for BR10 API
# Performs cleanup and optimization of blocked domains cache

LOG_FILE="/opt/br10api/logs/redis_maintenance.log"

log() {
  echo "$(date +"%Y-%m-%d %H:%M:%S") - $1" >> "$LOG_FILE"
}

log "Starting Redis cache maintenance for API"

# Check if Redis is available
if ! redis-cli PING &>/dev/null; then
  log "ERROR: Redis is not responding"
  exit 1
fi

# Clean expired cache keys
expired_keys=$(redis-cli --raw keys "br10:blocklist:*" | xargs -r redis-cli TTL | awk '{if($1<0) print $1}' | wc -l)
log "Found $expired_keys expired keys for cleanup"

# Check cache integrity
domains_file="/var/lib/br10api/blocked_domains.txt"
if [ -f "$domains_file" ]; then
  # Check if the file exists and calculate number of domains
  domains_count=$(grep -v "^#" "$domains_file" | grep -v "^$" | wc -l)
  
  # Compare with Redis cache
  cache_count=$(redis-cli HGET "br10:blocklist:meta" "count")
  
  if [ -n "$cache_count" ] && [ "$domains_count" -ne "$cache_count" ]; then
    log "Inconsistency detected: $domains_count domains in file vs $cache_count in cache"
    
    # Force cache recreation
    redis-cli DEL "br10:blocklist:set" "br10:blocklist:domains" "br10:blocklist:checksum" "br10:blocklist:meta"
    log "Cache cleared to force recreation on next integration script run"
  else
    log "Cache consistent with domains file ($domains_count)"
  fi
else
  log "WARNING: Domains file not found: $domains_file"
fi

# Clean old client cache (more than 24 hours without activity)
inactive_clients=$(redis-cli ZRANGEBYSCORE "unbound:clients:last_seen" 0 $(( $(date +%s) - 86400 )))
if [ -n "$inactive_clients" ]; then
  for client in $inactive_clients; do
    redis-cli ZREM "unbound:clients:last_seen" "$client"
    redis-cli HDEL "unbound:clients:queries" "$client"
    log "Inactive client removed from cache: $client"
  done
fi

log "Redis cache maintenance for API completed"
exit 0
EOL

    chmod +x "$MAINT_SCRIPT"
    
    # Add to cron
    echo "0 2 * * * root $MAINT_SCRIPT > /dev/null 2>&1" >> "$CRON_FILE"
    
    log_success "Blocking API integration configured successfully"
    echo -e "${GREEN}Blocking API integration configured successfully!${NC}"
    
    return 0
}

# Function to start/restart Redis
restart_redis() {
    log "Restarting Redis service..."
    echo -e "${BLUE}Restarting Redis service...${NC}"
    
    # Check current status
    if systemctl is-active --quiet $REDIS_SERVICE; then
        echo -e "${YELLOW}Redis service is already running. Restarting...${NC}"
    else
        echo -e "${YELLOW}Redis service is not running. Starting...${NC}"
    fi
    
    # Restart service with detailed output
    restart_output=$(systemctl restart $REDIS_SERVICE 2>&1)
    restart_status=$?
    
    log "Restart command output: $restart_output"
    echo -e "${YELLOW}Restart command output: $restart_output${NC}"
    
    # Check if it started correctly
    sleep 3
    if systemctl is-active --quiet $REDIS_SERVICE; then
        log_success "Redis service restarted successfully"
        echo -e "${GREEN}Redis service restarted successfully!${NC}"
        
        # Show status information
        redis_info=$(redis-cli INFO server | grep redis_version)
        redis_memory=$(redis-cli INFO memory | grep used_memory_human)
        redis_clients=$(redis-cli INFO clients | grep connected_clients)
        
        echo -e "${BLUE}Redis version: ${GREEN}$(echo "$redis_info" | cut -d ":" -f 2)${NC}"
        echo -e "${BLUE}Memory usage: ${GREEN}$(echo "$redis_memory" | cut -d ":" -f 2)${NC}"
        echo -e "${BLUE}Connected clients: ${GREEN}$(echo "$redis_clients" | cut -d ":" -f 2)${NC}"
        
        return 0
    else
        service_status=$(systemctl status $REDIS_SERVICE 2>&1)
        log_error "Failed to restart Redis service: $service_status"
        echo -e "${RED}Failed to restart Redis service. Check the logs:${NC}"
        echo -e "${YELLOW}$service_status${NC}"
        echo -e "${YELLOW}journalctl -u $REDIS_SERVICE${NC}"
        return 1
    fi
}

# Function to check Redis status
check_redis_status() {
    log "Checking Redis status..."
    echo -e "${BLUE}Checking Redis status...${NC}"
    
    # Check if service is active
    if systemctl is-active --quiet $REDIS_SERVICE; then
        echo -e "${GREEN}Redis service is running${NC}"
    else
        echo -e "${RED}Redis service is not running${NC}"
        
        # Check reason
        service_status=$(systemctl status $REDIS_SERVICE 2>&1)
        echo -e "${YELLOW}$service_status${NC}"
        return 1
    fi
    
    # Check direct connection
    ping_output=$(redis-cli PING 2>&1)
    if echo "$ping_output" | grep -q "PONG"; then
        echo -e "${GREEN}Redis is responding correctly${NC}"
    else
        echo -e "${RED}Redis is not responding to PING command: $ping_output${NC}"
        log_error "Redis not responding to PING: $ping_output"
        return 1
    fi
    
    # Show statistics
    echo -e "\n${BLUE}Redis Statistics:${NC}"
    
    # Get statistics safely with error handling
    version=$(redis-cli INFO server 2>/dev/null | grep redis_version | cut -d ":" -f 2)
    uptime=$(redis-cli INFO server 2>/dev/null | grep uptime_in_days | cut -d ":" -f 2)
    memory_usage=$(redis-cli INFO memory 2>/dev/null | grep used_memory_human | cut -d ":" -f 2)
    max_memory_config=$(redis-cli CONFIG GET maxmemory 2>/dev/null | tail -1)
    connected_clients=$(redis-cli INFO clients 2>/dev/null | grep connected_clients | cut -d ":" -f 2)
    total_commands=$(redis-cli INFO stats 2>/dev/null | grep total_commands_processed | cut -d ":" -f 2)
    total_connections=$(redis-cli INFO stats 2>/dev/null | grep total_connections_received | cut -d ":" -f 2)
    
    if [[ "$max_memory_config" =~ ^[0-9]+$ ]]; then
        max_memory=$(awk "BEGIN {printf \"%.2f MB\", $max_memory_config/1024/1024}")
    else
        max_memory="Unknown"
    fi
    
    echo -e "${YELLOW}Version:${NC} ${version:-Unknown}"
    echo -e "${YELLOW}Uptime:${NC} ${uptime:-Unknown} days"
    echo -e "${YELLOW}Memory usage:${NC} ${memory_usage:-Unknown}"
    echo -e "${YELLOW}Maximum memory:${NC} $max_memory"
    echo -e "${YELLOW}Connected clients:${NC} ${connected_clients:-Unknown}"
    echo -e "${YELLOW}Total commands:${NC} ${total_commands:-Unknown}"
    echo -e "${YELLOW}Total connections:${NC} ${total_connections:-Unknown}"
    
    # Check if monitoring is working
    if [ -f "$SCRIPTS_DIR/redis_maintenance.sh" ] && [ -f "/etc/cron.d/br10redis" ]; then
        echo -e "${GREEN}Monitoring and maintenance scripts installed correctly${NC}"
    else
        echo -e "${RED}Monitoring scripts not correctly installed${NC}"
    fi
    
    # Test basic performance
    echo -e "\n${BLUE}Testing basic performance...${NC}"
    
    # Run simple tests
    redis-cli FLUSHDB &>/dev/null
    
    echo -e "${YELLOW}Write test (1000 keys):${NC}"
    redis-cli --raw --stat SET test:key:__rand_int__ value:__rand_int__ 1000
    
    echo -e "${YELLOW}Read test (1000 keys):${NC}"
    redis-cli --raw --stat GET test:key:__rand_int__ 1000
    
    echo -e "${YELLOW}HSET/HGET test (1000 operations):${NC}"
    redis-cli --raw --stat HSET test:hash:1 field:__rand_int__ value:__rand_int__ 1000
    
    # Clean test data
    redis-cli FLUSHDB &>/dev/null
    
    return 0
}

# Function to display menu
show_menu() {
    echo -e "${BLUE}===============================================${NC}"
    echo -e "${BLUE}      BR10 Redis Optimized Configuration       ${NC}"
    echo -e "${BLUE}===============================================${NC}"
    echo -e "${BLUE}Select an option:${NC}"
    echo -e "${GREEN}1.${NC} Install Redis"
    echo -e "${GREEN}2.${NC} Create New Redis Configuration"
    echo -e "${GREEN}3.${NC} Create Maintenance Scripts"
    echo -e "${GREEN}4.${NC} Integrate with Unbound"
    echo -e "${GREEN}5.${NC} Integrate with Blocking API"
    echo -e "${GREEN}6.${NC} Restart Redis Service"
    echo -e "${GREEN}7.${NC} Check Redis Status"
    echo -e "${GREEN}8.${NC} Run All Steps"
    echo -e "${GREEN}0.${NC} Exit"
    echo -e "${BLUE}===============================================${NC}"
}

# Main function
main() {
    # Check root permissions
    check_root
    
    # Create directory for logs
    mkdir -p "$(dirname "$LOG_FILE")"
    
    # Initialize log
    log "Script started"
    
    # Create necessary directories
    create_directories
    
    # Detect system resources
    detect_system_resources
    
    # Menu loop
    while true; do
        clear
        display_banner
        show_menu
        
        read -p "Option: " option
        
        case $option in
            1)
                clear
                install_redis
                read -p "Press ENTER to continue..."
                ;;
            2)
                clear
                create_redis_config
                read -p "Press ENTER to continue..."
                ;;
            3)
                clear
                create_maintenance_scripts
                read -p "Press ENTER to continue..."
                ;;
            4)
                clear
                integrate_with_unbound
                read -p "Press ENTER to continue..."
                ;;
            5)
                clear
                integrate_with_api
                read -p "Press ENTER to continue..."
                ;;
            6)
                clear
                restart_redis
                read -p "Press ENTER to continue..."
                ;;
            7)
                clear
                check_redis_status
                read -p "Press ENTER to continue..."
                ;;
            8)
                clear
                echo -e "${PURPLE}Running all steps...${NC}"
                
                install_redis
                create_redis_config
                create_maintenance_scripts
                integrate_with_unbound
                integrate_with_api
                restart_redis
                check_redis_status
                
                echo -e "\n${GREEN}All steps completed!${NC}"
                read -p "Press ENTER to continue..."
                ;;
            0)
                clear
                echo -e "${GREEN}Exiting...${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid option!${NC}"
                sleep 2
                ;;
        esac
    done
}

# Run main function
main
