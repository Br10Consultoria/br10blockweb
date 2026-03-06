#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Database Initialization Script
================================================
Script para inicializar o banco de dados e criar o usuário admin.
Pode ser executado diretamente ou via Docker entrypoint.

Uso:
    python init_db.py                          # interativo
    python init_db.py --admin-user admin --admin-pass SENHA
    python init_db.py --skip-user              # só roda migrações

Autor: BR10 Team
Versão: 3.0.1
"""
import sys
import argparse
from pathlib import Path

# Adicionar raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).parent))


def init_database(admin_user: str = None, admin_pass: str = None, skip_user: bool = False):
    """Inicializa o banco de dados."""
    print("🔧 Inicializando banco de dados...")

    try:
        # Importar após configurar o path
        from backend.database.db import db
        from backend.database.migrations import run_migrations
        from backend.models.user import User

        # Testar conexão
        if not db.test_connection():
            print("❌ Não foi possível conectar ao banco de dados")
            print("   Verifique as variáveis DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD")
            sys.exit(1)

        print("✅ Conexão com banco de dados estabelecida")

        # Executar migrações
        run_migrations()
        print("✅ Migrações executadas com sucesso")

        if skip_user:
            print("⏭️  Criação de usuário ignorada (--skip-user)")
            print("\n🎉 Banco de dados inicializado com sucesso!")
            return

        # Criar usuário admin
        print("\n👤 Configurando usuário administrador...")

        if not admin_user:
            admin_user = input("Username (padrão: admin): ").strip() or "admin"
        if not admin_pass:
            import getpass
            admin_pass = getpass.getpass("Senha: ").strip()

        if not admin_pass:
            print("❌ Senha não pode ser vazia")
            sys.exit(1)

        # Verificar se já existe
        existing = User.get_by_username(admin_user)
        if existing:
            print(f"⚠️  Usuário '{admin_user}' já existe — pulando criação")
        else:
            user = User.create(admin_user, admin_pass, role="admin")
            print(f"✅ Usuário '{admin_user}' criado com sucesso (ID: {user.id})")

        print("\n🎉 Banco de dados inicializado com sucesso!")
        print(f"   Acesse o painel e faça login com o usuário '{admin_user}'")

    except Exception as e:
        print(f"❌ Erro ao inicializar banco: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inicializa o banco de dados BR10 Block Web")
    parser.add_argument("--admin-user", default=None, help="Nome do usuário admin")
    parser.add_argument("--admin-pass", default=None, help="Senha do usuário admin")
    parser.add_argument("--skip-user", action="store_true", help="Não criar usuário admin")
    args = parser.parse_args()

    init_database(
        admin_user=args.admin_user,
        admin_pass=args.admin_pass,
        skip_user=args.skip_user,
    )
