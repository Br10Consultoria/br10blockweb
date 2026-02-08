#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Database Initialization Script
================================================
Script para inicializar o banco de dados

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import sys
from pathlib import Path

# Adicionar backend ao path
sys.path.insert(0, str(Path(__file__).parent))

from backend.database.db import db
from backend.models.user import User

def init_database():
    """Inicializa o banco de dados"""
    print("🔧 Inicializando banco de dados...")
    
    try:
        # Executar migrações
        db.run_migrations()
        print("✅ Migrações executadas com sucesso")
        
        # Criar usuário admin padrão
        print("\n👤 Criando usuário administrador...")
        username = input("Username (padrão: admin): ").strip() or "admin"
        password = input("Senha: ").strip()
        
        if not password:
            print("❌ Senha não pode ser vazia")
            return
        
        # Verificar se já existe
        if User.get_by_username(username):
            print(f"⚠️  Usuário '{username}' já existe")
            return
        
        # Criar usuário
        user = User.create(username, password, role="admin")
        print(f"✅ Usuário '{username}' criado com sucesso")
        print(f"   ID: {user.id}")
        print(f"   Role: {user.role}")
        
        print("\n🎉 Banco de dados inicializado com sucesso!")
        print(f"\n🌐 Acesse: http://localhost:5000")
        print(f"   Username: {username}")
        print(f"   Senha: (a que você definiu)")
        
    except Exception as e:
        print(f"❌ Erro ao inicializar banco: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    init_database()
