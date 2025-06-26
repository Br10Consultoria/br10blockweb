#!/bin/bash
# BR10 DNS Blocklist Dashboard Installer
# Baseado no Tutorial de Patrick Brandao
# Version 1.2 - 23/03/2025

# Define colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Directories
BASE_DIR="/opt/br10dashboard"
CONFIG_DIR="$BASE_DIR/config"
LOG_DIR="$BASE_DIR/logs"
TEMPLATES_DIR="$BASE_DIR/templates"

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
    echo -e "${GREEN}=============================================================${NC}"
    echo -e "${GREEN}   BR10 DNS Blocklist Dashboard with HTTPS and CSRF Setup    ${NC}"
    echo -e "${GREEN}=============================================================${NC}"
    echo
}

# Function to check root permissions
check_root() {
    if [ "$(id -u)" != "0" ]; then
        echo -e "${RED}This script must be run as root.${NC}"
        exit 1
    fi
}

# Function to create directory if not exists
create_dir_if_not_exists() {
    if [ ! -d "$1" ]; then
        mkdir -p "$1"
        echo -e "${GREEN}Directory created: $1${NC}"
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
            echo -e "${RED}Critical error. Aborting installation.${NC}"
            exit 1
        fi
    fi
}

# Function to install a package
install_package() {
    PACKAGE=$1
    CRITICAL=$2

    if ! dpkg -s $PACKAGE >/dev/null 2>&1; then
        echo -e "${YELLOW}Installing $PACKAGE...${NC}"
        apt-get install -y $PACKAGE >/dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to install $PACKAGE${NC}"
            if [ "$CRITICAL" = "critical" ]; then
                echo -e "${RED}This package is critical. Aborting installation.${NC}"
                exit 1
            fi
        else
            echo -e "${GREEN}$PACKAGE installed successfully${NC}"
        fi
    else
        echo -e "${GREEN}$PACKAGE is already installed${NC}"
    fi
}

# Funcao para instalar sudo se nao estiver presente
install_sudo() {
    show_progress "Verificando e instalando sudo"
    
    if ! command -v sudo &> /dev/null; then
        echo -e "${YELLOW}O comando sudo nao esta instalado. Instalando...${NC}"
        apt-get update
        apt-get install -y sudo
        check_status "Instalacao do sudo"
    else
        echo -e "${GREEN}O comando sudo ja esta instalado${NC}"
    fi
}

# Funcao para configurar NTP
configure_ntp() {
    show_progress "Configurando NTP (Network Time Protocol)"
    
    # Instalar NTP se nao estiver presente
    if ! command -v ntpd &> /dev/null && ! systemctl status systemd-timesyncd &> /dev/null; then
        echo -e "${YELLOW}Servico NTP nao encontrado. Instalando...${NC}"
        apt-get update
        apt-get install -y ntp
        check_status "Instalacao do NTP"
    fi
    
    # Verificar qual sistema de sincronizacao esta disponivel
    if command -v ntpd &> /dev/null; then
        # Configurar servidores NTP
        echo -e "${BLUE}Configurando servidores NTP...${NC}"
        cat > /etc/ntp.conf << EOF
# BR10 NTP Configuration
driftfile /var/lib/ntp/ntp.drift
statistics loopstats peerstats clockstats
filegen loopstats file loopstats type day enable
filegen peerstats file peerstats type day enable
filegen clockstats file clockstats type day enable

# Servidores NTP no Brasil
server a.st1.ntp.br iburst
server b.st1.ntp.br iburst
server c.st1.ntp.br iburst
server d.st1.ntp.br iburst
server gps.ntp.br iburst
EOF
        
        # Reiniciar servico NTP
        systemctl restart ntp
        systemctl enable ntp
        check_status "Configuracao e reinicio do NTP"
    elif systemctl status systemd-timesyncd &> /dev/null; then
        # Para sistemas com systemd-timesyncd
        echo -e "${BLUE}Configurando systemd-timesyncd...${NC}"
        cat > /etc/systemd/timesyncd.conf << EOF
[Time]
NTP=a.st1.ntp.br b.st1.ntp.br c.st1.ntp.br d.st1.ntp.br gps.ntp.br
FallbackNTP=0.pool.ntp.org 1.pool.ntp.org 2.pool.ntp.org 3.pool.ntp.org
EOF
        
        # Reiniciar servico timesyncd
        systemctl restart systemd-timesyncd
        systemctl enable systemd-timesyncd
        check_status "Configuracao e reinicio do systemd-timesyncd"
    else
        echo -e "${RED}Nao foi possivel identificar um servico NTP compativel${NC}"
        return 1
    fi
    
    # Verificar sincronizacao
    echo -e "${BLUE}Verificando sincronizacao de horario...${NC}"
    if command -v ntpq &> /dev/null; then
        ntpq -p
    elif command -v timedatectl &> /dev/null; then
        timedatectl status
    fi
    
    echo -e "${GREEN}Configuracao de NTP concluida${NC}"
}

