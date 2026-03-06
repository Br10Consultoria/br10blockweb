#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de inicialização DIRETO — usa psycopg2 sem pool/abstração.
Resolve definitivamente o problema de commit das migrations.
"""
import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import List

import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def get_db_config():
    return dict(
        host=os.environ.get('DB_HOST', 'postgres'),
        port=int(os.environ.get('DB_PORT', 5432)),
        dbname=os.environ.get('DB_NAME', 'br10blockweb'),
        user=os.environ.get('DB_USER', 'br10user'),
        password=os.environ.get('DB_PASSWORD', ''),
    )


def split_sql(sql: str) -> List[str]:
    stmts, cur, i = [], [], 0
    in_str = in_dq = in_lc = in_bc = False
    sc = dq_tag = ''
    while i < len(sql):
        ch = sql[i]
        if not in_str and not in_dq and not in_bc and ch == '-' and i+1 < len(sql) and sql[i+1] == '-':
            in_lc = True; i += 2; continue
        if in_lc:
            if ch == '\n': in_lc = False
            i += 1; continue
        if not in_str and not in_dq and not in_lc and ch == '/' and i+1 < len(sql) and sql[i+1] == '*':
            in_bc = True; i += 2; continue
        if in_bc:
            if ch == '*' and i+1 < len(sql) and sql[i+1] == '/': in_bc = False; i += 2
            else: i += 1
            continue
        if not in_str and not in_lc and not in_bc and ch == '$':
            m = re.match(r'\$([^$]*)\$', sql[i:])
            if m:
                tag = m.group(0)
                if not in_dq: in_dq = True; dq_tag = tag; cur.append(tag); i += len(tag); continue
                elif sql[i:i+len(dq_tag)] == dq_tag: in_dq = False; cur.append(dq_tag); i += len(dq_tag); continue
        if not in_dq and not in_lc and not in_bc and ch in ("'", '"'):
            if not in_str: in_str = True; sc = ch
            elif ch == sc:
                if i+1 < len(sql) and sql[i+1] == sc: cur.append(ch); cur.append(sql[i+1]); i += 2; continue
                else: in_str = False
            cur.append(ch); i += 1; continue
        if ch == ';' and not in_str and not in_dq and not in_lc and not in_bc:
            s = ''.join(cur).strip()
            if s: stmts.append(s)
            cur = []; i += 1; continue
        cur.append(ch); i += 1
    last = ''.join(cur).strip()
    if last: stmts.append(last)
    return [s for s in stmts if s.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--admin-user', default='admin')
    parser.add_argument('--admin-pass', default='admin123')
    args = parser.parse_args()

    print("🔧 Inicializando banco de dados (modo direto)...")
    cfg = get_db_config()
    print(f"   Conectando em {cfg['host']}:{cfg['port']}/{cfg['dbname']} como {cfg['user']}")

    try:
        conn = psycopg2.connect(cursor_factory=RealDictCursor, **cfg)
        conn.autocommit = False
        print("✅ Conexão estabelecida")
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        sys.exit(1)

    try:
        # 1. Criar tabela de controle de migrations
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id SERIAL PRIMARY KEY,
                    filename VARCHAR(255) UNIQUE NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()

        # 2. Verificar migrations aplicadas
        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM schema_migrations")
            applied = {r['filename'] for r in cur.fetchall()}

        # 3. Executar migrations
        migrations_dir = Path('/app/backend/database/migrations')
        if not migrations_dir.exists():
            migrations_dir = Path(__file__).parent / 'backend' / 'database' / 'migrations'

        sql_files = sorted(migrations_dir.glob('*.sql'))
        print(f"📦 {len(sql_files)} arquivo(s) de migration encontrado(s)")

        for sql_file in sql_files:
            fname = sql_file.name
            if fname in applied:
                print(f"   [SKIP] {fname}")
                continue

            print(f"   [EXEC] {fname}")
            sql = sql_file.read_text(encoding='utf-8')
            stmts = split_sql(sql)
            print(f"          {len(stmts)} statements")

            with conn.cursor() as cur:
                for idx, stmt in enumerate(stmts, 1):
                    preview = stmt.strip()[:70].replace('\n', ' ')
                    print(f"          [{idx:2d}/{len(stmts)}] {preview}")
                    cur.execute(stmt)
                cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (fname,))
            conn.commit()
            print(f"   [OK]   {fname} ✅")

        print("✅ Migrações executadas com sucesso")

        # 4. Verificar se tabela users existe
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as n FROM information_schema.tables WHERE table_name='users'")
            r = cur.fetchone()
            if r['n'] == 0:
                print("❌ ERRO: tabela 'users' não foi criada!")
                sys.exit(1)
            print("✅ Tabela 'users' verificada")

        # 5. Criar usuário admin
        print(f"👤 Configurando usuário '{args.admin_user}'...")
        pw_hash = generate_password_hash(args.admin_pass)

        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (args.admin_user,))
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    "UPDATE users SET password_hash=%s, role='admin', active=TRUE WHERE username=%s",
                    (pw_hash, args.admin_user)
                )
                print(f"   Usuário '{args.admin_user}' atualizado")
            else:
                cur.execute(
                    "INSERT INTO users (username, password_hash, role, email, active) VALUES (%s,%s,'admin',%s,TRUE)",
                    (args.admin_user, pw_hash, f"{args.admin_user}@br10.local")
                )
                print(f"   Usuário '{args.admin_user}' criado")
        conn.commit()

        print()
        print("🎉 Banco de dados inicializado com sucesso!")
        print(f"   Login: {args.admin_user} / {args.admin_pass}")

    except Exception as e:
        conn.rollback()
        print(f"❌ Erro: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
