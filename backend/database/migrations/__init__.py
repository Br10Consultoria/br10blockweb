#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Database Migrations
======================================
Sistema de migrações do banco de dados

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def get_migration_files() -> List[Path]:
    """Retorna lista ordenada de arquivos de migração"""
    migrations_dir = Path(__file__).parent
    migration_files = sorted(migrations_dir.glob("*.sql"))
    return migration_files


def run_migrations() -> None:
    """Executa todas as migrações pendentes"""
    from backend.database.db import db
    
    logger.info("Verificando migrações pendentes...")
    
    # Criar tabela de controle de migrações
    create_migrations_table = """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        id SERIAL PRIMARY KEY,
        filename VARCHAR(255) UNIQUE NOT NULL,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    db.execute_query(create_migrations_table, fetch=False)
    
    # Obter migrações já aplicadas
    applied = db.execute_query(
        "SELECT filename FROM schema_migrations ORDER BY filename"
    )
    applied_filenames = {row['filename'] for row in applied}
    
    # Executar migrações pendentes
    migration_files = get_migration_files()
    pending_count = 0
    
    for migration_file in migration_files:
        filename = migration_file.name
        
        if filename in applied_filenames:
            continue
        
        logger.info(f"Aplicando migração: {filename}")
        
        try:
            # Ler e executar SQL
            with open(migration_file, 'r', encoding='utf-8') as f:
                sql = f.read()
            
            # Executar migração
            with db.get_cursor() as cursor:
                cursor.execute(sql)
                
                # Registrar migração aplicada
                cursor.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (filename,)
                )
            
            logger.info(f"Migração aplicada com sucesso: {filename}")
            pending_count += 1
            
        except Exception as e:
            logger.error(f"Erro ao aplicar migração {filename}: {e}")
            raise
    
    if pending_count == 0:
        logger.info("Nenhuma migração pendente")
    else:
        logger.info(f"{pending_count} migração(ões) aplicada(s) com sucesso")


def rollback_last_migration() -> None:
    """Reverte a última migração aplicada"""
    from backend.database.db import db
    
    # Obter última migração
    result = db.execute_query(
        "SELECT filename FROM schema_migrations ORDER BY applied_at DESC LIMIT 1"
    )
    
    if not result:
        logger.warning("Nenhuma migração para reverter")
        return
    
    filename = result[0]['filename']
    logger.warning(f"Revertendo migração: {filename}")
    
    # Procurar arquivo de rollback
    migrations_dir = Path(__file__).parent
    rollback_file = migrations_dir / filename.replace('.sql', '_rollback.sql')
    
    if not rollback_file.exists():
        logger.error(f"Arquivo de rollback não encontrado: {rollback_file}")
        return
    
    try:
        # Ler e executar SQL de rollback
        with open(rollback_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        with db.get_cursor() as cursor:
            cursor.execute(sql)
            
            # Remover registro da migração
            cursor.execute(
                "DELETE FROM schema_migrations WHERE filename = %s",
                (filename,)
            )
        
        logger.info(f"Migração revertida com sucesso: {filename}")
        
    except Exception as e:
        logger.error(f"Erro ao reverter migração {filename}: {e}")
        raise