# Function to ask the user
ask() {
    read -p "$1 " answer
    echo $answer
}
# Step: Check prerequisites for both dashboard and HTTPS
check_prerequisites() {
    show_progress "Checking prerequisites"
    
    # Update package list
    apt-get update -qq
    
    # Install essential packages for dashboard and HTTPS
    ESSENTIAL_PACKAGES=(
        "python3" 
        "python3-pip" 
        "python3-venv" 
        "curl" 
        "wget" 
        "nginx" 
        "certbot" 
		"tmux"
        "python3-certbot-nginx"
    )
    
    for pkg in "${ESSENTIAL_PACKAGES[@]}"; do
        install_package $pkg
    done
    
    # Check firewall
    if command -v ufw &> /dev/null; then
        echo -e "${YELLOW}Configuring firewall (UFW)...${NC}"
        ufw allow 'Nginx HTTP' || echo -e "${YELLOW}Failed to configure UFW for HTTP${NC}"
        ufw allow 'Nginx HTTPS' || echo -e "${YELLOW}Failed to configure UFW for HTTPS${NC}"
        ufw allow 8084/tcp || echo -e "${YELLOW}Failed to configure UFW for port 8084${NC}"
    else
        echo -e "${YELLOW}UFW is not installed. Skipping firewall configuration.${NC}"
    fi
    
    check_status "Prerequisite check completed"
}
# Nova funcao para iniciar com tmux
start_dashboard_tmux() {
    show_progress "Starting dashboard in tmux session"
    
    # Kill existing session if exists
    tmux kill-session -t web01 2>/dev/null || true
    
    # Create new tmux session
    tmux new-session -d -s web01 -c "$BASE_DIR"
    
    # Activate virtual environment and start app in tmux
    tmux send-keys -t web01 "cd $BASE_DIR && source venv/bin/activate && python app.py" C-m
    
    check_status "Dashboard tmux session started"
    
    # Add startup script
    cat > "$BASE_DIR/start.sh" << EOF
#!/bin/bash
# Start BR10 dashboard in tmux
cd $BASE_DIR
tmux kill-session -t web01 2>/dev/null || true
tmux new-session -d -s web01 -c "$BASE_DIR"
tmux send-keys -t web01 "source venv/bin/activate && python app.py" C-m
echo "Dashboard started in tmux session 'web01'"
echo "To view, use: tmux attach -t web01"
EOF
    chmod +x "$BASE_DIR/start.sh"
    
    # Add to user instructions
    echo -e "${YELLOW}Added startup script at $BASE_DIR/start.sh${NC}"
    echo -e "${YELLOW}To manually start the dashboard, run: $BASE_DIR/start.sh${NC}"
}


# Step: Configure directories
setup_directories() {
    show_progress "Setting up directories"
    
    create_dir_if_not_exists "$BASE_DIR"
    create_dir_if_not_exists "$CONFIG_DIR"
    create_dir_if_not_exists "$LOG_DIR"
    create_dir_if_not_exists "$TEMPLATES_DIR"
    create_dir_if_not_exists "$BASE_DIR/history"
    create_dir_if_not_exists "$BASE_DIR/backups"
    
    check_status "Directory setup completed"
}

