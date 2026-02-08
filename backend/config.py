#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Configurações
================================
Configurações centralizadas da aplicação

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Diretórios base
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
UPLOADS_DIR = BASE_DIR / "uploads"
DATA_DIR = BASE_DIR / "data"
BACKUPS_DIR = DATA_DIR / "backups"
LOGS_DIR = BASE_DIR / "logs"

class Config:
    """Configurações da aplicação"""
    
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(24).hex())
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8084))
    
    # PostgreSQL
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 5432))
    DB_NAME = os.getenv("DB_NAME", "br10blockweb")
    DB_USER = os.getenv("DB_USER", "br10user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "br10pass")
    
    # String de conexão PostgreSQL
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    
    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
    
    # Cache TTL (em segundos)
    CACHE_TTL_DOMAINS = int(os.getenv("CACHE_TTL_DOMAINS", 300))  # 5 minutos
    CACHE_TTL_STATS = int(os.getenv("CACHE_TTL_STATS", 60))  # 1 minuto
    CACHE_TTL_CLIENTS = int(os.getenv("CACHE_TTL_CLIENTS", 120))  # 2 minutos
    
    # Sessão
    SESSION_LIFETIME_HOURS = int(os.getenv("SESSION_LIFETIME_HOURS", 24))
    SESSION_TYPE = "redis"
    
    # Upload de arquivos
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))  # 16MB
    ALLOWED_EXTENSIONS = {"pdf"}
    UPLOAD_FOLDER = UPLOADS_DIR
    
    # API
    API_KEY_LENGTH = 32
    API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", 100))  # requisições por minuto
    
    # Unbound
    UNBOUND_ZONE_FILE = Path(os.getenv("UNBOUND_ZONE_FILE", "/var/lib/unbound/br10block-rpz.zone"))
    BLOCKED_DOMAINS_FILE = Path(os.getenv("BLOCKED_DOMAINS_PATH", "/var/lib/br10api/blocked_domains.txt"))
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = LOGS_DIR / "app.log"
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", 10 * 1024 * 1024))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 5))
    
    # Backup automático
    BACKUP_ENABLED = os.getenv("BACKUP_ENABLED", "True").lower() == "true"
    BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", 24))
    BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", 7))
    
    @classmethod
    def ensure_directories(cls) -> None:
        """Garante que os diretórios necessários existam"""
        for directory in [
            UPLOADS_DIR,
            DATA_DIR,
            BACKUPS_DIR,
            LOGS_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_redis_url(cls) -> str:
        """Retorna URL de conexão do Redis"""
        if cls.REDIS_PASSWORD:
            return f"redis://:{cls.REDIS_PASSWORD}@{cls.REDIS_HOST}:{cls.REDIS_PORT}/{cls.REDIS_DB}"
        return f"redis://{cls.REDIS_HOST}:{cls.REDIS_PORT}/{cls.REDIS_DB}"


class DevelopmentConfig(Config):
    """Configurações para desenvolvimento"""
    DEBUG = True
    LOG_LEVEL = "DEBUG"


class ProductionConfig(Config):
    """Configurações para produção"""
    DEBUG = False
    LOG_LEVEL = "WARNING"


class TestingConfig(Config):
    """Configurações para testes"""
    TESTING = True
    DB_NAME = "br10blockweb_test"
    REDIS_DB = 1


# Mapeamento de ambientes
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig
}


def get_config(env: str = None) -> Config:
    """Retorna configuração baseada no ambiente"""
    if env is None:
        env = os.getenv("FLASK_ENV", "default")
    return config_by_name.get(env, DevelopmentConfig)
