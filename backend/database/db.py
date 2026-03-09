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
        """Context manager para obter conexão do pool (sem auto-commit)."""
        conn = None
        try:
            conn = self._pool.getconn()
            conn.autocommit = False
            yield conn
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            logger.error(f"Erro na transação do banco: {e}")
            raise
        finally:
            if conn:
                self._pool.putconn(conn)

    @contextmanager
    def get_cursor(self, commit: bool = True):
        """Context manager para obter cursor com commit explícito."""
        conn = None
        cursor = None
        try:
            conn = self._pool.getconn()
            conn.autocommit = False
            cursor = conn.cursor()
            yield cursor
            if commit:
                conn.commit()
                logger.debug("Transação commitada com sucesso")
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                    logger.warning(f"Rollback executado devido a erro: {e}")
                except Exception as rb_err:
                    logger.error(f"Erro ao fazer rollback: {rb_err}")
            logger.error(f"Erro no cursor: {e}")
            raise
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                self._pool.putconn(conn)
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = True):
        """
        Executa uma query e retorna resultados.

        Regras de commit:
        - SELECT puro: sem commit (fetch=True, sem RETURNING)
        - INSERT/UPDATE/DELETE sem RETURNING: commit, retorna rowcount
        - INSERT/UPDATE com RETURNING: commit + fetchall para retornar os dados
        - fetch=False explícito: sempre commit, retorna rowcount
        """
        query_upper = query.strip().upper()
        is_select = query_upper.startswith('SELECT')
        has_returning = 'RETURNING' in query_upper

        # Precisa de commit se: não é SELECT puro, OU é INSERT/UPDATE com RETURNING
        needs_commit = not is_select or has_returning

        with self.get_cursor(commit=needs_commit) as cursor:
            cursor.execute(query, params)

            # Retornar dados se: é SELECT, OU tem RETURNING, OU fetch=True explícito
            if fetch or has_returning:
                try:
                    rows = cursor.fetchall()
                    if has_returning and not rows:
                        logger.warning(f"Query com RETURNING não retornou dados: {query[:80]}")
                    return rows
                except psycopg2.ProgrammingError:
                    # fetchall() em query sem resultados (ex: INSERT sem RETURNING)
                    return []
                except Exception as e:
                    logger.error(f"Erro no fetchall: {e} | Query: {query[:80]}")
                    return []
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
    
    def initialize(self) -> None:
        """Inicializa o banco de dados: testa conexão e executa migrações pendentes."""
        logger.info("Inicializando banco de dados...")

        if not self.test_connection():
            raise Exception("Não foi possível conectar ao banco de dados")

        logger.info("Conexão com banco de dados estabelecida")

        # Executar migrações pendentes
        from backend.database.migrations import run_migrations
        run_migrations()

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