# Step: Configure environment for Dashboard
setup_dashboard_env() {
    show_progress "Setting up Python environment for Dashboard"
    
    # Create Python virtual environment
    if [ ! -d "$BASE_DIR/venv" ]; then
        python3 -m venv "$BASE_DIR/venv"
        check_status "Python virtual environment creation"
    else
        echo -e "${GREEN}Python virtual environment already exists${NC}"
    fi
    
    # Activate virtual environment and install dependencies
    source "$BASE_DIR/venv/bin/activate"
    if [ -f "$BASE_DIR/requirements.txt" ]; then
         pip install -r "$BASE_DIR/requirements.txt"
        check_status "Python dependencies installation from requirements.txt"
    else
        # Fallback to basic dependencies
        pip install flask requests werkzeug flask-wtf
        check_status "Python basic dependencies installation"
    fi
    
    # Deactivate virtual environment
    deactivate
}

# Step: Prepare Dashboard files
prepare_dashboard_files() {
    show_progress "Preparing Dashboard files"
    
    # Create main Flask application file
    cat > "$BASE_DIR/app.py" << 'EOF'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# BR10 BlockList Dashboard
# Version: 1.1 - 23/03/2025
# Description: Web interface for BR10 DNS Blocklist system statistics

import os
import json
import re
import time
import datetime
import hashlib
import logging
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_wtf.csrf import CSRFProtect

# Configuration
BASE_DIR = "/opt/br10dashboard"
BLOCKED_DOMAINS_PATH = os.path.join(BASE_DIR, "blocked_domains.txt")
HISTORY_DIR = os.path.join(BASE_DIR, "history")
LOG_DIR = os.path.join(BASE_DIR, "logs")
UNBOUND_ZONE_FILE = "/var/lib/unbound/br10block-rpz.zone"
USERS_FILE = os.path.join(BASE_DIR, "users.json")

# Flask app configuration
app = Flask(__name__, 
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"))
app.secret_key = os.urandom(24)  # Session key
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=24)
app.config['PREFERRED_URL_SCHEME'] = 'https'

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=os.path.join(LOG_DIR, 'dashboard.log'),
    filemode='a'
)
logger = logging.getLogger('dashboard')

# User and authentication functions
def init_users():
    """Initialize users file if it doesn't exist"""
    if not os.path.exists(USERS_FILE):
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        default_admin = {
            "username": "admin",
            "password": hashlib.sha256("admin123".encode()).hexdigest(),
            "role": "admin"
        }
        with open(USERS_FILE, 'w') as f:
            json.dump({"users": [default_admin]}, f, indent=2)
        logger.info("Users file created with default admin user")

def get_users():
    """Return the list of users"""
    if not os.path.exists(USERS_FILE):
        init_users()
    
    with open(USERS_FILE, 'r') as f:
        return json.load(f).get("users", [])

