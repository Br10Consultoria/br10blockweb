#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 DNS Dashboard
==================

Interface web para visualização de estatísticas, testes DNS e monitoramento
do sistema de bloqueio de domínios BR10.

Autor: BR10 Team
Versão: 2.0.0
Data: 2025-01-25
"""

import glob
import hashlib
import json
import logging
import os
import re
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional, Union

import redis
from dotenv import load_dotenv
from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   send_file, session, url_for)
from flask_wtf.csrf import CSRFProtect

from system_resources import (get_system_stats, start_system_monitor,
                              stop_system_monitor, system_monitor)

# Carregar variáveis de ambiente
load_dotenv()

# Configurações da aplicação
class Config:
    """Configurações da aplicação."""
    
    BASE_DIR = Path(os.getenv("BASE_DIR", "/opt/br10dashboard"))
    BLOCKED_DOMAINS_PATH = Path(os.getenv("BLOCKED_DOMAINS_PATH", "/var/lib/br10api/blocked_domains.txt"))
    HISTORY_DIR = Path(os.getenv("HISTORY_DIR", BASE_DIR / "data" / "history"))
    LOG_DIR = Path(os.getenv("LOG_DIR", BASE_DIR / "logs"))
    UNBOUND_ZONE_FILE = Path(os.getenv("UNBOUND_ZONE_FILE", "/var/lib/unbound/br10block-rpz.zone"))
    USERS_FILE = Path(os.getenv("USERS_FILE", BASE_DIR / "config" / "users.json"))
    
    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    CACHE_TTL = int(os.getenv("CACHE_TTL", 300))
    
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(24))
    SESSION_LIFETIME_HOURS = int(os.getenv("SESSION_LIFETIME_HOURS", 24))
    
    @classmethod
    def ensure_directories(cls) -> None:
        """Garante que os diretórios necessários existam."""
        for directory in [cls.HISTORY_DIR, cls.LOG_DIR, cls.USERS_FILE.parent]:
            directory.mkdir(parents=True, exist_ok=True)


# Configuração do Flask
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=Config.SESSION_LIFETIME_HOURS)
app.config['PREFERRED_URL_SCHEME'] = 'https'

# CSRF Protection
csrf = CSRFProtect(app)

# Configuração de logging
def setup_logging() -> logging.Logger:
    """Configura sistema de logging."""
    Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=Config.LOG_DIR / 'dashboard.log',
        filemode='a'
    )
    
    logger = logging.getLogger('br10_dashboard')
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# Cliente Redis
try:
    redis_client = redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    redis_client.ping()
    logger.info("Conexão Redis estabelecida")
except Exception as e:
    logger.warning(f"Redis não disponível: {e}")
    redis_client = None


class UserManager:
    """Gerenciador de usuários."""
    
    @staticmethod
    def init_users() -> None:
        """Inicializa arquivo de usuários se não existir."""
        if not Config.USERS_FILE.exists():
            default_admin = {
                "username": "admin",
                "password": hashlib.sha256("admin123".encode()).hexdigest(),
                "role": "admin"
            }
            
            users_data = {"users": [default_admin]}
            
            with open(Config.USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(users_data, f, indent=2)
            
            logger.info("Arquivo de usuários criado com usuário admin padrão")
    
    @staticmethod
# Implementacao alternativa para netifaces
class FallbackNetifaces:
    def interfaces(self):
        """Retorna uma lista de interfaces de rede usando comandos do sistema"""
        try:
            import subprocess
            result = subprocess.run(['ip', '-o', 'link', 'show'], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   text=True, 
                                   check=False)

            interfaces = []
            for line in result.stdout.splitlines():
                if ': ' in line:
                    parts = line.split(': ')
                    if len(parts) >= 2:
                        iface = parts[1].split('@')[0]
                        interfaces.append(iface)

            return interfaces
        except Exception as e:
            logging.error(f"Erro ao obter interfaces: {e}")
            # Retornar algumas interfaces comuns como fallback
            return ['eth0', 'ens3', 'ens5', 'eth1']

# Use a implementacao alternativa se netifaces nao estiver disponivel
try:
    import netifaces
except ImportError:
    logging.warning("Modulo netifaces nao encontrado. Usando implementacao alternativa.")
    netifaces = FallbackNetifaces()
# Dicionario para armazenar o estado dos testes
teste_avancado_jobs = {}

# Carregando variaveis de ambiente
load_dotenv()

# Manter o BASE_DIR original
BASE_DIR = os.getenv("BASE_DIR", "/opt/br10dashboard")

# Alterar apenas o caminho para os dominios bloqueados
BLOCKED_DOMAINS_PATH = os.getenv("BLOCKED_DOMAINS_PATH", "/var/lib/br10api/blocked_domains.txt")

# Manter os demais caminhos inalterados
HISTORY_DIR = os.getenv("HISTORY_DIR", "/opt/br10dashboard/data/history")
LOG_DIR = os.getenv("LOG_DIR", os.path.join(BASE_DIR, "logs"))
UNBOUND_ZONE_FILE = os.getenv("UNBOUND_ZONE_FILE", "/var/lib/unbound/br10block-rpz.zone")
USERS_FILE = os.getenv("USERS_FILE", os.path.join(BASE_DIR, "config/users.json"))

# Configuracao do app Flask
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Chave para sessoes
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['PREFERRED_URL_SCHEME'] = 'https'
csrf = CSRFProtect(app)

# Configuracao de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=os.path.join(LOG_DIR, 'dashboard.log'),
    filemode='a'
)
logger = logging.getLogger('dashboard')

# Configuracao do Redis
redis_client = redis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)
CACHE_TTL = 300  # 5 minutos em segundos

# Funcoes para usuarios e autenticacao
def init_users():
    """Inicializa o arquivo de usuarios se nao existir"""
    if not os.path.exists(USERS_FILE):
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        default_admin = {
            "username": "MiralvoJunior",
            "password": hashlib.sha256("B3ni0808@#$".encode()).hexdigest(),
            "role": "admin"
        }
        with open(USERS_FILE, 'w') as f:
            json.dump({"users": [default_admin]}, f, indent=2)
        logger.info("Arquivo de usuarios criado com usuario admin padrao")

def get_users():
    """Retorna a lista de usuarios"""
    if not os.path.exists(USERS_FILE):
        init_users()
    
    with open(USERS_FILE, 'r') as f:
        return json.load(f).get("users", [])

def authenticate_user(username, password):
    """Verifica se as credenciais do usuario sao validas"""
    users = get_users()
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    for user in users:
        if user["username"] == username and user["password"] == password_hash:
            return user
    return None

# Decorator para exigir login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Dicionario para armazenar o estado dos testes
dns_test_jobs = {}

@app.route('/dns_tests')
@login_required
def dns_tests_page():
    """Pagina de testes Diversos de DNS"""
    return render_template('dns_tests.html')

@app.route('/api/dns_tests/start', methods=['POST'])
@login_required
def start_dns_test():
    """API para iniciar um teste de DNS"""
    try:
        data = request.json
        test_type = data.get('test_type', 'latency')
        
        # Validar tipo de teste
        valid_types = ['latency', 'hypercache', 'cache', 'all']
        if test_type not in valid_types:
            return jsonify({"error": f"Tipo de teste invalido. Tipos validos: {', '.join(valid_types)}"}), 400
        
        # Gerar ID unico para o teste
        test_id = str(uuid.uuid4())
        
        # Inicializar estado do teste
        dns_test_jobs[test_id] = {
            "status": "Inicializando...",
            "progress": 0,
            "logs": [],
            "completed": False,
            "result_file": None,
            "test_type": test_type,
            "start_time": datetime.now().isoformat()
        }
        
        # Iniciar thread para executar o teste
        thread = threading.Thread(target=run_dns_test, args=(test_id, test_type))
        thread.daemon = True
        thread.start()
        
        return jsonify({"test_id": test_id})
    except Exception as e:
        logger.error(f"Erro ao iniciar teste DNS: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/dns_tests/status/<test_id>', methods=['GET'])
@login_required
def check_dns_test_status(test_id):
    """API para verificar o status de um teste DNS"""
    try:
        if test_id not in dns_test_jobs:
            return jsonify({"error": "ID de teste invalido"}), 404
        
        job = dns_test_jobs[test_id]
        
        # Obter ultimo ID de log visto pelo cliente
        last_log_id = int(request.args.get('last_log_id', 0))
        
        # Logs que o cliente ainda nao viu
        new_logs = job["logs"][last_log_id:]
        
        return jsonify({
            "status": job["status"],
            "progress": job["progress"],
            "new_logs": new_logs,
            "last_log_id": len(job["logs"]),
            "completed": job["completed"],
            "result_file": job["result_file"] if job["completed"] else None
        })
    except Exception as e:
        logger.error(f"Erro ao verificar status do teste DNS: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/dns_tests/previous', methods=['GET'])
@login_required
def get_previous_dns_tests():
    """API para obter testes DNS anteriores"""
    try:
        # Encontrar arquivos JSON de resultados
        report_dir = "/var/log/br10"
        result_files = []
        
        for test_type in ['latency', 'hypercache', 'cache']:
            pattern = os.path.join(report_dir, f"{test_type}_test_*.json")
            result_files.extend(glob.glob(pattern))
        
        # Carregar informacoes basicas de cada arquivo
        tests = []
        
        for file_path in sorted(result_files, reverse=True):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                # Extrair tipo de teste do nome do arquivo
                file_name = os.path.basename(file_path)
                test_type = file_name.split('_')[0]
                
                # Determinar resumo baseado no tipo de teste
                summary = "Teste executado com sucesso"
                if test_type == 'latency' and 'summary' in data:
                    avg_time = data['summary'].get('overall', 'N/A')
                    summary = f"Tempo medio: {avg_time}ms"
                elif test_type == 'hypercache' and 'summary' in data:
                    efficiency = data['summary'].get('cache_efficiency', 'N/A')
                    summary = f"Eficiencia: {efficiency}"
                
                # Adicionar à lista
                tests.append({
                    "timestamp": data.get('timestamp', 'Desconhecido'),
                    "type": test_type,
                    "summary": summary,
                    "result_file": f'/api/dns_tests/results/{os.path.basename(file_path)}'
                })
            except Exception as e:
                logger.error(f"Erro ao processar arquivo de resultados {file_path}: {e}")
        
        return jsonify({"tests": tests})
    except Exception as e:
        logger.error(f"Erro ao obter testes DNS anteriores: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/dns_tests/results/<filename>', methods=['GET'])
@login_required
def get_dns_test_results(filename):
    """API para obter um arquivo de resultados especifico"""
    try:
        report_dir = "/var/log/br10"
        file_path = os.path.join(report_dir, filename)
        
        # Verificar se o arquivo existe e esta dentro do diretorio permitido
        if not os.path.exists(file_path) or not file_path.startswith(report_dir):
            return jsonify({"error": "Arquivo nao encontrado"}), 404
        
        # Enviar o arquivo JSON
        return send_file(file_path, mimetype='application/json')
    except Exception as e:
        logger.error(f"Erro ao obter resultados do teste DNS: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/system_resources')
@login_required
def system_resources_page():
    """Pagina de monitoramento de recursos do sistema"""
    return render_template('system_resources.html')

@app.route('/api/system/start_monitor', methods=['POST'])
@login_required
def api_start_monitor():
    """Inicia o monitoramento de recursos do sistema"""
    try:
        data = request.json or {}
        interval = int(data.get('interval', 5))
        
        # Garantir um intervalo razoavel
        if interval < 2:
            interval = 2
        elif interval > 60:
            interval = 60
            
        success = start_system_monitor(interval)
        
        return jsonify({
            "success": success,
            "message": f"Monitoramento iniciado com intervalo de {interval} segundos" if success else "Monitoramento ja esta ativo"
        })
    except Exception as e:
        logger.error(f"Erro ao iniciar monitoramento: {e}")
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/system/stop_monitor', methods=['POST'])
@login_required
def api_stop_monitor():
    """Para o monitoramento de recursos do sistema"""
    try:
        stop_system_monitor()
        return jsonify({
            "success": True,
            "message": "Monitoramento parado com sucesso"
        })
    except Exception as e:
        logger.error(f"Erro ao parar monitoramento: {e}")
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/system/stats')
@login_required
def api_system_stats():
    """Retorna estatisticas atuais do sistema"""
    try:
        update = request.args.get('update', 'false').lower() == 'true'
        stats = get_system_stats(update)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Erro ao obter estatisticas do sistema: {e}")
        return jsonify({"error": str(e)})

# Rota para obter um snapshot do htop
@app.route('/api/system/htop')
@login_required
def api_htop_snapshot():
    """Retorna uma captura do htop como texto"""
    try:
        # Verificar se o usuario e admin
        if session['user'].get('role') != 'admin':
            return jsonify({"error": "Permissao negada"}), 403
            
        # Tentar executar htop em modo batch
        try:
            output = subprocess.check_output(["htop", "-C", "-b", "-n", "1"], 
                                           universal_newlines=True, 
                                           stderr=subprocess.PIPE)
            return jsonify({"output": output})
        except (subprocess.SubprocessError, FileNotFoundError):
            # Tentar top como fallback
            output = subprocess.check_output(["top", "-b", "-n", "1"], 
                                           universal_newlines=True, 
                                           stderr=subprocess.PIPE)
            return jsonify({"output": output})
    except Exception as e:
        logger.error(f"Erro ao capturar htop: {e}")
        return jsonify({"error": str(e)})

# Rota para obter um snapshot do iotop
@app.route('/api/system/iotop')
@login_required
def api_iotop_snapshot():
    """Retorna uma captura do iotop como texto"""
    try:
        # Verificar se o usuario e admin
        if session['user'].get('role') != 'admin':
            return jsonify({"error": "Permissao negada"}), 403
            
        # Tentar executar iotop em modo batch
        try:
            output = subprocess.check_output(["iotop", "-b", "-n", "1", "-o"], 
                                           universal_newlines=True, 
                                           stderr=subprocess.PIPE)
            return jsonify({"output": output})
        except (subprocess.SubprocessError, FileNotFoundError):
            return jsonify({"error": "iotop nao esta disponivel no sistema"})
    except Exception as e:
        logger.error(f"Erro ao capturar iotop: {e}")
        return jsonify({"error": str(e)})
        
def run_dns_test(test_id, test_type):
    """Funcao para executar o teste DNS em background"""
    job = dns_test_jobs[test_id]
    
    try:
        if test_type == 'latency':
            # Executar teste de latencia
            job["status"] = "Executando teste de latencia..."
            add_test_log(test_id, "Iniciando teste de latencia por tipo de consulta")
            result_file = run_latency_test(test_id)
        elif test_type == 'hypercache':
            # Executar teste de hypercache
            job["status"] = "Executando teste de hypercache..."
            add_test_log(test_id, "Iniciando teste de eficiencia avancada do cache")
            result_file = run_hypercache_test(test_id)
        elif test_type == 'cache':
            # Executar teste de cache padrao
            job["status"] = "Executando teste de cache..."
            add_test_log(test_id, "Iniciando teste de cache")
            result_file = run_cache_test(test_id)
        elif test_type == 'all':
            # Executar todos os testes
            add_test_log(test_id, "Iniciando todos os testes")
            
            # Teste de latencia
            job["status"] = "Executando teste de latencia (1/3)..."
            job["progress"] = 10
            add_test_log(test_id, "Iniciando teste de latencia")
            run_latency_test(test_id)
            job["progress"] = 33
            
            # Teste de hypercache
            job["status"] = "Executando teste de hypercache (2/3)..."
            add_test_log(test_id, "Iniciando teste de hypercache")
            run_hypercache_test(test_id)
            job["progress"] = 66
            
            # Teste de cache padrao
            job["status"] = "Executando teste de cache (3/3)..."
            add_test_log(test_id, "Iniciando teste de cache")
            result_file = run_cache_test(test_id)
            job["progress"] = 90
        else:
            add_test_log(test_id, f"Tipo de teste desconhecido: {test_type}", "error")
            job["status"] = "Erro: tipo de teste desconhecido"
            job["completed"] = True
            return
        
        # Finalizar teste
        job["status"] = "Teste concluido"
        job["progress"] = 100
        job["completed"] = True
        job["result_file"] = result_file
        
        add_test_log(test_id, "Teste concluido com sucesso!", "success")
        
    except Exception as e:
        logger.error(f"Erro ao executar teste DNS: {e}")
        add_test_log(test_id, f"Erro ao executar teste: {str(e)}", "error")
        job["status"] = "Erro ao executar teste"
        job["progress"] = 100
        job["completed"] = True

def add_test_log(test_id, message, log_type="info"):
    """Adiciona uma entrada de log ao teste"""
    if test_id in dns_test_jobs:
        dns_test_jobs[test_id]["logs"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "type": log_type
        })

def run_latency_test(test_id):
    """Executa o teste de latencia"""
    job = dns_test_jobs[test_id]
    job["progress"] = 20
    
    # Caminho para o script de teste
    test_script = "/home/br10config/unbound/tests/latency_test.sh"
    
    # Verificar se o script existe
    if not os.path.exists(test_script):
        add_test_log(test_id, f"Erro: Script de teste nao encontrado: {test_script}", "error")
        logger.error(f"Script de teste nao encontrado: {test_script}")
        print(f"[ERRO] Script de teste nao encontrado: {test_script}")
        raise FileNotFoundError(f"Script nao encontrado: {test_script}")
    
    # Tornar o script executavel
    os.chmod(test_script, 0o755)
    
    # Executar o script
    add_test_log(test_id, "Executando teste de latencia...")
    print("[INFO] Executando teste de latencia via shell...")
    job["progress"] = 30
    
    try:
        # Executar o script diretamente via shell, fora do ambiente virtual
        command = f"cd /home/br10config/unbound/tests && bash ./latency_test.sh"
        print(f"[INFO] Executando comando: {command}")
        
        result = subprocess.run(command, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True,
                               shell=True,
                               check=True)
        
        job["progress"] = 80
        
        # Logar a saida para depuracao
        print(f"[INFO] Saida do comando: {result.stdout}")
        if result.stderr:
            print(f"[AVISO] Erro do comando: {result.stderr}")
        
        # O script deve retornar o caminho do arquivo JSON na ultima linha
        output_lines = result.stdout.strip().split('\n')
        print(f"[INFO] Linhas de saida: {len(output_lines)}")
        
        result_file = None
        # Procurar pela linha que contem um caminho para um arquivo JSON
        for line in reversed(output_lines):
            if '.json' in line:
                result_file = line.strip()
                print(f"[INFO] Arquivo JSON encontrado: {result_file}")
                break
        
        # Se nao encontrou na saida, usar a ultima linha
        if not result_file and output_lines:
            result_file = output_lines[-1]
            print(f"[INFO] Usando ultima linha como caminho do arquivo: {result_file}")
        
        # Verificar se o arquivo existe
        if result_file and os.path.exists(result_file) and result_file.endswith('.json'):
            add_test_log(test_id, f"Teste concluido, resultados salvos em: {result_file}", "success")
            print(f"[INFO] Arquivo de resultados existe: {result_file}")
            
            # Verificar o conteudo do JSON
            try:
                with open(result_file, 'r') as f:
                    json_data = json.load(f)
                    
                print(f"[INFO] Conteudo do JSON: {len(json_data)} chaves")
                
                # Se o array de resultados esta vazio, enriquece-lo com dados do log
                if "results" in json_data and len(json_data["results"]) == 0:
                    print("[INFO] Array de resultados vazio, tentando enriquecer com dados do log")
                    log_file = result_file.replace('.json', '.log')
                    
                    if os.path.exists(log_file):
                        print(f"[INFO] Processando arquivo de log: {log_file}")
                        add_test_log(test_id, "Processando detalhes do arquivo de log", "info")
                        
                        with open(log_file, 'r') as f:
                            log_content = f.read()
                        
                        # Extrair dados do log
                        results = []
                        for line in log_content.splitlines():
                            parts = line.strip().split()
                            if len(parts) >= 5 and not line.startswith('===') and not line.startswith('--'):
                                try:
                                    # Tentar identificar linhas que contem dados de consulta
                                    if parts[0] in ['A', 'AAAA', 'MX', 'TXT', 'NS', 'SOA', 'CNAME']:
                                        record_type = parts[0]
                                        domain = parts[1]
                                        # Limpar valores ms
                                        time1 = float(parts[2].replace('ms', ''))
                                        time2 = float(parts[3].replace('ms', ''))
                                        time3 = float(parts[4].replace('ms', ''))
                                        avg = (time1 + time2 + time3) / 3
                                        
                                        results.append({
                                            "record_type": record_type,
                                            "domain": domain,
                                            "time1": time1,
                                            "time2": time2,
                                            "time3": time3,
                                            "avg": round(avg, 2)
                                        })
                                except (ValueError, IndexError) as e:
                                    print(f"[AVISO] Erro ao processar linha do log: {e}")
                                    continue
                        
                        print(f"[INFO] Extraidos {len(results)} resultados do arquivo de log")
                        
                        # Atualizar e salvar o JSON com os dados extraidos
                        if results:
                            json_data["results"] = results
                            # Calcular medias por tipo de registro se nao existirem
                            if "summary" in json_data and json_data["summary"] and "overall" in json_data["summary"]:
                                for record_type in set(r["record_type"] for r in results):
                                    type_results = [r for r in results if r["record_type"] == record_type]
                                    avg_time = sum(r["avg"] for r in type_results) / len(type_results)
                                    json_data["summary"][record_type] = round(avg_time, 2)
                                    
                            # Salvar o JSON atualizado
                            with open(result_file, 'w') as f:
                                json.dump(json_data, f, indent=2)
                            
                            print(f"[INFO] JSON atualizado com {len(results)} resultados")
                            add_test_log(test_id, f"JSON enriquecido com {len(results)} resultados detalhados", "success")
                    else:
                        print(f"[AVISO] Arquivo de log nao encontrado: {log_file}")
            except Exception as e:
                print(f"[ERRO] Falha ao processar JSON: {str(e)}")
                logger.error(f"Erro ao processar JSON: {str(e)}")
                add_test_log(test_id, f"Erro ao processar resultados: {str(e)}", "warning")
            
            # Criar URL para acessar o arquivo atraves da API
            api_path = f'/api/dns_tests/results/{os.path.basename(result_file)}'
            return api_path
        else:
            # Se nao encontrou o arquivo JSON no output, buscar por padrao
            print("[INFO] Arquivo JSON nao encontrado na saida, buscando o mais recente")
            report_dir = "/var/log/br10"
            json_files = glob.glob(os.path.join(report_dir, "latency_test_*.json"))
            
            if json_files:
                # Pegar o arquivo mais recente
                json_files.sort(key=os.path.getmtime, reverse=True)
                result_file = json_files[0]
                print(f"[INFO] Encontrado arquivo mais recente: {result_file}")
                api_path = f'/api/dns_tests/results/{os.path.basename(result_file)}'
                add_test_log(test_id, f"Teste concluido, resultados salvos em: {result_file}", "success")
                
                # Verificar tambem se e necessario enriquecer o JSON
                try:
                    with open(result_file, 'r') as f:
                        json_data = json.load(f)
                    
                    if "results" in json_data and len(json_data["results"]) == 0:
                        print("[INFO] Array de resultados vazio no arquivo mais recente, tentando enriquecer")
                        log_file = result_file.replace('.json', '.log')
                        if os.path.exists(log_file):
                            # Codigo de enriquecimento similar ao anterior...
                            # (repetindo o mesmo bloco de codigo para processar o log)
                            print(f"[INFO] Processando arquivo de log: {log_file}")
                            add_test_log(test_id, "Processando detalhes do arquivo de log", "info")
                            
                            with open(log_file, 'r') as f:
                                log_content = f.read()
                            
                            # Extrair dados do log
                            results = []
                            for line in log_content.splitlines():
                                parts = line.strip().split()
                                if len(parts) >= 5 and not line.startswith('===') and not line.startswith('--'):
                                    try:
                                        # Tentar identificar linhas que contem dados de consulta
                                        if parts[0] in ['A', 'AAAA', 'MX', 'TXT', 'NS', 'SOA', 'CNAME']:
                                            record_type = parts[0]
                                            domain = parts[1]
                                            # Limpar valores ms
                                            time1 = float(parts[2].replace('ms', ''))
                                            time2 = float(parts[3].replace('ms', ''))
                                            time3 = float(parts[4].replace('ms', ''))
                                            avg = (time1 + time2 + time3) / 3
                                            
                                            results.append({
                                                "record_type": record_type,
                                                "domain": domain,
                                                "time1": time1,
                                                "time2": time2,
                                                "time3": time3,
                                                "avg": round(avg, 2)
                                            })
                                    except (ValueError, IndexError) as e:
                                        print(f"[AVISO] Erro ao processar linha do log: {e}")
                                        continue
                            
                            print(f"[INFO] Extraidos {len(results)} resultados do arquivo de log")
                            
                            # Atualizar e salvar o JSON com os dados extraidos
                            if results:
                                json_data["results"] = results
                                # Calcular medias por tipo de registro se nao existirem
                                if "summary" in json_data and json_data["summary"] and "overall" in json_data["summary"]:
                                    for record_type in set(r["record_type"] for r in results):
                                        type_results = [r for r in results if r["record_type"] == record_type]
                                        avg_time = sum(r["avg"] for r in type_results) / len(type_results)
                                        json_data["summary"][record_type] = round(avg_time, 2)
                                        
                                # Salvar o JSON atualizado
                                with open(result_file, 'w') as f:
                                    json.dump(json_data, f, indent=2)
                                
                                print(f"[INFO] JSON atualizado com {len(results)} resultados")
                                add_test_log(test_id, f"JSON enriquecido com {len(results)} resultados detalhados", "success")
                except Exception as e:
                    print(f"[ERRO] Falha ao processar JSON recente: {str(e)}")
                
                return api_path
            
            add_test_log(test_id, "Arquivo de resultados nao encontrado", "error")
            print("[ERRO] Nenhum arquivo de resultados encontrado")
            raise FileNotFoundError("Arquivo de resultados nao encontrado")
    except subprocess.CalledProcessError as e:
        print(f"[ERRO] Falha ao executar script de teste: {e}")
        print(f"[ERRO] Saida de erro: {e.stderr}")
        add_test_log(test_id, f"Erro ao executar teste: {e}", "error")
        add_test_log(test_id, f"Saida de erro: {e.stderr}", "error")
        raise RuntimeError(f"Erro ao executar teste de latencia: {e}")
    
    return None

def run_hypercache_test(test_id):
    """Executa o teste de hypercache"""
    job = dns_test_jobs[test_id]
    job["progress"] = 20
    
    # Caminho para o script de teste
    test_script = "/home/br10config/unbound/tests/hypercache_test.sh"
    
    # Verificar se o script existe
    if not os.path.exists(test_script):
        add_test_log(test_id, f"Erro: Script de teste nao encontrado: {test_script}", "error")
        logger.error(f"Script de teste nao encontrado: {test_script}")
        print(f"[ERRO] Script de teste nao encontrado: {test_script}")
        raise FileNotFoundError(f"Script nao encontrado: {test_script}")
    
    # Tornar o script executavel
    os.chmod(test_script, 0o755)
    
    # Executar o script
    add_test_log(test_id, "Executando teste de hypercache...")
    print("[INFO] Executando teste de hypercache via shell...")
    job["progress"] = 30
    
    try:
        # Executar o script diretamente via shell, fora do ambiente virtual
        command = f"cd /home/br10config/unbound/tests && bash ./hypercache_test.sh"
        print(f"[INFO] Executando comando: {command}")
        
        result = subprocess.run(command, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True,
                               shell=True,
                               check=True)
        
        job["progress"] = 80
        
        # Logar a saida para depuracao
        print(f"[INFO] Saida do comando: {result.stdout}")
        if result.stderr:
            print(f"[AVISO] Erro do comando: {result.stderr}")
        
        # O script deve retornar o caminho do arquivo JSON na ultima linha
        output_lines = result.stdout.strip().split('\n')
        print(f"[INFO] Linhas de saida: {len(output_lines)}")
        
        result_file = None
        # Procurar pela linha que contem um caminho para um arquivo JSON
        for line in reversed(output_lines):
            if '.json' in line:
                result_file = line.strip()
                print(f"[INFO] Arquivo JSON encontrado: {result_file}")
                break
        
        # Se nao encontrou na saida, usar a ultima linha
        if not result_file and output_lines:
            result_file = output_lines[-1]
            print(f"[INFO] Usando ultima linha como caminho do arquivo: {result_file}")
        
        # Verificar se o arquivo existe
        if result_file and os.path.exists(result_file) and result_file.endswith('.json'):
            add_test_log(test_id, f"Teste concluido, resultados salvos em: {result_file}", "success")
            print(f"[INFO] Arquivo de resultados existe: {result_file}")
            
            # Verificar o conteudo do JSON
            try:
                with open(result_file, 'r') as f:
                    json_data = json.load(f)
                    
                print(f"[INFO] Conteudo do JSON: {len(json_data)} chaves")
                
                # Se o array de resultados esta vazio, enriquece-lo com dados do log
                if "results" in json_data and len(json_data["results"]) == 0:
                    print("[INFO] Array de resultados vazio, tentando enriquecer com dados do log")
                    log_file = result_file.replace('.json', '.log')
                    
                    if os.path.exists(log_file):
                        print(f"[INFO] Processando arquivo de log: {log_file}")
                        add_test_log(test_id, "Processando detalhes do arquivo de log", "info")
                        
                        with open(log_file, 'r') as f:
                            log_content = f.read()
                        
                        # Extrair dados do log especificos para hypercache test
                        results = []
                        for line in log_content.splitlines():
                            # Adaptar este regex conforme os logs do hypercache
                            if 'Cache efficiency:' in line:
                                efficiency = re.search(r'Cache efficiency:\s+(\d+\.\d+)%', line)
                                if efficiency:
                                    json_data["summary"] = {"cache_efficiency": f"{efficiency.group(1)}%"}
                                    
                        # Salvar o JSON atualizado
                        with open(result_file, 'w') as f:
                            json.dump(json_data, f, indent=2)
                        
                        print(f"[INFO] JSON atualizado")
                        add_test_log(test_id, "JSON enriquecido com dados do log", "success")
            except Exception as e:
                print(f"[ERRO] Falha ao processar JSON: {str(e)}")
                logger.error(f"Erro ao processar JSON: {str(e)}")
                add_test_log(test_id, f"Erro ao processar resultados: {str(e)}", "warning")
            
            # Criar URL para acessar o arquivo atraves da API
            api_path = f'/api/dns_tests/results/{os.path.basename(result_file)}'
            return api_path
        else:
            # Se nao encontrou o arquivo JSON no output, buscar por padrao
            print("[INFO] Arquivo JSON nao encontrado na saida, buscando o mais recente")
            report_dir = "/var/log/br10"
            json_files = glob.glob(os.path.join(report_dir, "hypercache_test_*.json"))
            
            if json_files:
                # Pegar o arquivo mais recente
                json_files.sort(key=os.path.getmtime, reverse=True)
                result_file = json_files[0]
                print(f"[INFO] Encontrado arquivo mais recente: {result_file}")
                api_path = f'/api/dns_tests/results/{os.path.basename(result_file)}'
                add_test_log(test_id, f"Teste concluido, resultados salvos em: {result_file}", "success")
                return api_path
            
            add_test_log(test_id, "Arquivo de resultados nao encontrado", "error")
            print("[ERRO] Nenhum arquivo de resultados encontrado")
            raise FileNotFoundError("Arquivo de resultados nao encontrado")
    except subprocess.CalledProcessError as e:
        print(f"[ERRO] Falha ao executar script de teste: {e}")
        print(f"[ERRO] Saida de erro: {e.stderr}")
        add_test_log(test_id, f"Erro ao executar teste: {e}", "error")
        add_test_log(test_id, f"Saida de erro: {e.stderr}", "error")
        raise RuntimeError(f"Erro ao executar teste de hypercache: {e}")
    
    return None

def run_cache_test(test_id):
    """Executa o teste de cache padrao"""
    job = dns_test_jobs[test_id]
    job["progress"] = 20
    
    # Caminho para o script de teste
    test_script = "/home/br10config/unbound/tests/cache_tests.sh"
    
    # Verificar se o script existe
    if not os.path.exists(test_script):
        add_test_log(test_id, f"Erro: Script de teste nao encontrado: {test_script}", "error")
        logger.error(f"Script de teste nao encontrado: {test_script}")
        print(f"[ERRO] Script de teste nao encontrado: {test_script}")
        raise FileNotFoundError(f"Script nao encontrado: {test_script}")
    
    # Tornar o script executavel
    os.chmod(test_script, 0o755)
    
    # Executar o script
    add_test_log(test_id, "Executando teste de cache...")
    print("[INFO] Executando teste de cache via shell...")
    job["progress"] = 30
    
    try:
        # Executar o script diretamente via shell, fora do ambiente virtual
        command = f"cd /home/br10config/unbound/tests && bash ./cache_tests.sh"
        print(f"[INFO] Executando comando: {command}")
        
        result = subprocess.run(command, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True,
                               shell=True,
                               check=True)
        
        job["progress"] = 80
        
        # Logar a saida para depuracao
        print(f"[INFO] Saida do comando: {result.stdout}")
        if result.stderr:
            print(f"[AVISO] Erro do comando: {result.stderr}")
            
        # Para o teste de cache, vamos converter o arquivo de log para JSON
        report_dir = "/var/log/br10"
        log_files = glob.glob(os.path.join(report_dir, "cache_test_*.log"))
        
        if log_files:
            # Pegar o arquivo mais recente
            log_files.sort(key=os.path.getmtime, reverse=True)
            log_file = log_files[0]
            print(f"[INFO] Arquivo de log encontrado: {log_file}")
            
            # Criar um JSON com o conteudo do arquivo
            with open(log_file, 'r') as f:
                log_content = f.read()
            
            # Nome do arquivo JSON
            json_file = log_file.replace('.log', '.json')
            
            # Analisar o conteudo do log para extrair estatisticas
            hits_match = re.search(r'Total cache hits:\s+(\d+)', log_content)
            misses_match = re.search(r'Total cache misses:\s+(\d+)', log_content)
            
            hits = int(hits_match.group(1)) if hits_match else 0
            misses = int(misses_match.group(1)) if misses_match else 0
            total = hits + misses
            ratio = (hits / total * 100) if total > 0 else 0
            
            # Criar JSON estruturado
            data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "test_type": "cache",
                "content": log_content,
                "summary": {
                    "total_queries": total,
                    "cache_hits": hits,
                    "cache_misses": misses,
                    "hit_ratio": f"{ratio:.2f}%"
                }
            }
            
            # Salvar JSON
            with open(json_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"[INFO] JSON criado: {json_file}")
            add_test_log(test_id, f"Teste concluido, resultados salvos em: {json_file}", "success")
            
            # Criar URL para acessar o arquivo atraves da API
            api_path = f'/api/dns_tests/results/{os.path.basename(json_file)}'
            return api_path
        else:
            # Se nao encontrou logs especificos, tentar encontrar resultados JSON diretos
            json_files = glob.glob(os.path.join(report_dir, "cache_test_*.json"))
            
            if json_files:
                # Pegar o arquivo mais recente
                json_files.sort(key=os.path.getmtime, reverse=True)
                result_file = json_files[0]
                print(f"[INFO] Encontrado arquivo JSON mais recente: {result_file}")
                api_path = f'/api/dns_tests/results/{os.path.basename(result_file)}'
                add_test_log(test_id, f"Teste concluido, resultados salvos em: {result_file}", "success")
                return api_path
            
            add_test_log(test_id, "Arquivo de resultados nao encontrado", "error")
            print("[ERRO] Nenhum arquivo de resultados encontrado")
            raise FileNotFoundError("Arquivo de resultados nao encontrado")
    except subprocess.CalledProcessError as e:
        print(f"[ERRO] Falha ao executar script de teste: {e}")
        print(f"[ERRO] Saida de erro: {e.stderr}")
        add_test_log(test_id, f"Erro ao executar teste: {e}", "error")
        add_test_log(test_id, f"Saida de erro: {e.stderr}", "error")
        raise RuntimeError(f"Erro ao executar teste de cache: {e}")
    
    return None
                
# Funcoes utilitarias para analise de dados
def load_blocked_domains():
    """Carrega a lista de dominios bloqueados"""
    try:
        if not os.path.exists(BLOCKED_DOMAINS_PATH):
            return []

        with open(BLOCKED_DOMAINS_PATH, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except Exception as e:
        logger.error(f"Erro ao carregar dominios bloqueados: {e}")
        return []

def load_zone_file():
    """Carrega e analisa o arquivo de zona RPZ do Unbound"""
    zone_data = {
        "total_domains": 0,
        "last_modified": None,
        "domains_sample": [],
        "zone_file_size": 0  # Adicionado para armazenar o tamanho do arquivo
    }

    try:
        if not os.path.exists(UNBOUND_ZONE_FILE):
            return zone_data

        # Obter informacoes do arquivo
        file_stat = os.stat(UNBOUND_ZONE_FILE)
        zone_data["last_modified"] = datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        zone_data["zone_file_size"] = file_stat.st_size  # Adicionar tamanho do arquivo em bytes

        # Analisar o arquivo de zona
        domain_count = 0
        sample_domains = []

        with open(UNBOUND_ZONE_FILE, 'r') as f:
            for line in f:
                if 'IN CNAME' in line and not line.startswith(';'):
                    domain_count += 1
                    # Extrair o dominio da linha
                    match = re.match(r'^([^\s]+)', line.strip())
                    if match and len(sample_domains) < 20:  # Salvar ate 20 exemplos
                        domain = match.group(1)
                        if domain.endswith('.'):
                            domain = domain[:-1]
                        sample_domains.append(domain)

        zone_data["total_domains"] = domain_count
        zone_data["domains_sample"] = sample_domains
        
        return zone_data
    except Exception as e:
        logger.error(f"Erro ao carregar arquivo de zona: {e}")
        return zone_data

def load_history_data(limit=30):
    """Carrega os dados de historico de atualizacoes"""
    try:
        history_files = []
        if os.path.exists(HISTORY_DIR):
            for filename in os.listdir(HISTORY_DIR):
                if filename.startswith("blocklist_") and filename.endswith(".json"):
                    filepath = os.path.join(HISTORY_DIR, filename)
                    file_time = os.path.getmtime(filepath)
                    history_files.append((filepath, file_time))
        
        # Ordenar por data (mais recente primeiro)
        history_files.sort(key=lambda x: x[1], reverse=True)
        
        # Carregar dados dos arquivos de historico
        history_data = []
        for filepath, _ in history_files[:limit]:
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    # Converter timestamp para formato legivel
                    if "timestamp" in data:
                        try:
                            dt = datetime.fromisoformat(data["timestamp"])
                            data["formatted_time"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            data["formatted_time"] = data["timestamp"]
                    history_data.append(data)
            except Exception as e:
                logger.error(f"Erro ao processar arquivo de historico {filepath}: {e}")
                continue
        
        return history_data
    except Exception as e:
        logger.error(f"Erro ao carregar dados de historico: {e}")
        return []

def get_unbound_stats():
    """Obtem estatisticas do servidor Unbound"""
    try:
        stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "queries": 0,
            "uptime": "Desconhecido",
            "cache_hit_ratio": "0%",
            "response_times": {}
        }
        
        # Verificar se o unbound-control esta disponivel
        unbound_control = "/usr/sbin/unbound-control"
        if not os.path.exists(unbound_control):
            unbound_control = "/usr/bin/unbound-control"
            if not os.path.exists(unbound_control):
                logger.warning("unbound-control nao encontrado")
                return stats
        
        # Executar unbound-control stats
        import subprocess
        try:
            output = subprocess.check_output([unbound_control, "stats"], universal_newlines=True)
            
            # Analisar a saida
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
            
            # Calcular uptime
            uptime_output = subprocess.check_output([unbound_control, "status"], universal_newlines=True)
            for line in uptime_output.splitlines():
                if "uptime:" in line:
                    stats["uptime"] = line.split("uptime:")[1].strip()
                    break
            
            # Calcular taxa de hit de cache
            if stats["queries"] > 0:
                hit_ratio = (stats["cache_hits"] / stats["queries"]) * 100
                stats["cache_hit_ratio"] = f"{hit_ratio:.2f}%"
        
        except subprocess.SubprocessError as e:
            logger.error(f"Erro ao executar unbound-control: {e}")
        
        return stats
    except Exception as e:
        logger.error(f"Erro ao obter estatisticas do Unbound: {e}")
        return stats
        
def load_system_logs(log_type='all', log_level='all', search=''):
    """Carrega logs do sistema baseado em filtros"""
    logs = []
    
    try:
        # Base dir para os logs organizados por servico
        base_log_dir = '/opt/br10api/logs'
        
        # Definir diretorios de log com base no tipo
        log_dirs = []
        
        if log_type == 'all' or log_type == 'dashboard':
            log_dirs.append((os.path.join(base_log_dir, 'dashboard'), 'dashboard'))
            log_dirs.append((os.path.join(LOG_DIR), 'dashboard'))  # Diretorio original do dashboard
            
        if log_type == 'all' or log_type == 'unbound':
            log_dirs.append((os.path.join(base_log_dir, 'unbound'), 'unbound'))
            
            # Usar journalctl para unbound como backup
            try:
                cmd = ["journalctl", "-u", "unbound", "--no-pager", "-n", "1000"]
                output = subprocess.check_output(cmd, universal_newlines=True)
                
                temp_log_file = os.path.join(LOG_DIR, "unbound_journalctl.txt")
                with open(temp_log_file, "w") as f:
                    f.write(output)
                
                log_dirs.append((temp_log_file, 'unbound'))
            except Exception as e:
                logger.error(f"Erro ao obter logs do Unbound via journalctl: {e}")
        
        if log_type == 'all' or log_type == 'error':
            log_dirs.append((os.path.join(base_log_dir, 'error'), 'error'))
            
        if log_type == 'all' or log_type == 'api':
            log_dirs.append((os.path.join(base_log_dir, 'api'), 'api'))
            
        if log_type == 'all' or log_type == 'security':
            log_dirs.append((os.path.join(base_log_dir, 'security'), 'security'))
            
        if log_type == 'all' or log_type == 'system':
            # Usar journalctl para logs do sistema
            try:
                cmd = ["journalctl", "--no-pager", "-n", "500"]
                output = subprocess.check_output(cmd, universal_newlines=True)
                
                temp_log_file = os.path.join(LOG_DIR, "system_journalctl.txt")
                with open(temp_log_file, "w") as f:
                    f.write(output)
                
                log_dirs.append((temp_log_file, 'system'))
            except Exception as e:
                logger.error(f"Erro ao obter logs do sistema via journalctl: {e}")
        
        # Processar cada diretorio de log
        for log_dir, file_type in log_dirs:
            if os.path.isfile(log_dir):
                # Se for um arquivo unico
                process_log_file(log_dir, file_type, log_level, search, logs)
            elif os.path.isdir(log_dir):
                # Se for um diretorio, processar todos os arquivos
                log_files = sorted(
                    [os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith('.log')],
                    key=os.path.getmtime,
                    reverse=True
                )
                
                # Limitar a 5 arquivos mais recentes por tipo
                for log_file in log_files[:5]:
                    process_log_file(log_file, file_type, log_level, search, logs)
        
        # Ordenar logs por timestamp (mais recente primeiro)
        logs.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return logs
    except Exception as e:
        logger.error(f"Erro ao carregar logs: {e}")
        return []

def process_log_file(log_file, file_type, log_level, search, logs):
    """Processa um arquivo de log e adiciona entradas à lista de logs"""
    if not os.path.exists(log_file):
        return
    
    # Limitando a quantidade de linhas para nao sobrecarregar
    cmd = ["tail", "-n", "1000", log_file]
    try:
        output = subprocess.check_output(cmd, universal_newlines=True)
        
        for line in output.splitlines():
            # Verificar o nivel do log
            level = "INFO"
            if "ERROR" in line or "error" in line:
                level = "ERROR"
            elif "WARN" in line or "WARNING" in line or "warning" in line:
                level = "WARNING"
            elif "DEBUG" in line or "debug" in line:
                level = "DEBUG"
                
            # Aplicar filtro de nivel
            if log_level != 'all' and log_level.upper() != level:
                continue
                
            # Aplicar filtro de busca
            if search and search.lower() not in line.lower():
                continue
                
            # Extrair timestamp
            timestamp = "N/A"
            timestamp_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', line)
            if timestamp_match:
                timestamp = timestamp_match.group(0)
            else:
                # Formato alternativo (ex: Mar 18 10:30:45)
                alt_match = re.search(r'[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}', line)
                if alt_match:
                    timestamp = alt_match.group(0)
            
            if timestamp == "N/A":
                # Usar a hora do sistema para logs sem timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
            # Adicionar log à lista
            logs.append({
                "timestamp": timestamp,
                "type": file_type,
                "level": level,
                "message": line
            })
    except subprocess.SubprocessError as e:
        logger.error(f"Erro ao ler arquivo de log {log_file}: {e}")
        
        # Ordenar logs por timestamp (mais recente primeiro)
        logs.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return logs
    except Exception as e:
        logger.error(f"Erro ao carregar logs: {e}")
        return []
        
def get_recent_access_attempts(limit=100):
    """Obtem tentativas recentes de acesso a dominios bloqueados (a partir dos logs)"""
    try:
        # Verificar se o arquivo de log do Unbound existe
        unbound_log = "/var/log/unbound.log"
        if not os.path.exists(unbound_log):
            # Tentar alternativa
            unbound_log = "/var/log/syslog"
            if not os.path.exists(unbound_log):
                logger.warning("Arquivo de log do Unbound nao encontrado")
                return []
        
        # Extrair tentativas de acesso bloqueadas
        import subprocess
        try:
            # Procurar por bloqueios RPZ
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
            
            # Ordenar por tempo (mais recente primeiro)
            return sorted(attempts, key=lambda x: x["time"], reverse=True)
            
        except subprocess.SubprocessError as e:
            logger.warning(f"Erro ao extrair tentativas de acesso dos logs: {e}")
            return []
            
    except Exception as e:
        logger.error(f"Erro ao obter tentativas de acesso: {e}")
        return []

@app.route('/logs')
@login_required
def logs_page():
    """Pagina de visualizacao de logs do sistema"""
    # Verificar se e admin (opcional, se quiser restringir)
    if session['user'].get('role') != 'admin':
        flash('Permissao negada', 'danger')
        return redirect(url_for('dashboard'))
        
    return render_template('logs.html')
    
@app.route('/api/logs')
@login_required
def api_logs():
    """API para listar logs do sistema"""
    try:
        # Obter parametros
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 100))
        log_type = request.args.get('type', 'all')
        log_level = request.args.get('level', 'all')
        search = request.args.get('search', '')
        
        # Carregar logs
        logs = load_system_logs(log_type, log_level, search)
        
        # Paginacao
        total_logs = len(logs)
        total_pages = (total_logs + per_page - 1) // per_page
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        return jsonify({
            "logs": logs[start_idx:end_idx],
            "total": total_logs,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        })
    except Exception as e:
        logger.error(f"Erro ao listar logs: {e}")
        return jsonify({"error": str(e)})
        
@app.route('/users')
@login_required
def users_page():
    """Pagina de gerenciamento de usuarios"""
    # Verificar se e admin
    if session['user'].get('role') != 'admin':
        flash('Permissao negada', 'danger')
        return redirect(url_for('dashboard'))
        
    return render_template('users.html')
    
# Rotas da aplicacao
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Pagina de login"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = authenticate_user(username, password)
        if user:
            session['user'] = user
            logger.info(f"Usuario {username} fez login com sucesso")
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario ou senha invalidos', 'danger')
            logger.warning(f"Tentativa de login falhou para usuario: {username}")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Rota para logout"""
    if 'user' in session:
        username = session['user']['username']
        session.pop('user', None)
        logger.info(f"Usuario {username} fez logout")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    """Pagina principal do dashboard"""
    return render_template('dashboard.html')

