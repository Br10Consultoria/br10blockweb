#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - User Model
=============================
Modelo de usuário do sistema

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import hashlib
from datetime import datetime
from typing import Dict, List, Optional

from backend.database.db import db


class User:
    """Modelo de usuário"""
    
    def __init__(
        self,
        id: Optional[int] = None,
        username: str = None,
        password_hash: str = None,
        role: str = 'user',
        email: Optional[str] = None,
        active: bool = True,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.email = email
        self.active = active
        self.created_at = created_at
        self.updated_at = updated_at
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Gera hash SHA-256 da senha"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verifica se a senha corresponde ao hash"""
        return User.hash_password(password) == password_hash
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        """Cria instância a partir de dicionário"""
        return cls(
            id=data.get('id'),
            username=data.get('username'),
            password_hash=data.get('password_hash'),
            role=data.get('role', 'user'),
            email=data.get('email'),
            active=data.get('active', True),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def to_dict(self, include_password: bool = False) -> Dict:
        """Converte para dicionário"""
        data = {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'email': self.email,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_password:
            data['password_hash'] = self.password_hash
        
        return data
    
    @classmethod
    def create(cls, username: str, password: str, role: str = 'user', email: Optional[str] = None) -> 'User':
        """Cria novo usuário"""
        password_hash = cls.hash_password(password)
        
        query = """
        INSERT INTO users (username, password_hash, role, email)
        VALUES (%s, %s, %s, %s)
        RETURNING id, username, password_hash, role, email, active, created_at, updated_at
        """
        
        result = db.execute_query(query, (username, password_hash, role, email))
        return cls.from_dict(result[0])
    
    @classmethod
    def get_by_id(cls, user_id: int) -> Optional['User']:
        """Busca usuário por ID"""
        query = "SELECT * FROM users WHERE id = %s"
        result = db.execute_query(query, (user_id,))
        
        if result:
            return cls.from_dict(result[0])
        return None
    
    @classmethod
    def get_by_username(cls, username: str) -> Optional['User']:
        """Busca usuário por username"""
        query = "SELECT * FROM users WHERE username = %s"
        result = db.execute_query(query, (username,))
        
        if result:
            return cls.from_dict(result[0])
        return None
    
    @classmethod
    def authenticate(cls, username: str, password: str) -> Optional['User']:
        """Autentica usuário"""
        user = cls.get_by_username(username)
        
        if user and user.active and cls.verify_password(password, user.password_hash):
            return user
        
        return None
    
    @classmethod
    def get_all(cls, active_only: bool = True) -> List['User']:
        """Lista todos os usuários"""
        if active_only:
            query = "SELECT * FROM users WHERE active = TRUE ORDER BY username"
        else:
            query = "SELECT * FROM users ORDER BY username"
        
        result = db.execute_query(query)
        return [cls.from_dict(row) for row in result]
    
    def update(self, **kwargs) -> bool:
        """Atualiza dados do usuário"""
        allowed_fields = ['email', 'role', 'active']
        updates = []
        params = []
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f"{field} = %s")
                params.append(value)
        
        if not updates:
            return False
        
        params.append(self.id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
        
        db.execute_query(query, tuple(params), fetch=False)
        
        # Recarregar dados
        updated = self.get_by_id(self.id)
        if updated:
            self.__dict__.update(updated.__dict__)
            return True
        
        return False
    
    def change_password(self, new_password: str) -> bool:
        """Altera senha do usuário"""
        new_hash = self.hash_password(new_password)
        
        query = "UPDATE users SET password_hash = %s WHERE id = %s"
        db.execute_query(query, (new_hash, self.id), fetch=False)
        
        self.password_hash = new_hash
        return True
    
    def delete(self) -> bool:
        """Remove usuário (soft delete)"""
        query = "UPDATE users SET active = FALSE WHERE id = %s"
        db.execute_query(query, (self.id,), fetch=False)
        self.active = False
        return True
    
    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"
