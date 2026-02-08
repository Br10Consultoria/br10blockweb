#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Database Connection
======================================
Gerenciamento de conexão com PostgreSQL

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import logging
from contextlib import contextmanager
from typing import Optional

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from backend.config import Config

logger = logging.getLogger(__name__)


class Database:
    """Gerenciador de conexão com PostgreSQL"""
    
    _instance: Optional['Database'] = None
    _pool: Optional[pool.ThreadedConnectionPool] = None
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Inicializa o pool de conexões"""
        if self._pool is None:
            self._initialize_pool()
    
    def _initialize_pool(self) -> None:
        """Cria o pool de conexões"""
        try:
            self._pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                cursor_factory=RealDictCursor
            )
            logger.info(f"Pool de conexões PostgreSQL criado: {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")
        except Exception as e:
            logger.error(f"Erro ao criar pool de conexões: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Context manager para obter conexão do pool"""
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Erro na transação do banco: {e}")
            raise
        finally:
            if conn:
                self._pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, commit: bool = True):
        """Context manager para obter cursor"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                yield cursor
                if commit:
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Erro no cursor: {e}")
                raise
            finally:
                cursor.close()
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = True):
        """Executa uma query e retorna resultados"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            if fetch:
                return cursor.fetchall()
            return cursor.rowcount
    
    def execute_many(self, query: str, params_list: list) -> int:
        """Executa múltiplas queries com diferentes parâmetros"""
        with self.get_cursor() as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount
    
    def close_all_connections(self) -> None:
        """Fecha todas as conexões do pool"""
        if self._pool:
            self._pool.closeall()
            logger.info("Pool de conexões fechado")
    
    def test_connection(self) -> bool:
        """Testa a conexão com o banco"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result is not None
        except Exception as e:
            logger.error(f"Erro ao testar conexão: {e}")
            return False


# Instância global do banco
db = Database()


def init_database() -> None:
    """Inicializa o banco de dados e cria as tabelas"""
    logger.info("Inicializando banco de dados...")
    
    # Verificar conexão
    if not db.test_connection():
        raise Exception("Não foi possível conectar ao banco de dados")
    
    logger.info("Conexão com banco de dados estabelecida")
    
    # Executar migrações
    from backend.database.migrations import run_migrations
    run_migrations()


def close_database() -> None:
    """Fecha conexões com o banco"""
    db.close_all_connections()