def authenticate_user(username, password):
    """Verify if user credentials are valid"""
    users = get_users()
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    for user in users:
        if user["username"] == username and user["password"] == password_hash:
            return user
    return None

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Utility functions for data analysis
def load_blocked_domains():
    """Load list of blocked domains"""
    try:
        if not os.path.exists(BLOCKED_DOMAINS_PATH):
            return []
        
        with open(BLOCKED_DOMAINS_PATH, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except Exception as e:
        logger.error(f"Error loading blocked domains: {e}")
        return []

def load_zone_file():
    """Load and parse Unbound RPZ zone file"""
    zone_data = {
        "total_domains": 0,
        "last_modified": None,
        "domains_sample": []
    }
    
    try:
        if not os.path.exists(UNBOUND_ZONE_FILE):
            return zone_data
        
        # Get file info
        file_stat = os.stat(UNBOUND_ZONE_FILE)
        zone_data["last_modified"] = datetime.datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        
        # Parse zone file
        domain_count = 0
        sample_domains = []
        
        with open(UNBOUND_ZONE_FILE, 'r') as f:
            for line in f:
                if 'IN CNAME' in line and not line.startswith(';'):
                    domain_count += 1
                    # Extract domain from line
                    match = re.match(r'^([^\s]+)', line.strip())
                    if match and len(sample_domains) < 20:  # Save up to 20 examples
                        domain = match.group(1)
                        if domain.endswith('.'):
                            domain = domain[:-1]
                        sample_domains.append(domain)
        
        zone_data["total_domains"] = domain_count
        zone_data["domains_sample"] = sample_domains
        
        return zone_data
    except Exception as e:
        logger.error(f"Error loading zone file: {e}")
        return zone_data

def load_history_data(limit=30):
    """Load blocklist update history data"""
    try:
        history_files = []
        if os.path.exists(HISTORY_DIR):
            for filename in os.listdir(HISTORY_DIR):
                if filename.startswith("blocklist_") and filename.endswith(".json"):
                    filepath = os.path.join(HISTORY_DIR, filename)
                    file_time = os.path.getmtime(filepath)
                    history_files.append((filepath, file_time))
        
        # Sort by date (most recent first)
        history_files.sort(key=lambda x: x[1], reverse=True)
        
        # Load data from history files
        history_data = []
        for filepath, _ in history_files[:limit]:
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    # Convert timestamp to readable format
                    if "timestamp" in data:
                        try:
                            dt = datetime.datetime.fromisoformat(data["timestamp"])
                            data["formatted_time"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            data["formatted_time"] = data["timestamp"]
                    history_data.append(data)
            except Exception as e:
                logger.error(f"Error processing history file {filepath}: {e}")
                continue
        
        return history_data
    except Exception as e:
        logger.error(f"Error loading history data: {e}")
        return []

def get_unbound_stats():
    """Get Unbound server statistics"""
    try:
        stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "queries": 0,
            "uptime": "Unknown",
            "cache_hit_ratio": "0%",
            "response_times": {}
        }
        
        # Check if unbound-control is available
        unbound_control = "/usr/sbin/unbound-control"
        if not os.path.exists(unbound_control):
            unbound_control = "/usr/bin/unbound-control"
            if not os.path.exists(unbound_control):
                logger.warning("unbound-control not found")
                return stats
        
        # Run unbound-control stats
        import subprocess
        try:
            output = subprocess.check_output([unbound_control, "stats"], universal_newlines=True)
            
            # Parse output
            for line in output.splitlines():
                if "total.num.queries=" in line:
                    stats["queries"] = int(line.split("=")[1])
                elif "total.num.cachehits=" in line:
                    stats["cache_hits"] = int(line.split("=")[1])
                elif "total.num.cachemiss=" in line:
                    stats["cache_misses"] = int(line.split("=")[1])
                elif line.startswith("histogram."):
                    parts = line.split("=")
                    if len(parts) == 2:
                        time_range = parts[0].replace("histogram.", "")
                        count = parts[1]
                        if int(count) > 0:
                            stats["response_times"][time_range] = count
            
            # Calculate uptime
            uptime_output = subprocess.check_output([unbound_control, "status"], universal_newlines=True)
            for line in uptime_output.splitlines():
                if "uptime:" in line:
                    stats["uptime"] = line.split("uptime:")[1].strip()
                    break
            
            # Calculate cache hit ratio
            if stats["queries"] > 0:
                hit_ratio = (stats["cache_hits"] / stats["queries"]) * 100
                stats["cache_hit_ratio"] = f"{hit_ratio:.2f}%"
        
        except subprocess.SubprocessError as e:
            logger.error(f"Error running unbound-control: {e}")
        
        return stats
    except Exception as e:
        logger.error(f"Error getting Unbound statistics: {e}")
        return stats

def get_recent_access_attempts(limit=100):
    """Get recent blocked domain access attempts (from logs)"""
    try:
        # Check if Unbound log file exists
        unbound_log = "/var/log/unbound.log"
        if not os.path.exists(unbound_log):
            # Try alternative
            unbound_log = "/var/log/syslog"
            if not os.path.exists(unbound_log):
                logger.warning("Unbound log file not found")
                return []
        
        # Extract blocked access attempts
        import subprocess
        try:
            # Look for RPZ blocks
            output = subprocess.check_output(
                ["grep", "rpz", unbound_log, "-r", "--include=*.log", "/var/log/"],
                universal_newlines=True,
                stderr=subprocess.PIPE
            )
            
            attempts = []
            pattern = r'(\w{3}\s+\d+\s+\d+:\d+:\d+).*rpz-log.*query\s+([\w\.-]+)\s+.*from\s+(\d+\.\d+\.\d+\.\d+)'
            
            for line in output.splitlines()[-limit:]:
                match = re.search(pattern, line)
                if match:
                    timestamp, domain, client_ip = match.groups()
                    attempts.append({
                        "time": timestamp,
                        "domain": domain,
                        "client_ip": client_ip
                    })
            
            # Sort by time (most recent first)
            return sorted(attempts, key=lambda x: x["time"], reverse=True)
            
        except subprocess.SubprocessError as e:
            logger.warning(f"Error extracting access attempts from logs: {e}")
            return []
            
    except Exception as e:
        logger.error(f"Error getting access attempts: {e}")
        return []

# Application routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = authenticate_user(username, password)
        if user:
            session['user'] = user
            logger.info(f"User {username} logged in successfully")
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
            logger.warning(f"Login attempt failed for user: {username}")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout route"""
    if 'user' in session:
        username = session['user']['username']
        session.pop('user', None)
        logger.info(f"User {username} logged out")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    """Dashboard main page"""
    return render_template('dashboard.html')

@app.route('/domains')
@login_required
def domains():
    """Blocked domains listing page"""
    return render_template('domains.html')

@app.route('/attempts')
@login_required
def attempts():
    """Blocked access attempts page"""
    return render_template('attempts.html')

@app.route('/history')
@login_required
def history():
    """Update history page"""
    return render_template('history.html')

# API endpoints to provide data to frontend
@app.route('/api/stats')
@login_required
def api_stats():
    """API for general statistics"""
    try:
        blocked_domains = load_blocked_domains()
        zone_data = load_zone_file()
        unbound_stats = get_unbound_stats()
        
        return jsonify({
            "blocked_domains_count": len(blocked_domains),
            "zone_file": zone_data,
            "unbound": unbound_stats,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/domains')
@login_required
def api_domains():
    """API to list blocked domains"""
    try:
        blocked_domains = load_blocked_domains()
        
        # Pagination
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 100))
        search = request.args.get('search', '')
        
        if search:
            filtered_domains = [d for d in blocked_domains if search.lower() in d.lower()]
        else:
            filtered_domains = blocked_domains
        
        total_domains = len(filtered_domains)
        total_pages = (total_domains + per_page - 1) // per_page
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        return jsonify({
            "domains": filtered_domains[start_idx:end_idx],
            "total": total_domains,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        })
    except Exception as e:
        logger.error(f"Error listing domains: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/history')
@login_required
def api_history():
    """API for update history"""
    try:
        limit = int(request.args.get('limit', 30))
        history_data = load_history_data(limit)
        
        return jsonify({
            "history": history_data,
            "count": len(history_data)
        })
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/attempts')
@login_required
def api_attempts():
    """API for blocked domain access attempts"""
    try:
        limit = int(request.args.get('limit', 100))
        attempts = get_recent_access_attempts(limit)
        
        return jsonify({
            "attempts": attempts,
            "count": len(attempts)
        })
    except Exception as e:
        logger.error(f"Error getting access attempts: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/users', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_users():
    """API to manage users"""
    # Check if admin
    if session['user'].get('role') != 'admin':
        return jsonify({"error": "Permission denied"}), 403
    
    if request.method == 'GET':
        # List users
        users = get_users()
        # Remove passwords
        for user in users:
            user.pop('password', None)
        return jsonify({"users": users})
    
    elif request.method == 'POST':
        # Add or update user
        data = request.json
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({"error": "Incomplete data"}), 400
        
        username = data['username']
        password = data['password']
        role = data.get('role', 'user')
        
        users = get_users()
        
        # Check if user already exists
        user_exists = False
        for user in users:
            if user['username'] == username:
                user['password'] = hashlib.sha256(password.encode()).hexdigest()
                user['role'] = role
                user_exists = True
                break
        
        # Add new user
        if not user_exists:
            new_user = {
                "username": username,
                "password": hashlib.sha256(password.encode()).hexdigest(),
                "role": role
            }
            users.append(new_user)
        
        # Save changes
        with open(USERS_FILE, 'w') as f:
            json.dump({"users": users}, f, indent=2)
        
        logger.info(f"User {username} {'updated' if user_exists else 'added'}")
        return jsonify({"success": True, "message": f"User {username} {'updated' if user_exists else 'added'} successfully"})
    
    elif request.method == 'DELETE':
        # Remove user
        data = request.json
        if not data or 'username' not in data:
            return jsonify({"error": "Incomplete data"}), 400
        
        username = data['username']
        
        # Don't allow removing your own user
        if username == session['user']['username']:
            return jsonify({"error": "Cannot remove your own user"}), 400
        
        users = get_users()
        users = [user for user in users if user['username'] != username]
        
        # Save changes
        with open(USERS_FILE, 'w') as f:
            json.dump({"users": users}, f, indent=2)
        
        logger.info(f"User {username} removed")
        return jsonify({"success": True, "message": f"User {username} removed successfully"})

# Application initialization
if __name__ == '__main__':
    # Ensure log directory exists
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # Initialize users
    init_users()
    
    # Start server
    app.run(host='0.0.0.0', port=8084, debug=False)
EOF
    
    # Make file executable
    chmod +x "$BASE_DIR/app.py"
    check_status "Dashboard main file creation"
    
    # Create readme explaining how to add templates
    cat > "$BASE_DIR/README.md" << 'EOF'
# BR10 DNS Blocklist Dashboard

This dashboard provides a web interface for the BR10 DNS Blocklist system with HTTPS and CSRF protection.

## Default Access Information

The dashboard can be accessed at: https://your-domain.com

Default credentials:
- Username: admin
- Password: admin123

## Directory Structure

- `/opt/br10dashboard/` - Main directory
  - `templates/` - HTML template files
  - `static/` - Static files (CSS, JS, images)
  - `logs/` - Log files
  - `config/` - Configuration files
  - `history/` - History data
  - `backups/` - Backup files
  - `venv/` - Python virtual environment
EOF
    
    check_status "README creation for Dashboard"
}
# Step: Configure Nginx and HTTPS
setup_nginx_https() {
    show_progress "Setting up Nginx and HTTPS"
    
    # Ask for domain
    echo -e "${YELLOW}HTTPS and CSRF Setup for BR10 DNS Blocklist${NC}"
    echo "----------------------------------------"
    DOMAIN=$(ask "Enter domain for the certificate (e.g., your-domain.com):")
    
    if [ -z "$DOMAIN" ]; then
        echo -e "${RED}Domain cannot be empty. Using server IP address instead.${NC}"
        DOMAIN=$(hostname -I | awk '{print $1}')
        echo -e "${YELLOW}Using IP address as domain: $DOMAIN${NC}"
    fi
    
    # Create Nginx configuration
    show_progress "Creating Nginx configuration for domain $DOMAIN"
    cat > /etc/nginx/sites-available/br10dashboard << EOF
server {
    listen 80;
    server_name $DOMAIN;

    access_log /var/log/nginx/br10_access.log;
    error_log /var/log/nginx/br10_error.log;

    location / {
        proxy_pass http://127.0.0.1:8084;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

    # Enable site
    show_progress "Enabling site in Nginx"
    ln -sf /etc/nginx/sites-available/br10dashboard /etc/nginx/sites-enabled/
    nginx -t || { 
        echo -e "${RED}Invalid Nginx configuration${NC}"; 
        echo -e "${YELLOW}Continuing without HTTPS setup. You can configure it manually later.${NC}"; 
        return 1;
    }
    systemctl restart nginx || {
        echo -e "${RED}Failed to restart Nginx${NC}"; 
        echo -e "${YELLOW}Continuing without HTTPS setup. You can configure it manually later.${NC}"; 
        return 1;
    }
    
    # Check if domain is a valid hostname (not an IP address)
    if [[ $DOMAIN =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo -e "${YELLOW}Warning: Using IP address ($DOMAIN) instead of a domain name.${NC}"
        echo -e "${YELLOW}Let's Encrypt requires a valid domain name for certificate issuance.${NC}"
        echo -e "${YELLOW}Skipping Let's Encrypt certificate setup.${NC}"
        echo -e "${YELLOW}You can access the dashboard at: http://$DOMAIN:8084${NC}"
        return 0
    fi
    
    # Get SSL certificate with Let's Encrypt
    show_progress "Getting SSL certificate for $DOMAIN"
	# Try to obtain SSL certificate
    if certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN; then
        echo -e "${GREEN}SSL certificate obtained successfully!${NC}"
        echo -e "${GREEN}HTTPS has been configured successfully.${NC}"
    else
        echo -e "${YELLOW}Failed to obtain SSL certificate. Continuing without HTTPS.${NC}"
        echo -e "${YELLOW}You can try running certbot manually later:${NC}"
        echo -e "${YELLOW}  sudo certbot --nginx -d $DOMAIN${NC}"
    fi
    
    check_status "Nginx and HTTPS setup"
}

# Setup Symbolic Links for data access
setup_data_links() {
    show_progress "Setting up data directory links"
    
    # Create links from original paths to our new structure
    if [ -d "/var/lib/br10api" ]; then
        if [ -f "/var/lib/br10api/blocked_domains.txt" ]; then
            ln -sf "/var/lib/br10api/blocked_domains.txt" "$BASE_DIR/blocked_domains.txt"
            check_status "Linked blocked domains file"
        fi
        
        if [ -d "/var/lib/br10api/history" ]; then
            # Link existing history files
            for file in /var/lib/br10api/history/*; do
                if [ -f "$file" ]; then
                    basename=$(basename "$file")
                    ln -sf "$file" "$BASE_DIR/history/$basename"
                fi
            done
            check_status "Linked history files"
        fi
    else
        echo -e "${YELLOW}BR10 API data directory not found. Will create new data directory.${NC}"
        touch "$BASE_DIR/blocked_domains.txt"
    fi
}
# Funcao principal
main() {
   display_banner
   check_root
   
   echo -e "${GREEN}Bem-vindo ao Instalador do Dashboard BR10 DNS Blocklist${NC}"
   echo -e "${BLUE}Este script ira executar as seguintes acões:${NC}"
   echo -e " ${GREEN}1.${NC} Verificar e instalar pre-requisitos para o Dashboard e HTTPS"
   echo -e " ${GREEN}2.${NC} Configurar diretorios necessarios"
   echo -e " ${GREEN}3.${NC} Configurar ambiente Python para o Dashboard"
   echo -e " ${GREEN}4.${NC} Instalar arquivos do Dashboard"
   echo -e " ${GREEN}5.${NC} Configurar Nginx e HTTPS com Let's Encrypt"
   echo -e " ${GREEN}6.${NC} Configurar e iniciar o servico do Dashboard"
   echo
   
   read -p "Deseja continuar com a instalacao? (S/n): " confirm
   if [[ "$confirm" == [Nn] ]]; then
       echo -e "${YELLOW}Instalacao cancelada pelo usuario${NC}"
       exit 0
   fi
    
    # Run installation steps
    echo -e "${BLUE}Iniciando Instalacao...${NC}"
    
    check_prerequisites
    setup_directories
    setup_dashboard_env
    prepare_dashboard_files
    setup_data_links
    setup_nginx_https
    start_dashboard_tmux
    
    
    # Get server IP for display
    SERVER_IP=$(hostname -I | awk '{print $1}')
    
    echo
    echo -e "${GREEN}=============================================================${NC}"
    echo -e "${GREEN}       BR10 Dashboard installed successfully!                ${NC}"
    echo -e "${GREEN}=============================================================${NC}"
    echo
    echo -e "${BLUE}To access the Dashboard Web interface, open your browser and go to:${NC}"
    echo -e "${GREEN}http://$SERVER_IP:8084${NC}"
    echo
    echo -e "${BLUE}If HTTPS was set up successfully, you can also use:${NC}"
    echo -e "${GREEN}https://$DOMAIN${NC}"
    echo
    echo -e "${BLUE}Default credentials:${NC}"
    echo -e "${GREEN}Username: admin${NC}"
    echo -e "${GREEN}Password: admin123${NC}"
    echo
    echo -e "${YELLOW}IMPORTANT: Please place your HTML templates in:${NC}"
    echo -e "${YELLOW}$TEMPLATES_DIR${NC}"
    echo
    echo -e "${BLUE}Thank you for using the BR10 DNS Blocklist Dashboard installer!${NC}"
}

# Execute main function
main