@app.route('/domains')
@login_required
def domains():
    """Pagina de listagem de dominios bloqueados"""
    return render_template('domains.html')

@app.route('/attempts')
@login_required
def attempts():
    """Pagina de tentativas de acesso a dominios bloqueados"""
    return render_template('attempts.html')

@app.route('/history')
@login_required
def history():
    """Pagina de historico de atualizacoes"""
    return render_template('history.html')

# API endpoints para fornecer dados ao frontend
@app.route('/api/stats')
@login_required
def api_stats():
    """API para estatisticas gerais"""
    try:
        blocked_domains = load_blocked_domains()
        zone_data = load_zone_file()
        unbound_stats = get_unbound_stats()
        
        return jsonify({
            "blocked_domains_count": len(blocked_domains),
            "zone_file": zone_data,
            "unbound": unbound_stats,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        logger.error(f"Erro ao obter estatisticas: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/domains')
@login_required
def api_domains():
    """API para listar dominios bloqueados"""
    try:
        blocked_domains = load_blocked_domains()
        
        # Paginacao
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
        logger.error(f"Erro ao listar dominios: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/history')
@login_required
def api_history():
    """API para historico de atualizacoes"""
    try:
        limit = int(request.args.get('limit', 30))
        history_data = load_history_data(limit)
        
        return jsonify({
            "history": history_data,
            "count": len(history_data)
        })
    except Exception as e:
        logger.error(f"Erro ao obter historico: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/attempts')
@login_required
def api_attempts():
    """API para tentativas de acesso a dominios bloqueados"""
    try:
        limit = int(request.args.get('limit', 100))
        attempts = get_recent_access_attempts(limit)
        
        return jsonify({
            "attempts": attempts,
            "count": len(attempts)
        })
    except Exception as e:
        logger.error(f"Erro ao obter tentativas de acesso: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/users', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_users():
    """API para gerenciar usuarios"""
    # Verificar se e admin
    if session['user'].get('role') != 'admin':
        return jsonify({"error": "Permissao negada"}), 403
    
    if request.method == 'GET':
        # Listar usuarios
        users = get_users()
        # Remover senhas
        for user in users:
            user.pop('password', None)
        return jsonify({"users": users})
    
    elif request.method == 'POST':
        # Adicionar ou atualizar usuario
        data = request.json
        if not data or 'username' not in data:
            return jsonify({"error": "Dados incompletos"}), 400
        
        username = data['username']
        password = data.get('password')
        role = data.get('role', 'user')
        
        users = get_users()
        
        # Verificar se ja existe
        user_exists = False
        for user in users:
            if user['username'] == username:
                # Atualizar role sempre
                user['role'] = role
                # Atualizar senha apenas se fornecida
                if password:
                    user['password'] = hashlib.sha256(password.encode()).hexdigest()
                user_exists = True
                break
        
        # Adicionar novo usuario (senha obrigatoria)
        if not user_exists:
            if not password:
                return jsonify({"error": "Senha e obrigatoria para novos usuarios"}), 400
                
            new_user = {
                "username": username,
                "password": hashlib.sha256(password.encode()).hexdigest(),
                "role": role
            }
            users.append(new_user)
        
        # Salvar alteracoes
        with open(USERS_FILE, 'w') as f:
            json.dump({"users": users}, f, indent=2)
        
        logger.info(f"Usuario {username} {'atualizado' if user_exists else 'adicionado'}")
        return jsonify({"success": True, "message": f"Usuario {username} {'atualizado' if user_exists else 'adicionado'} com sucesso"})
    
    elif request.method == 'DELETE':
        # Remover usuario
        data = request.json
        if not data or 'username' not in data:
            return jsonify({"error": "Dados incompletos"}), 400
        
        username = data['username']
        
        # Nao permitir remover o proprio usuario
        if username == session['user']['username']:
            return jsonify({"error": "Nao e possivel remover o proprio usuario"}), 400
        
        users = get_users()
        users = [user for user in users if user['username'] != username]
        
        # Salvar alteracoes
        with open(USERS_FILE, 'w') as f:
            json.dump({"users": users}, f, indent=2)
        
        logger.info(f"Usuario {username} removido")
        return jsonify({"success": True, "message": f"Usuario {username} removido com sucesso"})
  

@app.route('/clients')
@login_required
def clients_page():
    return render_template('clients.html')

@app.route('/api/clients', methods=['GET'])
@login_required
def get_clients():
    # Parametros da requisicao
    limit = request.args.get('limit', 100, type=int)
    sort = request.args.get('sort', 'queries')
    search = request.args.get('search', '')
    
    # Parametro adicional para forcar refresh do cache
    force_refresh = request.args.get('refresh', 'false') == 'true'
    
    # Obter dados do cache ou dos logs
    clients_data = get_clients_data_with_cache(limit, sort, search, force_refresh)
    
    return jsonify(clients_data)

# Funcao para obter dados dos clientes com cache no Redis
def get_clients_data_with_cache(limit=100, sort='queries', search='', force_refresh=False):
    """API para obter dados dos clientes DNS com cache"""
    # Chave unica para o cache, incluindo parametros de ordenacao
    cache_key = f"dns_clients_data:{sort}"
    
    # Se nao for uma busca especifica e o cache existe, use-o
    if not search and not force_refresh:
        # Verificar se ha dados em cache
        cached_data = redis_client.get(cache_key)
        if cached_data:
            # Converter de JSON para dicionario
            data = json.loads(cached_data)
            
            # Limitar resultados conforme solicitado
            data['clients'] = data['clients'][:limit]
            return data
    
    # Se chegamos aqui, precisamos processar os dados
    result = process_unbound_stats(limit, sort, search)
    
    # Se nao for uma busca especifica, armazene no cache
    if not search:
        # Armazenar dados no Redis como JSON
        redis_client.setex(
            cache_key, 
            CACHE_TTL,  # TTL de 5 minutos
            json.dumps(result)
        )
    
    return result

def process_unbound_stats(limit=100, sort='queries', search=''):
    """Coleta estatísticas do Unbound via unbound-control stats e logs reais"""
    
    # Tentar obter estatísticas do Redis primeiro
    cache_key = "dns_clients_stats"
    cached_data = redis_client.get(cache_key)
    
    clients = {}
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not cached_data or search:  # Se não tem cache ou precisa filtrar, buscar dados frescos
        try:
            # Usar unbound-control stats para estatísticas gerais
            stats_output = subprocess.check_output(["unbound-control", "stats"], 
                                                 universal_newlines=True)
            
            # Extrair estatísticas gerais
            total_queries = 0
            total_cachehits = 0
            total_cachemiss = 0
            
            for line in stats_output.splitlines():
                if line.startswith("total.num.queries="):
                    total_queries = int(line.split("=")[1])
                elif line.startswith("total.num.cachehits="):
                    total_cachehits = int(line.split("=")[1])
                elif line.startswith("total.num.cachemiss="):
                    total_cachemiss = int(line.split("=")[1])
            
            # Adicionar cliente agregado com valores totais
            clients["all"] = {
                'ip': 'Agregado',
                'hostname': 'Todos os clientes',
                'total_queries': total_queries,
                'cache_hits': total_cachehits,
                'cache_misses': total_cachemiss,
                'last_query_time': current_time
            }
            
            # Obter todos os logs recentes do Unbound para extrair IPs de clientes reais
            log_files = [
                "/var/log/unbound/unbound.log",  # Principal arquivo de log do Unbound
                "/var/log/syslog"                # Arquivo de sistema que pode conter logs do Unbound
            ]
            
            # Padrão para extrair consultas de clientes específicos
            query_pattern = re.compile(r'unbound\[[0-9:]+\] query: (\d+\.\d+\.\d+\.\d+) ([^ ]+)')
            reply_pattern = re.compile(r'unbound\[[0-9:]+\] reply: (\d+\.\d+\.\d+\.\d+) ([^ ]+)(.*)(NOERROR|NXDOMAIN|SERVFAIL)')
            
            # Tenta obter logs via journalctl
            try:
                log_output = subprocess.check_output(
                    ["journalctl", "-u", "unbound", "--since", "1 hour ago", "--no-pager"],
                    universal_newlines=True
                )
                
                # Processar logs para extrair IPs de clientes
                client_stats = {}
                
                for line in log_output.splitlines():
                    # Procurar consultas dos clientes
                    query_match = query_pattern.search(line)
                    if query_match:
                        client_ip = query_match.group(1)
                        
                        # Filtrar por busca se especificado
                        if search and search not in client_ip:
                            continue
                            
                        # Inicializar cliente se não existir
                        if client_ip not in client_stats:
                            client_stats[client_ip] = {
                                'queries': 0,
                                'hits': 0,
                                'misses': 0,
                                'last_seen': current_time
                            }
                        
                        # Incrementar contador de consultas
                        client_stats[client_ip]['queries'] += 1
                    
                    # Procurar respostas para os clientes (para identificar cache hits)
                    reply_match = reply_pattern.search(line)
                    if reply_match:
                        client_ip = reply_match.group(1)
                        
                        # Filtrar por busca
                        if search and search not in client_ip:
                            continue
                            
                        # Verificar se já existe o cliente
                        if client_ip not in client_stats:
                            continue
                        
                        # Verificar se é um cache hit (tempo zero)
                        if "0.000000" in line:
                            client_stats[client_ip]['hits'] += 1
                        else:
                            client_stats[client_ip]['misses'] += 1
                
                # Converter estatísticas por cliente para o formato esperado
                for client_ip, stats in client_stats.items():
                    clients[client_ip] = {
                        'ip': client_ip,
                        'hostname': '',  # Sem hostname por padrão
                        'total_queries': stats['queries'],
                        'cache_hits': stats['hits'],
                        'cache_misses': stats['misses'],
                        'last_query_time': stats['last_seen']
                    }
            except Exception as e:
                print(f"[DEBUG] Erro ao processar logs: {str(e)}")
            
            # Se não foram encontrados clientes nos logs, verificar também os arquivos de log diretos
            if len(clients) <= 1:  # Se só temos o cliente agregado
                for log_file in log_files:
                    if os.path.exists(log_file):
                        try:
                            # Obter as últimas 1000 linhas
                            log_content = subprocess.check_output(
                                ["tail", "-n", "1000", log_file],
                                universal_newlines=True
                            )
                            
                            # Processar da mesma forma que acima
                            client_stats = {}
                            
                            for line in log_content.splitlines():
                                # Procurar consultas dos clientes
                                query_match = query_pattern.search(line)
                                if query_match:
                                    client_ip = query_match.group(1)
                                    
                                    # Filtrar por busca
                                    if search and search not in client_ip:
                                        continue
                                        
                                    # Inicializar cliente se não existir
                                    if client_ip not in client_stats:
                                        client_stats[client_ip] = {
                                            'queries': 0,
                                            'hits': 0,
                                            'misses': 0,
                                            'last_seen': current_time
                                        }
                                    
                                    # Incrementar contador de consultas
                                    client_stats[client_ip]['queries'] += 1
                                
                                # Procurar respostas para os clientes
                                reply_match = reply_pattern.search(line)
                                if reply_match:
                                    client_ip = reply_match.group(1)
                                    
                                    # Filtrar por busca
                                    if search and search not in client_ip:
                                        continue
                                        
                                    # Verificar se já existe o cliente
                                    if client_ip not in client_stats:
                                        continue
                                    
                                    # Verificar se é um cache hit (tempo zero)
                                    if "0.000000" in line:
                                        client_stats[client_ip]['hits'] += 1
                                    else:
                                        client_stats[client_ip]['misses'] += 1
                            
                            # Converter estatísticas por cliente para o formato esperado
                            for client_ip, stats in client_stats.items():
                                # Só adicionar se ainda não existe
                                if client_ip not in clients:
                                    clients[client_ip] = {
                                        'ip': client_ip,
                                        'hostname': '',  # Sem hostname por padrão
                                        'total_queries': stats['queries'],
                                        'cache_hits': stats['hits'],
                                        'cache_misses': stats['misses'],
                                        'last_query_time': stats['last_seen']
                                    }
                        except Exception as e:
                            print(f"[DEBUG] Erro ao processar arquivo de log {log_file}: {str(e)}")
            
            # Armazenar dados no Redis para uso futuro
            if not search:  # Não armazenar resultados de busca no cache
                redis_client.setex(cache_key, CACHE_TTL, json.dumps(clients))
                redis_client.setex("dns_clients_base", 3600, json.dumps(clients))
                
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas via unbound-control: {e}")
            
            # Tentar usar cache como fallback
            if cached_data:
                clients = json.loads(cached_data)
    else:
        # Usar dados do cache
        clients = json.loads(cached_data)
        
        # Aplicar filtro de busca se necessário
        if search:
            clients = {ip: data for ip, data in clients.items() if search in ip}
    
    # Converter para lista
    clients_list = list(clients.values())
    
    # Ordenar a lista conforme solicitado
    if sort == 'queries':
        clients_list.sort(key=lambda x: x['total_queries'], reverse=True)
    elif sort == 'hits':
        clients_list.sort(key=lambda x: x['cache_hits'], reverse=True)
    elif sort == 'misses':
        clients_list.sort(key=lambda x: x['cache_misses'], reverse=True)
    elif sort == 'ratio':
        clients_list.sort(key=lambda x: (x['cache_hits'] / max(x['total_queries'], 1)), reverse=True)
    
    # Limitar resultados
    if limit > 0:
        limited_list = clients_list[:limit]
    else:
        limited_list = clients_list
    
    # Calcular totais
    total_clients = len(clients) - (1 if 'all' in clients else 0)  # Não contar o agregado
    total_queries = sum(client['total_queries'] for client in clients.values())
    
    result = {
        'clients': limited_list,
        'total_clients': total_clients,
        'total_queries': total_queries
    }

    return result
# Adicione um endpoint para limpar o cache, caso necessario
@app.route('/api/clients/clear-cache', methods=['POST'])
@login_required
def clear_clients_cache():
    try:
        # Limpar todas as chaves relacionadas a clientes
        keys = redis_client.keys("dns_clients_*")
        if keys:
            redis_client.delete(*keys)
        return jsonify({"status": "success", "message": "Cache limpo com sucesso"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erro ao limpar cache: {str(e)}"})

@app.route('/teste_avancado')
@login_required
def teste_avancado_page():
    """Pagina de testes avancados de DNS"""
    return render_template('teste_avancado.html')

@app.route('/api/teste_avancado/interfaces', methods=['GET'])
@login_required
def get_network_interfaces():
    """API para obter interfaces de rede disponiveis"""
    try:
        interfaces = netifaces.interfaces()
        # Filtrar apenas interfaces reais (excluir lo, docker, etc)
        filtered_interfaces = [iface for iface in interfaces if not (
            iface.startswith('lo') or 
            iface.startswith('docker') or 
            iface.startswith('veth') or
            iface.startswith('br-')
        )]
        
        return jsonify({"interfaces": filtered_interfaces})
    except Exception as e:
        logger.error(f"Erro ao obter interfaces de rede: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/teste_avancado/start', methods=['POST'])
@login_required
def start_teste_avancado():
    """API para iniciar um teste avancado"""
    try:
        data = request.json
        test_type = data.get('test_type')
        params = data.get('params', {})
        
        if not test_type:
            return jsonify({"error": "Tipo de teste nao especificado"})
        
        # Gerar ID unico para o teste
        test_id = str(uuid.uuid4())
        
        # Inicializar estado do teste
        teste_avancado_jobs[test_id] = {
            "status": "Inicializando...",
            "progress": 0,
            "log": [],
            "completed": False,
            "results": {},
            "test_type": test_type,
            "params": params,
            "start_time": datetime.now().isoformat()
        }
        
        # Iniciar o teste em uma thread separada
        thread = threading.Thread(target=run_teste_avancado, args=(test_id, test_type, params))
        thread.daemon = True
        thread.start()
        
        return jsonify({"test_id": test_id})
    except Exception as e:
        logger.error(f"Erro ao iniciar teste avancado: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/teste_avancado/status/<test_id>', methods=['GET'])
@login_required
def check_teste_avancado_status(test_id):
    """API para verificar o status de um teste avancado"""
    try:
        if test_id not in teste_avancado_jobs:
            return jsonify({"error": "ID de teste invalido"})
        
        job = teste_avancado_jobs[test_id]
        
        # Pegar logs que ainda nao foram enviados
        job_log = job["log"]
        last_log_index = int(request.args.get('last_log', 0))
        log_updates = job_log[last_log_index:] if last_log_index < len(job_log) else []
        
        return jsonify({
            "status": job["status"],
            "progress": job["progress"],
            "log_updates": log_updates,
            "completed": job["completed"],
            "results": job["results"] if job["completed"] else {}
        })
    except Exception as e:
        logger.error(f"Erro ao verificar status do teste: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/teste_avancado/report', methods=['POST'])
@login_required
def generate_teste_avancado_report():
    """API para gerar relatorio de teste avancado"""
    try:
        data = request.json
        results = data.get('results', {})
        test_type = data.get('test_type', 'unknown')
        
        if not results:
            return jsonify({"error": "Resultados nao fornecidos"})
        
        # Gerar o relatorio
        report_path = generate_report(results, test_type)
        
        # Criar URL para download
        report_url = f"/api/teste_avancado/download/{os.path.basename(report_path)}"
        
        return jsonify({"report_url": report_url})
    except Exception as e:
        logger.error(f"Erro ao gerar relatorio: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/stats/cache-by-ip')
@login_required
def api_cache_by_ip():
    """API para estatisticas de cache por tipo de IP"""
    try:
        # Obter dados dos clientes
        cached_data = redis_client.get("dns_clients_base")
        
        # Inicializar contadores
        ipv4_hits = 0
        ipv4_misses = 0
        ipv6_hits = 0
        ipv6_misses = 0
        top_clients = []
        
        if cached_data:
            clients = json.loads(cached_data)
            
            # Salvar dado agregado antes de processamento
            aggregated_data = None
            if "all" in clients:
                aggregated_data = clients["all"]
                del clients["all"]  # Remover temporariamente para processar os individuais
                
            # Processar clientes individuais
            for client_ip, data in clients.items():
                hits = data.get("cache_hits", 0)
                misses = data.get("cache_misses", 0)
                
                # Determinar tipo de IP (IPv6 contem ':')
                if ':' in client_ip:
                    ipv6_hits += hits
                    ipv6_misses += misses
                else:
                    ipv4_hits += hits
                    ipv4_misses += misses
            
            # Se nao temos dados individuais suficientes, mas temos dado agregado
            if (ipv4_hits + ipv4_misses + ipv6_hits + ipv6_misses < 10) and aggregated_data:
                total_hits = aggregated_data.get("cache_hits", 0)
                total_misses = aggregated_data.get("cache_misses", 0)
                
                # Distribuir os hits/misses: 80% IPv4, 20% IPv6 (proporcao tipica)
                ipv4_hits = int(total_hits * 0.8)
                ipv4_misses = int(total_misses * 0.8)
                ipv6_hits = total_hits - ipv4_hits
                ipv6_misses = total_misses - ipv4_misses
                
                # Adicionar clientes simulados para exibicao na lista
                clients["192.168.1.1"] = {
                    "ip": "192.168.1.1",
                    "hostname": "IPv4 Clients (estimado)",
                    "total_queries": ipv4_hits + ipv4_misses,
                    "cache_hits": ipv4_hits,
                    "cache_misses": ipv4_misses
                }
                
                clients["::1"] = {
                    "ip": "::1",
                    "hostname": "IPv6 Clients (estimado)",
                    "total_queries": ipv6_hits + ipv6_misses,
                    "cache_hits": ipv6_hits,
                    "cache_misses": ipv6_misses
                }
            
            # Preparar lista de top clientes
            client_list = []
            for client_ip, data in clients.items():
                total_queries = data.get("total_queries", 0)
                if total_queries > 0:
                    client_list.append({
                        "ip": client_ip,
                        "hostname": data.get("hostname", "Unknown"),
                        "total_queries": total_queries,
                        "cache_hits": data.get("cache_hits", 0),
                        "cache_misses": data.get("cache_misses", 0)
                    })
            
            # Ordenar por total de consultas (maior para menor)
            client_list.sort(key=lambda x: x["total_queries"], reverse=True)
            
            # Pegar os top 10 clientes
            top_clients = client_list[:10]
        
        # Calcular percentuais de hit
        total_ipv4 = ipv4_hits + ipv4_misses
        total_ipv6 = ipv6_hits + ipv6_misses
        
        ipv4_hit_percent = round((ipv4_hits / total_ipv4) * 100) if total_ipv4 > 0 else 0
        ipv6_hit_percent = round((ipv6_hits / total_ipv6) * 100) if total_ipv6 > 0 else 0
        
        return jsonify({
            "ipv4_hits": ipv4_hits,
            "ipv4_misses": ipv4_misses,
            "ipv4_total": total_ipv4,
            "ipv4_hit_percent": ipv4_hit_percent,
            
            "ipv6_hits": ipv6_hits,
            "ipv6_misses": ipv6_misses,
            "ipv6_total": total_ipv6,
            "ipv6_hit_percent": ipv6_hit_percent,
            
            "top_clients": top_clients
        })
    except Exception as e:
        logger.error(f"Erro ao obter estatisticas de cache por IP: {e}")
        return jsonify({"error": str(e)})
        
@app.route('/api/teste_avancado/download/<filename>', methods=['GET'])
@login_required
def download_teste_avancado_report(filename):
    """API para baixar um relatorio de teste avancado"""
    try:
        reports_dir = os.path.join(BASE_DIR, "reports")
        report_path = os.path.join(reports_dir, filename)
        
        if not os.path.exists(report_path):
            return jsonify({"error": "Relatorio nao encontrado"}), 404
        
        # Enviar o arquivo como anexo para download
        return send_file(
            report_path,
            as_attachment=True,
            attachment_filename=f"relatorio_dns_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mimetype="text/plain"
        )
    except Exception as e:
        logger.error(f"Erro ao baixar relatorio: {e}")
        return jsonify({"error": str(e)}), 500

def run_teste_avancado(test_id, test_type, params):
    """Executa um teste avançado em background"""
    job = teste_avancado_jobs[test_id]
    
    try:
        # Adicionar log de início
        add_test_log(test_id, f"Iniciando teste {test_type}...", "info")
        
        # Caminho para o script de teste
        test_script = "/home/br10config/unbound/tests/teste_avancado.sh"
        
        # Verificar se o script existe
        if not os.path.exists(test_script):
            add_test_log(test_id, f"Erro: Script de teste não encontrado: {test_script}", "error")
            logger.error(f"Script de teste não encontrado: {test_script}")
            print(f"[ERRO] Script de teste não encontrado: {test_script}")
            raise FileNotFoundError(f"Script não encontrado: {test_script}")
        
        # Tornar o script executável
        os.chmod(test_script, 0o755)
        
        # Preparar argumentos para o script
        args = [test_type]
        
        # Adicionar parâmetros específicos com base no tipo de teste
        if test_type == 'stress' or test_type == 'all':
            args.append(str(params.get('numQueries', 1000)))
            args.append(str(params.get('numParallel', 10)))
        
        if test_type == 'leak' or test_type == 'all':
            args.append(params.get('interface', 'auto'))
            args.append(str(params.get('captureTime', 10)))
        
        if test_type == 'comparative' or test_type == 'all':
            dns_servers = params.get('dnsServers', [])
            if isinstance(dns_servers, list):
                args.append(','.join(dns_servers))
            else:
                args.append(dns_servers)
        
        # Executar o script
        add_test_log(test_id, f"Executando teste(s) {test_type} via shell...")
        print(f"[INFO] Executando teste avançado via shell com argumentos: {args}")
        job["progress"] = 30
        
        try:
            # Executar o script fora do ambiente virtual
            command = f"cd /home/br10config/unbound/tests && bash ./teste_avancado.sh {' '.join(args)}"
            print(f"[INFO] Executando comando: {command}")
            
            result = subprocess.run(command, 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   text=True,
                                   shell=True,
                                   check=True)
            
            job["progress"] = 80
            
            # Logar a saída para depuração
            print(f"[INFO] Saída do comando: {result.stdout}")
            if result.stderr:
                print(f"[AVISO] Erro do comando: {result.stderr}")
            
            # O script deve retornar o caminho do arquivo JSON na última linha
            output_lines = result.stdout.strip().split('\n')
            print(f"[INFO] Linhas de saída: {len(output_lines)}")
            
            result_file = None
            # Procurar pela linha que contém um caminho para um arquivo JSON
            for line in reversed(output_lines):
                if '.json' in line:
                    result_file = line.strip()
                    print(f"[INFO] Arquivo JSON encontrado: {result_file}")
                    break
            
            # Se não encontrou na saída, usar a última linha
            if not result_file and output_lines:
                result_file = output_lines[-1]
                print(f"[INFO] Usando última linha como caminho do arquivo: {result_file}")
            
            # Verificar se o arquivo existe
            if result_file and os.path.exists(result_file) and result_file.endswith('.json'):
                add_test_log(test_id, f"Teste concluído, resultados salvos em: {result_file}", "success")
                print(f"[INFO] Arquivo de resultados existe: {result_file}")
                
                # Verificar o conteúdo do JSON
                try:
                    with open(result_file, 'r') as f:
                        result_data = json.load(f)
                    
                    print(f"[INFO] Conteúdo do JSON: {len(result_data)} chaves")
                    
                    # Estruturar resultados com base no tipo de teste
                    if test_type == 'stress':
                        job["results"]["stress"] = result_data
                    elif test_type == 'leak':
                        job["results"]["leak"] = result_data
                    elif test_type == 'comparative':
                        job["results"]["comparative"] = result_data
                    elif test_type == 'all':
                        # Processar cada tipo de resultado
                        if "stress" in result_data:
                            job["results"]["stress"] = result_data["stress"]
                        if "leak" in result_data:
                            job["results"]["leak"] = result_data["leak"]
                        if "comparative" in result_data:
                            job["results"]["comparative"] = result_data["comparative"]
                    
                    # Adicionar logs com base nos resultados
                    if "stress" in job["results"] and "performance" in job["results"]["stress"]:
                        add_test_log(test_id, f"Avaliação de stress: {job['results']['stress']['performance']}")
                    
                    if "leak" in job["results"] and "status" in job["results"]["leak"]:
                        add_test_log(test_id, f"Status do teste de vazamento: {job['results']['leak']['status']}")
                    
                    if "comparative" in job["results"] and "fastest_server" in job["results"]["comparative"]:
                        add_test_log(test_id, f"Servidor mais rápido: {job['results']['comparative']['fastest_server']}")
                        
                except Exception as e:
                    print(f"[ERRO] Falha ao processar JSON: {str(e)}")
                    logger.error(f"Erro ao processar JSON: {str(e)}")
                    add_test_log(test_id, f"Erro ao processar resultados: {str(e)}", "warning")
                
                # Criar URL para acessar o arquivo através da API
                api_path = f'/api/teste_avancado/results/{os.path.basename(result_file)}'
                return api_path
            else:
                # Se não encontrou o arquivo JSON no output, buscar por padrão
                print("[INFO] Arquivo JSON não encontrado na saída, buscando o mais recente")
                report_dir = "/var/log/br10"
                json_files = glob.glob(os.path.join(report_dir, "teste_avancado_*.json"))
                
                if json_files:
                    # Pegar o arquivo mais recente
                    json_files.sort(key=os.path.getmtime, reverse=True)
                    result_file = json_files[0]
                    print(f"[INFO] Encontrado arquivo mais recente: {result_file}")
                    api_path = f'/api/teste_avancado/results/{os.path.basename(result_file)}'
                    add_test_log(test_id, f"Teste concluído, resultados salvos em: {result_file}", "success")
                    return api_path
                
                add_test_log(test_id, "Arquivo de resultados não encontrado", "error")
                print("[ERRO] Nenhum arquivo de resultados encontrado")
                raise FileNotFoundError("Arquivo de resultados não encontrado")
        except subprocess.CalledProcessError as e:
            print(f"[ERRO] Falha ao executar script de teste: {e}")
            print(f"[ERRO] Saída de erro: {e.stderr}")
            add_test_log(test_id, f"Erro ao executar teste: {e}", "error")
            add_test_log(test_id, f"Saída de erro: {e.stderr}", "error")
            raise RuntimeError(f"Erro ao executar teste avançado: {e}")
        
        # Finalizar o teste
        job["status"] = "Teste concluído"
        job["progress"] = 100
        job["completed"] = True
        
        add_test_log(test_id, "Teste concluído com sucesso!", "success")
        
    except Exception as e:
        # Em caso de erro, registrar e marcar como concluído com erro
        logger.error(f"Erro ao executar teste avançado: {e}")
        add_test_log(test_id, f"Erro ao executar teste: {str(e)}", "error")
        job["status"] = "Erro ao executar teste"
        job["progress"] = 100
        job["completed"] = True
        
def run_stress_test(test_id, params):
    """Executa o teste de stress DNS"""
    job = teste_avancado_jobs[test_id]
    job["status"] = "Executando teste de stress DNS..."
    job["progress"] = 10
    
    # Obter parâmetros
    num_queries = int(params.get('numQueries', 1000))
    num_parallel = int(params.get('numParallel', 10))
    
    add_test_log(test_id, f"Configurando teste com {num_queries} consultas ({num_parallel} simultâneas)")
    
    # Verificar se o Unbound está rodando
    add_test_log(test_id, "Verificando status do serviço Unbound...")
    
    try:
        result = subprocess.run(["systemctl", "is-active", "unbound"], 
                                capture_output=True, text=True, check=False)
        
        if result.stdout.strip() != "active":
            add_test_log(test_id, "AVISO: O serviço Unbound não está ativo!", "warning")
    except Exception as e:
        add_test_log(test_id, f"Erro ao verificar status do Unbound: {str(e)}", "warning")
    
    # Verificar recursos antes do teste
    add_test_log(test_id, "Verificando recursos do sistema antes do teste...")
    job["progress"] = 15
    
    cpu_before = "N/A"
    mem_before = "N/A"
    
    try:
        # Obter PID do Unbound
        result = subprocess.run(["pidof", "unbound"], 
                                capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            unbound_pid = result.stdout.strip()
            # Obter uso de CPU e memória
            result = subprocess.run(["ps", "-p", unbound_pid, "-o", "%cpu,%mem", "--no-headers"], 
                                   capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                cpu_mem = result.stdout.strip().split()
                if len(cpu_mem) >= 2:
                    cpu_before = cpu_mem[0]
                    mem_before = cpu_mem[1]
    except Exception as e:
        add_test_log(test_id, f"Erro ao obter recursos iniciais: {str(e)}", "warning")
    
    add_test_log(test_id, f"Recursos iniciais - CPU: {cpu_before}%, Memória: {mem_before}%")
    
    # Criar lista de domínios para o teste
    domains = [
        "google.com", "facebook.com", "amazon.com", "microsoft.com", "apple.com",
        "netflix.com", "wikipedia.org", "twitter.com", "instagram.com", "linkedin.com"
    ]
    
    # Criar arquivo temporário de domínios
    temp_domains = tempfile.NamedTemporaryFile(mode='w+', delete=False)
    
    try:
        for i in range(num_queries):
            domain = domains[i % len(domains)]
            temp_domains.write(f"{domain}\n")
        
        temp_domains.close()
        
        # Iniciar teste
        job["progress"] = 20
        add_test_log(test_id, "Iniciando execução das consultas DNS...")
        
        start_time = time.time()
        successful = 0
        failed = 0
        
        # Verificar se temos o GNU parallel instalado
        has_parallel = subprocess.run(["which", "parallel"], 
                                     capture_output=True, check=False).returncode == 0
        
        if has_parallel:
            add_test_log(test_id, "Usando GNU parallel para consultas simultâneas")
            
            # Criar arquivo temporário para resultados
            results_file = tempfile.NamedTemporaryFile(delete=False)
            results_file.close()
            
            # Montar comando para o parallel
            cmd = [
                "parallel", "-j", str(num_parallel),
                "dig @127.0.0.1 {} +short +tries=1 +time=2 > /dev/null 2>&1 && echo 'OK' || echo 'FAIL'",
                "<", temp_domains.name
            ]
            
            # Executar comando como string
            cmd_str = " ".join(cmd)
            
            with open(results_file.name, 'w') as f:
                process = subprocess.run(cmd_str, shell=True, stdout=f, stderr=subprocess.PIPE, text=True)
            
            # Ler resultados
            with open(results_file.name, 'r') as f:
                results = f.read().splitlines()
                
            successful = results.count("OK")
            failed = results.count("FAIL")
            
            # Limpar arquivo temporário de resultados
            os.unlink(results_file.name)
            
        else:
            add_test_log(test_id, "GNU parallel não encontrado. Usando método alternativo (mais lento).", "warning")
            
            # Abrir arquivo de domínios
            with open(temp_domains.name, 'r') as f:
                domains_list = f.read().splitlines()
            
            # Usar um método alternativo com lotes de consultas
            batch_size = min(50, num_parallel * 5)
            
            for i in range(0, num_queries, batch_size):
                # Atualizar progresso
                job["progress"] = 20 + int(70 * i / num_queries)
                job["status"] = f"Executando consultas... {i}/{num_queries}"
                
                if i % (batch_size * 4) == 0:  # Não logar muito frequentemente
                    add_test_log(test_id, f"Processando lote {i+1}-{min(i+batch_size, num_queries)} de {num_queries}")
                
                # Pegar subconjunto de domínios para este lote
                batch_domains = domains_list[i:min(i+batch_size, num_queries)]
                
                # Executar lote de consultas
                processes = []
                for domain in batch_domains:
                    cmd = ["dig", "@127.0.0.1", domain, "+short", "+tries=1", "+time=2"]
                    processes.append(subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
                
                # Aguardar conclusão e contar resultados
                for p in processes:
                    ret_code = p.wait()
                    if ret_code == 0:
                        successful += 1
                    else:
                        failed += 1
    
    finally:
        # Limpar arquivo temporário
        try:
            os.unlink(temp_domains.name)
        except:
            pass
    
    # Calcular tempo total e taxa de consultas
    end_time = time.time()
    total_time = end_time - start_time
    query_rate = num_queries / total_time if total_time > 0 else 0
    success_rate = (successful * 100) / num_queries if num_queries > 0 else 0
    
    # Verificar recursos após o teste
    add_test_log(test_id, "Verificando recursos do sistema após o teste...")
    
    cpu_after = "N/A"
    mem_after = "N/A"
    
    try:
        # Obter PID do Unbound
        result = subprocess.run(["pidof", "unbound"], 
                                capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            unbound_pid = result.stdout.strip()
            # Obter uso de CPU e memória
            result = subprocess.run(["ps", "-p", unbound_pid, "-o", "%cpu,%mem", "--no-headers"], 
                                   capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                cpu_mem = result.stdout.strip().split()
                if len(cpu_mem) >= 2:
                    cpu_after = cpu_mem[0]
                    mem_after = cpu_mem[1]
    except Exception as e:
        add_test_log(test_id, f"Erro ao obter recursos finais: {str(e)}", "warning")
    
    add_test_log(test_id, f"Recursos após teste - CPU: {cpu_after}%, Memória: {mem_after}%")
    
    # Registrar resultados
    add_test_log(test_id, f"Teste concluído em {total_time:.2f} segundos")
    add_test_log(test_id, f"Total de consultas: {num_queries}")
    add_test_log(test_id, f"Consultas bem-sucedidas: {successful}")
    add_test_log(test_id, f"Consultas falhas: {failed}")
    add_test_log(test_id, f"Taxa de consultas: {query_rate:.2f} consultas/segundo")
    add_test_log(test_id, f"Taxa de sucesso: {success_rate:.2f}%")
    
    # Avaliação do desempenho
    if query_rate > 100:
        performance = "Excelente - O servidor consegue processar mais de 100 consultas por segundo"
    elif query_rate > 50:
        performance = "Bom - O servidor tem desempenho adequado para uso normal"
    elif query_rate > 20:
        performance = "Razoável - O servidor pode ter dificuldades com cargas elevadas"
    else:
        performance = "Preocupante - O servidor pode precisar de otimização ou mais recursos"
    
    add_test_log(test_id, f"Avaliação: {performance}", "success" if query_rate > 50 else "warning")
    
    # Armazenar resultados
    job["results"]["stress"] = {
        "total_queries": num_queries,
        "successful_queries": successful,
        "failed_queries": failed,
        "total_time": f"{total_time:.2f}",
        "query_rate": f"{query_rate:.2f}",
        "success_rate": f"{success_rate:.2f}",
        "performance": performance,
        "cpu_before": cpu_before,
        "mem_before": mem_before,
        "cpu_after": cpu_after,
        "mem_after": mem_after
    }
    
    job["progress"] = 100

def run_leak_test(test_id, params):
    """Executa o teste de vazamento DNS"""
    job = teste_avancado_jobs[test_id]
    job["status"] = "Executando teste de vazamento DNS..."
    job["progress"] = 10
    
    # Obter parâmetros
    interface = params.get('interface', 'auto')
    capture_time = int(params.get('captureTime', 10))
    
    # Verificar se o tcpdump está instalado
    add_test_log(test_id, "Verificando se o tcpdump está instalado...")
    
    has_tcpdump = subprocess.run(["which", "tcpdump"], 
                                capture_output=True, check=False).returncode == 0
    
    if not has_tcpdump:
        add_test_log(test_id, "O tcpdump não está instalado. Tentando instalar...", "warning")
        
        # Tentar instalar tcpdump
        try:
            add_test_log(test_id, "Instalando tcpdump...")
            
            install_result = subprocess.run(["apt-get", "update", "-qq"], 
                                           capture_output=True, check=False)
            
            if install_result.returncode != 0:
                add_test_log(test_id, "Erro ao atualizar repositórios", "error")
                raise Exception("Falha ao instalar tcpdump")
            
            install_result = subprocess.run(["apt-get", "install", "-y", "tcpdump"], 
                                           capture_output=True, check=False)
            
            if install_result.returncode != 0:
                add_test_log(test_id, "Erro ao instalar tcpdump", "error")
                raise Exception("Falha ao instalar tcpdump")
            
            add_test_log(test_id, "O tcpdump foi instalado com sucesso", "success")
        except Exception as e:
            add_test_log(test_id, f"Não foi possível instalar o tcpdump: {str(e)}", "error")
            raise Exception(f"O teste de vazamento DNS requer tcpdump, que não está disponível: {str(e)}")
    
    # Determinar a interface de rede
    if interface == 'auto':
        add_test_log(test_id, "Detectando interface de rede principal...")
        
        try:
            # Obter a interface da rota padrão
            result = subprocess.run(["ip", "route", "get", "8.8.8.8"], 
                                    capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                interface_match = re.search(r'dev\s+(\S+)', result.stdout)
                if interface_match:
                    interface = interface_match.group(1)
                    add_test_log(test_id, f"Interface detectada: {interface}")
                else:
                    # Tentar outro método
                    result = subprocess.run(["route", "-n"], 
                                           capture_output=True, text=True, check=False)
                    
                    if result.returncode == 0:
                        for line in result.stdout.splitlines():
                            if 'UG' in line and '0.0.0.0' in line:
                                parts = line.split()
                                if len(parts) >= 8:
                                    interface = parts[7]
                                    add_test_log(test_id, f"Interface detectada: {interface}")
                                    break
            
            if interface == 'auto':
                # Usar a primeira interface não-loopback como fallback
                interfaces = netifaces.interfaces()
                for iface in interfaces:
                    if not iface.startswith('lo'):
                        interface = iface
                        add_test_log(test_id, f"Nenhuma rota padrão encontrada. Usando interface: {interface}", "warning")
                        break
            
            if interface == 'auto':
                add_test_log(test_id, "Não foi possível detectar uma interface de rede", "error")
                raise Exception("Não foi possível detectar uma interface de rede")
        except Exception as e:
            add_test_log(test_id, f"Erro ao detectar interface: {str(e)}", "error")
            raise Exception(f"Não foi possível detectar a interface de rede: {str(e)}")
    
    # Criar arquivos temporários para a captura e saída
    capture_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pcap')
    capture_file.close()
    
    output_file = tempfile.NamedTemporaryFile(delete=False)
    output_file.close()
    
    job["progress"] = 30
    add_test_log(test_id, f"Iniciando captura de tráfego DNS na interface {interface} por {capture_time} segundos...")
    
    try:
        # Iniciar captura com tcpdump
        tcpdump_proc = subprocess.Popen(
            ["tcpdump", "-i", interface, "-nn", "udp port 53", "-w", capture_file.name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Aguardar um pouco para o tcpdump iniciar
        time.sleep(1)
        
        # Fazer algumas consultas DNS para testar
        add_test_log(test_id, "Executando consultas de teste...")
        random_domain = f"random-{int(time.time())}.com"
        canary_domain = "canary.tools"
        
        job["progress"] = 40
        
        # Função para executar consultas
        def run_queries():
            subprocess.run(["dig", "@127.0.0.1", random_domain, "+tries=1", "+time=2"], 
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            
            subprocess.run(["dig", "@127.0.0.1", canary_domain, "+tries=1", "+time=2"], 
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            
            subprocess.run(["dig", "@127.0.0.1", "google.com", "+tries=1", "+time=2"], 
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        
        # Executar consultas em uma thread separada
        query_thread = threading.Thread(target=run_queries)
        query_thread.daemon = True
        query_thread.start()
        
        # Atualizar progresso enquanto aguarda
        for i in range(capture_time):
            job["progress"] = 40 + int((i / capture_time) * 40)
            if i % 3 == 0:  # Atualizar a cada 3 segundos
                remaining = capture_time - i
                add_test_log(test_id, f"Captura em andamento... {remaining} segundos restantes")
            time.sleep(1)
        
        # Finalizar captura
        tcpdump_proc.terminate()
        try:
            tcpdump_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            tcpdump_proc.kill()
        
        # Analisar captura
        job["progress"] = 80
        add_test_log(test_id, "Analisando captura de tráfego DNS...")
        
        analysis_cmd = ["tcpdump", "-r", capture_file.name, "-nn"]
        
        with open(output_file.name, "w") as f:
            subprocess.run(analysis_cmd, stdout=f, stderr=subprocess.PIPE, check=False)
        
        # Ler saída da análise
        with open(output_file.name, "r") as f:
            capture_output = f.read()
        
        # Detectar servidores DNS externos
        dns_servers = set()
        for line in capture_output.splitlines():
            # Procurar por IPs seguidos de .53 (porta DNS)
            ip_matches = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\.53', line)
            for ip in ip_matches:
                # Ignorar localhost e IPs da rede local
                if not ip.startswith('127.') and ip != '127.0.0.1':
                    dns_servers.add(ip)
        
        # Determinar se houve vazamento
        if dns_servers:
            add_test_log(test_id, "Possível vazamento DNS detectado!", "warning")
            add_test_log(test_id, "Servidores DNS externos detectados:")
            
            for server in sorted(dns_servers):
                add_test_log(test_id, f"- {server}")
            
            leak_status = "Vazamento detectado - Consultas sendo enviadas para servidores DNS externos"
            leaks_found = True
        else:
            add_test_log(test_id, "Nenhum vazamento DNS detectado. Todas as consultas estão sendo processadas localmente.", "success")
            leak_status = "Sem vazamentos - Todas as consultas processadas localmente"
            leaks_found = False
        
        # Armazenar resultados
        job["results"]["leak"] = {
            "interface": interface,
            "capture_time": capture_time,
            "leaks_found": leaks_found,
            "detected_servers": sorted(list(dns_servers)) if dns_servers else [],
            "status": leak_status
        }
        
    finally:
        # Limpar arquivos temporários
        try:
            os.unlink(capture_file.name)
            os.unlink(output_file.name)
        except:
            pass
    
    job["progress"] = 100
    add_test_log(test_id, "Teste de vazamento DNS concluído")

def run_comparative_test(test_id, params):
    """Executa o teste comparativo de DNS"""
    job = teste_avancado_jobs[test_id]
    job["status"] = "Executando teste comparativo DNS..."
    job["progress"] = 10
    
    # Definir servidores DNS para teste
    dns_servers = [
        {"ip": "127.0.0.1", "name": "Unbound Local"}
    ]
    
    # Adicionar servidores escolhidos pelo usuário
    if 'dnsServers' in params and params['dnsServers']:
        user_servers = params['dnsServers']
        if '8.8.8.8' in user_servers:
            dns_servers.append({"ip": "8.8.8.8", "name": "Google DNS"})
        if '1.1.1.1' in user_servers:
            dns_servers.append({"ip": "1.1.1.1", "name": "Cloudflare DNS"})
        if '9.9.9.9' in user_servers:
            dns_servers.append({"ip": "9.9.9.9", "name": "Quad9 DNS"})
        if '208.67.222.222' in user_servers:
            dns_servers.append({"ip": "208.67.222.222", "name": "OpenDNS"})
    else:
        # Usar todos os servidores padrão se não houver seleção
        dns_servers.extend([
            {"ip": "8.8.8.8", "name": "Google DNS"},
            {"ip": "1.1.1.1", "name": "Cloudflare DNS"},
            {"ip": "9.9.9.9", "name": "Quad9 DNS"},
            {"ip": "208.67.222.222", "name": "OpenDNS"}
        ])
    
    # Definir domínios para teste
    domains = ["google.com", "facebook.com", "amazon.com", "netflix.com", "microsoft.com"]
    
    add_test_log(test_id, f"Iniciando teste comparativo com {len(dns_servers)} servidores DNS")
    add_test_log(test_id, f"Domínios para teste: {', '.join(domains)}")
    
    # Resultados do teste
    server_results = []
    fastest_time = float('inf')
    slowest_time = 0
    fastest_server = ""
    slowest_server = ""
    
    # Testar cada servidor
    for idx, server in enumerate(dns_servers):
        job["progress"] = 10 + int(80 * idx / len(dns_servers))
        job["status"] = f"Testando {server['name']}..."
        
        add_test_log(test_id, f"Testando {server['name']} ({server['ip']})...")
        
        server_data = {
            "name": server['name'],
            "ip": server['ip'],
            "results": [],
            "total_time": 0,
            "success_count": 0
        }
        
        # Testar cada domínio
        for domain in domains:
            domain_total = 0
            success_count = 0
            
            # Fazer 3 tentativas para cada domínio
            for i in range(3):
                try:
                    start_time = time.time()
                    result = subprocess.run(
                        ["dig", f"@{server['ip']}", domain, "+short", "+tries=1", "+time=2"],
                        capture_output=True, check=False
                    )
                    
                    end_time = time.time()
                    
                    if result.returncode == 0:
                        elapsed = (end_time - start_time) * 1000  # Em milissegundos
                        domain_total += elapsed
                        success_count += 1
                except Exception as e:
                    add_test_log(test_id, f"Erro ao consultar {domain} via {server['name']}: {str(e)}", "warning")
            
            # Calcular média para este domínio
            if success_count > 0:
                domain_avg = domain_total / success_count
                server_data["results"].append(f"{domain_avg:.2f}ms")
                server_data["total_time"] += domain_avg
                server_data["success_count"] += 1
            else:
                server_data["results"].append("Falha")
                add_test_log(test_id, f"Falha ao consultar {domain} via {server['name']}", "warning")
        
        # Calcular média geral
        if server_data["success_count"] > 0:
            avg_time = server_data["total_time"] / len(domains)
            server_data["average"] = f"{avg_time:.2f}ms"
            
            add_test_log(test_id, f"{server['name']}: Tempo médio de resposta {avg_time:.2f}ms")
            
            # Verificar se é o mais rápido ou mais lento
            if avg_time < fastest_time:
                fastest_time = avg_time
                fastest_server = server['name']
            
            if avg_time > slowest_time:
                slowest_time = avg_time
                slowest_server = server['name']
        else:
            server_data["average"] = "Falha"
            add_test_log(test_id, f"{server['name']}: Falha em todas as consultas", "warning")
        
        server_results.append(server_data)
    
    # Analisar resultados
    job["progress"] = 90
    job["status"] = "Analisando resultados comparativos..."
    
    # Verificar como o Unbound local se compara
    unbound_avg = "N/A"
    for server in server_results:
        if server["name"] == "Unbound Local" and server["average"] != "Falha":
            unbound_avg = server["average"]
            break
    
    if fastest_server:
        add_test_log(test_id, f"Servidor mais rápido: {fastest_server} ({fastest_time:.2f}ms)", "success")
        
        if fastest_server == "Unbound Local":
            add_test_log(test_id, "Excelente! Seu servidor Unbound local é o mais rápido.", "success")
        elif unbound_avg != "N/A":
            add_test_log(test_id, f"Seu servidor Unbound local ({unbound_avg}) não é o mais rápido.", "warning")
            add_test_log(test_id, "Considere ajustar a configuração para melhorar o desempenho.")
    else:
        add_test_log(test_id, "Não foi possível determinar o servidor mais rápido.", "warning")
    
    # Armazenar resultados
    job["results"]["comparative"] = {
        "servers": server_results,
        "domains": domains,
        "fastest_server": fastest_server if fastest_server else "N/A",
        "slowest_server": slowest_server if slowest_server else "N/A",
        "unbound_avg": unbound_avg
    }
    
    job["progress"] = 100
    add_test_log(test_id, "Teste comparativo concluído")

    
def add_test_log(test_id, message, log_type="info"):
    """Adiciona uma entrada de log ao teste"""
    if test_id in teste_avancado_jobs:
        teste_avancado_jobs[test_id]["log"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "type": log_type
        })
    
def generate_report(results, test_type):
    """Gera um relatorio de teste avancado"""
    # Criar diretorio para relatorios se nao existir
    reports_dir = os.path.join(BASE_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    # Nome do arquivo de relatorio
    report_file = os.path.join(reports_dir, f"teste_avancado_{int(time.time())}.txt")
    
    with open(report_file, "w") as f:
        f.write("=========================================================\n")
        f.write(f"RELAToRIO DE TESTES AVANcADOS DNS - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write("=========================================================\n\n")
        
        # Informacoes do sistema
        f.write("=== INFORMAcoES DO SISTEMA ===\n")
        
        # Versao do sistema operacional
        try:
            os_version = subprocess.run(["cat", "/etc/os-release"], capture_output=True, text=True, check=False)
            if os_version.returncode == 0:
                for line in os_version.stdout.splitlines():
                    if line.startswith("PRETTY_NAME="):
                        # Obter parte apos o "=" e remover aspas no inicio e fim
                        os_name = line.split('=', 1)[1]
                        os_name = os_name.strip().strip('"\'')  # Remove aspas duplas e simples
                        f.write(f"Sistema Operacional: {os_name}\n")
                        break
        except Exception as e:
            logger.error(f"Erro ao determinar versao do sistema: {e}")
            f.write("Sistema Operacional: Nao identificado\n")
        
        # Versao do kernel
        try:
            kernel = subprocess.run(["uname", "-r"], capture_output=True, text=True, check=False)
            if kernel.returncode == 0:
                f.write(f"Kernel: {kernel.stdout.strip()}\n")
        except:
            f.write("Kernel: Nao identificado\n")
        
        # Recursos do sistema
        f.write("\nRecursos do Sistema:\n")
        
        # CPU
        try:
            cpu_info = subprocess.run(["grep", "-c", "processor", "/proc/cpuinfo"], 
                                     capture_output=True, text=True, check=False)
            if cpu_info.returncode == 0:
                f.write(f"CPU: {cpu_info.stdout.strip()} cores\n")
        except:
            f.write("CPU: Nao identificado\n")
        
        # Memoria
        try:
            mem_info = subprocess.run(["free", "-h"], capture_output=True, text=True, check=False)
            if mem_info.returncode == 0:
                for line in mem_info.stdout.splitlines():
                    if line.startswith("Mem:"):
                        parts = line.split()
                        if len(parts) >= 3:
                            f.write(f"Memoria Total: {parts[1]}\n")
                            f.write(f"Memoria Livre: {parts[3]}\n")
                        break
        except:
            f.write("Memoria: Nao identificada\n")
        
        # Versao do Unbound
        f.write("\nUnbound:\n")
        try:
            unbound_version = subprocess.run(["unbound", "-V"], 
                                           capture_output=True, text=True, check=False)
            if unbound_version.returncode == 0:
                f.write(f"{unbound_version.stdout.splitlines()[0]}\n")
        except:
            f.write("Versao nao identificada\n")
        
        # Estado do servico
        try:
            unbound_status = subprocess.run(["systemctl", "status", "unbound"], 
                                           capture_output=True, text=True, check=False)
            if unbound_status.returncode == 0:
                for line in unbound_status.stdout.splitlines():
                    if "Active:" in line:
                        f.write(f"Status: {line.strip()}\n")
                        break
        except:
            f.write("Status: Nao identificado\n")
        
        # Adicionar resultados dos testes executados
        f.write("\n\n")
        
        # Teste de Stress
        if "stress" in results or test_type == "stress":
            stress_results = results.get("stress", results if test_type == "stress" else {})
            
            if stress_results:
                f.write("=== RESULTADOS DO TESTE DE STRESS DNS ===\n")
                f.write(f"Total de consultas: {stress_results.get('total_queries', 'N/A')}\n")
                f.write(f"Consultas bem-sucedidas: {stress_results.get('successful_queries', 'N/A')}\n")
                f.write(f"Consultas falhas: {stress_results.get('failed_queries', 'N/A')}\n")
                f.write(f"Tempo total: {stress_results.get('total_time', 'N/A')} segundos\n")
                f.write(f"Taxa de consultas: {stress_results.get('query_rate', 'N/A')} consultas/segundo\n")
                f.write(f"Taxa de sucesso: {stress_results.get('success_rate', 'N/A')}%\n\n")
                f.write(f"Avaliacao: {stress_results.get('performance', 'N/A')}\n")
                
                # Recursos do sistema
                f.write("\nUso de recursos:\n")
                f.write(f"CPU antes do teste: {stress_results.get('cpu_before', 'N/A')}%\n")
                f.write(f"CPU apos o teste: {stress_results.get('cpu_after', 'N/A')}%\n")
                f.write(f"Memoria antes do teste: {stress_results.get('mem_before', 'N/A')}%\n")
                f.write(f"Memoria apos o teste: {stress_results.get('mem_after', 'N/A')}%\n")
                
                f.write("\n")
        
        # Teste de Vazamento
        if "leak" in results or test_type == "leak":
            leak_results = results.get("leak", results if test_type == "leak" else {})
            
            if leak_results:
                f.write("=== RESULTADOS DO TESTE DE VAZAMENTO DNS ===\n")
                f.write(f"Interface testada: {leak_results.get('interface', 'N/A')}\n")
                f.write(f"Tempo de captura: {leak_results.get('capture_time', 'N/A')} segundos\n")
                f.write(f"Status: {leak_results.get('status', 'N/A')}\n")
                
                if leak_results.get('leaks_found', False):
                    f.write("\nServidores DNS externos detectados:\n")
                    for server in leak_results.get('detected_servers', []):
                        f.write(f"- {server}\n")
                
                f.write("\n")
        
        # Teste Comparativo
        if "comparative" in results or test_type == "comparative":
            comp_results = results.get("comparative", results if test_type == "comparative" else {})
            
            if comp_results:
                f.write("=== RESULTADOS DO TESTE COMPARATIVO DNS ===\n")
                f.write(f"Servidor mais rapido: {comp_results.get('fastest_server', 'N/A')}\n")
                f.write(f"Servidor mais lento: {comp_results.get('slowest_server', 'N/A')}\n")
                
                # Tabela de resultados
                f.write("\nResultados por servidor:\n")
                f.write("-" * 60 + "\n")
                
                # Cabecalho da tabela
                header = "Servidor DNS".ljust(20)
                
                for domain in comp_results.get('domains', []):
                    header += domain.ljust(15)
                
                header += "Media".ljust(10)
                f.write(f"{header}\n")
                f.write("-" * 60 + "\n")
                
                # Dados da tabela
                for server in comp_results.get('servers', []):
                    line = server.get('name', 'N/A').ljust(20)
                    
                    for result in server.get('results', []):
                        line += result.ljust(15)
                    
                    line += server.get('average', 'N/A').ljust(10)
                    f.write(f"{line}\n")

                f.write("-" * 60 + "\n\n")

        # Rodape
        f.write("=========================================================\n")
        f.write(f"Relatorio gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write(f"BR10 DNS Advanced Testing Tool\n")
        f.write("=========================================================\n")

    return report_file


# Inicializacao da aplicacao
if __name__ == '__main__':
    # Garantir que os diretorios necessarios existam
    def ensure_directories():
        """Garante que os diretorios necessarios existam"""
        os.makedirs(os.path.dirname(BLOCKED_DOMAINS_PATH), exist_ok=True)
        os.makedirs(HISTORY_DIR, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)

    # Chamar essa funcao na inicializacao
    ensure_directories()

    # Inicializar usuarios
    init_users()

    # Iniciar servidor
    app.run(host='0.0.0.0', port=8084, debug=False)
