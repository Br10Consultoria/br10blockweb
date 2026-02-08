#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Cache Service
================================
Serviço de cache com Redis

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import json
import logging
from functools import wraps
from typing import Any, Callable, Optional, Union

import redis

from backend.config import Config

logger = logging.getLogger(__name__)


class CacheService:
    """Serviço de cache com Redis"""
    
    _instance: Optional['CacheService'] = None
    _redis_client: Optional[redis.Redis] = None
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super(CacheService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Inicializa conexão com Redis"""
        if self._redis_client is None:
            self._initialize_redis()
    
    def _initialize_redis(self) -> None:
        """Cria conexão com Redis"""
        try:
            self._redis_client = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                password=Config.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Testar conexão
            self._redis_client.ping()
            logger.info(f"Conexão Redis estabelecida: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
        
        except Exception as e:
            logger.warning(f"Redis não disponível: {e}")
            self._redis_client = None
    
    @property
    def is_available(self) -> bool:
        """Verifica se Redis está disponível"""
        if self._redis_client is None:
            return False
        
        try:
            self._redis_client.ping()
            return True
        except:
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Busca valor no cache"""
        if not self.is_available:
            return None
        
        try:
            value = self._redis_client.get(key)
            if value:
                # Tentar deserializar JSON
                try:
                    return json.loads(value)
                except:
                    return value
            return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar cache {key}: {e}")
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Define valor no cache"""
        if not self.is_available:
            return False
        
        try:
            # Serializar se necessário
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            if ttl:
                self._redis_client.setex(key, ttl, value)
            else:
                self._redis_client.set(key, value)
            
            return True
        
        except Exception as e:
            logger.error(f"Erro ao definir cache {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Remove valor do cache"""
        if not self.is_available:
            return False
        
        try:
            self._redis_client.delete(key)
            return True
        
        except Exception as e:
            logger.error(f"Erro ao deletar cache {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Remove todas as chaves que correspondem ao padrão"""
        if not self.is_available:
            return 0
        
        try:
            keys = self._redis_client.keys(pattern)
            if keys:
                return self._redis_client.delete(*keys)
            return 0
        
        except Exception as e:
            logger.error(f"Erro ao deletar padrão {pattern}: {e}")
            return 0
    
    def exists(self, key: str) -> bool:
        """Verifica se chave existe"""
        if not self.is_available:
            return False
        
        try:
            return self._redis_client.exists(key) > 0
        except:
            return False
    
    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Incrementa valor inteiro"""
        if not self.is_available:
            return None
        
        try:
            return self._redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Erro ao incrementar {key}: {e}")
            return None
    
    def expire(self, key: str, ttl: int) -> bool:
        """Define TTL para chave existente"""
        if not self.is_available:
            return False
        
        try:
            return self._redis_client.expire(key, ttl)
        except:
            return False
    
    def ttl(self, key: str) -> Optional[int]:
        """Retorna TTL restante da chave"""
        if not self.is_available:
            return None
        
        try:
            return self._redis_client.ttl(key)
        except:
            return None
    
    def flush_all(self) -> bool:
        """Limpa todo o cache (use com cuidado!)"""
        if not self.is_available:
            return False
        
        try:
            self._redis_client.flushdb()
            logger.warning("Cache Redis limpo completamente")
            return True
        except Exception as e:
            logger.error(f"Erro ao limpar cache: {e}")
            return False
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do Redis"""
        if not self.is_available:
            return {'available': False}
        
        try:
            info = self._redis_client.info()
            return {
                'available': True,
                'used_memory': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'total_keys': self._redis_client.dbsize(),
                'uptime_days': info.get('uptime_in_days'),
                'hit_rate': self._calculate_hit_rate(info)
            }
        except Exception as e:
            logger.error(f"Erro ao obter stats do Redis: {e}")
            return {'available': False, 'error': str(e)}
    
    @staticmethod
    def _calculate_hit_rate(info: dict) -> float:
        """Calcula taxa de acerto do cache"""
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        
        if hits + misses == 0:
            return 0.0
        
        return (hits / (hits + misses)) * 100


# Instância global do cache
cache = CacheService()


def cached(
    key_prefix: str,
    ttl: Optional[int] = None,
    key_builder: Optional[Callable] = None
):
    """
    Decorator para cachear resultado de função
    
    Args:
        key_prefix: Prefixo da chave de cache
        ttl: Tempo de vida em segundos (None = usar padrão)
        key_builder: Função para construir chave customizada
    
    Example:
        @cached('domains:list', ttl=300)
        def get_all_domains():
            return Domain.get_all()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Construir chave de cache
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Chave padrão: prefix:func_name:args_hash
                args_str = str(args) + str(sorted(kwargs.items()))
                cache_key = f"{key_prefix}:{func.__name__}:{hash(args_str)}"
            
            # Tentar buscar do cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # Executar função
            logger.debug(f"Cache miss: {cache_key}")
            result = func(*args, **kwargs)
            
            # Salvar no cache
            cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(pattern: str) -> int:
    """
    Invalida cache por padrão
    
    Args:
        pattern: Padrão de chaves (ex: 'domains:*')
    
    Returns:
        Número de chaves removidas
    """
    return cache.delete_pattern(pattern)


# Funções de cache específicas para o domínio

def cache_domains_list(domains: list, ttl: Optional[int] = None) -> bool:
    """Cacheia lista de domínios ativos"""
    if ttl is None:
        ttl = Config.CACHE_TTL_DOMAINS
    return cache.set('domains:active_list', domains, ttl)


def get_cached_domains_list() -> Optional[list]:
    """Retorna lista de domínios do cache"""
    return cache.get('domains:active_list')


def invalidate_domains_cache() -> None:
    """Invalida todo o cache relacionado a domínios"""
    cache.delete_pattern('domains:*')
    logger.info("Cache de domínios invalidado")


def cache_client_status(client_id: int, status: dict, ttl: Optional[int] = None) -> bool:
    """Cacheia status de cliente"""
    if ttl is None:
        ttl = Config.CACHE_TTL_CLIENTS
    return cache.set(f'client:status:{client_id}', status, ttl)


def get_cached_client_status(client_id: int) -> Optional[dict]:
    """Retorna status de cliente do cache"""
    return cache.get(f'client:status:{client_id}')


def cache_statistics(stats: dict, ttl: Optional[int] = None) -> bool:
    """Cacheia estatísticas gerais"""
    if ttl is None:
        ttl = Config.CACHE_TTL_STATS
    return cache.set('stats:general', stats, ttl)


def get_cached_statistics() -> Optional[dict]:
    """Retorna estatísticas do cache"""
    return cache.get('stats:general')


def rate_limit_check(identifier: str, limit: int, window: int = 60) -> bool:
    """
    Verifica rate limiting
    
    Args:
        identifier: Identificador único (IP, API key, etc)
        limit: Número máximo de requisições
        window: Janela de tempo em segundos
    
    Returns:
        True se dentro do limite, False se excedeu
    """
    if not cache.is_available:
        return True  # Se Redis não está disponível, permitir
    
    key = f'ratelimit:{identifier}'
    
    try:
        current = cache.increment(key)
        
        if current == 1:
            # Primeira requisição, definir TTL
            cache.expire(key, window)
        
        return current <= limit
    
    except:
        return True  # Em caso de erro, permitir
