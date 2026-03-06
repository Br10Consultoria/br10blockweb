#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Database Migrations
======================================
Sistema de migrações do banco de dados

IMPORTANTE: psycopg2 cursor.execute() executa apenas o PRIMEIRO statement
quando o SQL contém múltiplos statements separados por ';'.
Por isso, o SQL é dividido em statements individuais antes da execução.

Autor: BR10 Team
Versão: 3.0.2
"""

import logging
import re
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def split_sql_statements(sql: str) -> List[str]:
    """
    Divide um bloco de SQL em statements individuais de forma segura.

    Trata corretamente:
    - Comentários de linha (-- ...) — ignorados completamente
    - Comentários de bloco (/* ... */) — ignorados completamente
    - Strings literais com ponto-e-vírgula dentro ('...; ...')
    - Blocos DO $$ ... $$ (funções PL/pgSQL)
    """
    statements = []
    current = []
    i = 0
    in_string = False
    string_char = None
    in_dollar_quote = False
    dollar_tag = ''
    in_line_comment = False
    in_block_comment = False

    while i < len(sql):
        ch = sql[i]

        # Início de comentário de linha (--)
        if (not in_string and not in_dollar_quote and not in_block_comment
                and ch == '-' and i + 1 < len(sql) and sql[i + 1] == '-'):
            in_line_comment = True
            i += 2  # pular os dois traços
            continue

        # Dentro de comentário de linha — pular tudo até newline
        if in_line_comment:
            if ch == '\n':
                in_line_comment = False
            i += 1
            continue

        # Início de comentário de bloco (/*)
        if (not in_string and not in_dollar_quote and not in_line_comment
                and ch == '/' and i + 1 < len(sql) and sql[i + 1] == '*'):
            in_block_comment = True
            i += 2
            continue

        # Dentro de comentário de bloco — pular tudo até */
        if in_block_comment:
            if ch == '*' and i + 1 < len(sql) and sql[i + 1] == '/':
                i += 2
                in_block_comment = False
            else:
                i += 1
            continue

        # Dollar quoting (blocos DO $$ ... $$ ou $tag$ ... $tag$)
        if (not in_string and not in_line_comment and not in_block_comment
                and ch == '$'):
            match = re.match(r'\$([^$]*)\$', sql[i:])
            if match:
                tag = match.group(0)
                if not in_dollar_quote:
                    in_dollar_quote = True
                    dollar_tag = tag
                    current.append(tag)
                    i += len(tag)
                    continue
                elif sql[i:i + len(dollar_tag)] == dollar_tag:
                    in_dollar_quote = False
                    current.append(dollar_tag)
                    i += len(dollar_tag)
                    continue

        # String literal ('...' ou "...")
        if (not in_dollar_quote and not in_line_comment and not in_block_comment
                and ch in ("'", '"')):
            if not in_string:
                in_string = True
                string_char = ch
            elif ch == string_char:
                # Escape '' dentro de string
                if i + 1 < len(sql) and sql[i + 1] == string_char:
                    current.append(ch)
                    current.append(sql[i + 1])
                    i += 2
                    continue
                else:
                    in_string = False
            current.append(ch)
            i += 1
            continue

        # Separador de statement
        if (ch == ';' and not in_string and not in_dollar_quote
                and not in_line_comment and not in_block_comment):
            stmt = ''.join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    # Último statement sem ; no final
    last = ''.join(current).strip()
    if last:
        statements.append(last)

    # Filtrar statements vazios
    return [s for s in statements if s.strip()]


def get_migration_files() -> List[Path]:
    """Retorna lista ordenada de arquivos de migração (excluindo rollbacks)"""
    migrations_dir = Path(__file__).parent
    return sorted(
        f for f in migrations_dir.glob("*.sql")
        if '_rollback' not in f.name
    )


def run_migrations() -> None:
    """Executa todas as migrações pendentes"""
    from backend.database.db import db

    logger.info("Verificando migrações pendentes...")

    # Criar tabela de controle de migrações (statement único)
    with db.get_cursor(commit=True) as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # Obter migrações já aplicadas
    applied = db.execute_query(
        "SELECT filename FROM schema_migrations ORDER BY filename"
    )
    applied_filenames = {row['filename'] for row in (applied or [])}

    migration_files = get_migration_files()
    pending_count = 0

    for migration_file in migration_files:
        filename = migration_file.name

        if filename in applied_filenames:
            logger.debug(f"Migração já aplicada: {filename}")
            continue

        logger.info(f"Aplicando migração: {filename}")

        try:
            with open(migration_file, 'r', encoding='utf-8') as f:
                sql = f.read()

            statements = split_sql_statements(sql)
            logger.info(f"  {len(statements)} statements encontrados em {filename}")

            # Executar todos os statements + registro numa única transação
            with db.get_cursor(commit=True) as cursor:
                for idx, stmt in enumerate(statements, 1):
                    logger.debug(f"  [{idx}/{len(statements)}] {stmt[:60].strip()}...")
                    cursor.execute(stmt)

                # Registrar migração como aplicada
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

    result = db.execute_query(
        "SELECT filename FROM schema_migrations ORDER BY applied_at DESC LIMIT 1"
    )

    if not result:
        logger.warning("Nenhuma migração para reverter")
        return

    filename = result[0]['filename']
    logger.warning(f"Revertendo migração: {filename}")

    migrations_dir = Path(__file__).parent
    rollback_file = migrations_dir / filename.replace('.sql', '_rollback.sql')

    if not rollback_file.exists():
        logger.error(f"Arquivo de rollback não encontrado: {rollback_file}")
        return

    try:
        with open(rollback_file, 'r', encoding='utf-8') as f:
            sql = f.read()

        statements = split_sql_statements(sql)

        with db.get_cursor(commit=True) as cursor:
            for stmt in statements:
                cursor.execute(stmt)
            cursor.execute(
                "DELETE FROM schema_migrations WHERE filename = %s",
                (filename,)
            )

        logger.info(f"Migração revertida com sucesso: {filename}")

    except Exception as e:
        logger.error(f"Erro ao reverter migração {filename}: {e}")
        raise
