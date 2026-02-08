#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - DNS Client Model
===================================
Modelo de cliente DNS

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import json
import secrets
from datetime import datetime
from typing import Dict, List, Optional

from backend.database.db import db


class DNSClient:
    """Modelo de cliente DNS"""
    
    def __init__(
        self,
        id: Optional[int] = None,
        name: str = None,
        api_key: str = None,
        ip_address: Optional[str] = None,
        description: Optional[str] = None,
        status: str = 'offline',
        last_sync: Optional[datetime] = None,
        last_heartbeat: Optional[datetime] = None,
        domains_count: int = 0,
        active: bool = True,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ):
        self.id = id
        self.name = name
        self.api_key = api_key
        self.ip_address = ip_address
        self.description = description
        self.status = status
        self.last_sync = last_sync
        self.last_heartbeat = last_heartbeat
        self.domains_count = domains_count
        self.active = active
        self.created_at = created_at
        self.updated_at = updated_at
        self.metadata = metadata or {}
    
    @staticmethod
    def generate_api_key() -> str:
        """Gera uma API key única"""
        return secrets.token_urlsafe(32)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DNSClient':
        """Cria instância a partir de dicionário"""
        metadata = data.get('metadata', {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        return cls(
            id=data.get('id'),
            name=data.get('name'),
            api_key=data.get('api_key'),
            ip_address=data.get('ip_address'),
            description=data.get('description'),
            status=data.get('status', 'offline'),
            last_sync=data.get('last_sync'),
            last_heartbeat=data.get('last_heartbeat'),
            domains_count=data.get('domains_count', 0),
            active=data.get('active', True),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            metadata=metadata
        )
    
    def to_dict(self, include_api_key: bool = False) -> Dict:
        """Converte para dicionário"""
        data = {
            'id': self.id,
            'name': self.name,
            'ip_address': self.ip_address,
            'description': self.description,
            'status': self.status,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'domains_count': self.domains_count,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.metadata
        }
        
        if include_api_key:
            data['api_key'] = self.api_key
        
        return data
    
    @classmethod
    def create(
        cls,
        name: str,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> 'DNSClient':
        """Cria novo cliente DNS"""
        api_key = cls.generate_api_key()
        
        query = """
        INSERT INTO dns_clients (name, api_key, description, ip_address, metadata)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, name, api_key, ip_address, description, status, last_sync, 
                  last_heartbeat, domains_count, active, created_at, updated_at, metadata
        """
        
        metadata_json = json.dumps(metadata) if metadata else '{}'
        
        result = db.execute_query(
            query,
            (name, api_key, description, ip_address, metadata_json)
        )
        
        return cls.from_dict(result[0])
    
    @classmethod
    def get_by_id(cls, client_id: int) -> Optional['DNSClient']:
        """Busca cliente por ID"""
        query = "SELECT * FROM dns_clients WHERE id = %s"
        result = db.execute_query(query, (client_id,))
        
        if result:
            return cls.from_dict(result[0])
        return None
    
    @classmethod
    def get_by_api_key(cls, api_key: str) -> Optional['DNSClient']:
        """Busca cliente por API key"""
        query = "SELECT * FROM dns_clients WHERE api_key = %s AND active = TRUE"
        result = db.execute_query(query, (api_key,))
        
        if result:
            return cls.from_dict(result[0])
        return None
    
    @classmethod
    def get_all(cls, active_only: bool = True) -> List['DNSClient']:
        """Lista todos os clientes"""
        if active_only:
            query = "SELECT * FROM dns_clients WHERE active = TRUE ORDER BY name"
        else:
            query = "SELECT * FROM dns_clients ORDER BY name"
        
        result = db.execute_query(query)
        return [cls.from_dict(row) for row in result]
    
    @classmethod
    def count(cls, active_only: bool = True) -> int:
        """Conta total de clientes"""
        if active_only:
            query = "SELECT COUNT(*) as count FROM dns_clients WHERE active = TRUE"
        else:
            query = "SELECT COUNT(*) as count FROM dns_clients"
        
        result = db.execute_query(query)
        return result[0]['count']
    
    def update(self, **kwargs) -> bool:
        """Atualiza dados do cliente"""
        allowed_fields = ['name', 'description', 'ip_address', 'status', 
                         'last_sync', 'last_heartbeat', 'domains_count', 
                         'active', 'metadata']
        updates = []
        params = []
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                if field == 'metadata':
                    value = json.dumps(value)
                updates.append(f"{field} = %s")
                params.append(value)
        
        if not updates:
            return False
        
        params.append(self.id)
        query = f"UPDATE dns_clients SET {', '.join(updates)} WHERE id = %s"
        
        db.execute_query(query, tuple(params), fetch=False)
        
        # Recarregar dados
        updated = self.get_by_id(self.id)
        if updated:
            self.__dict__.update(updated.__dict__)
            return True
        
        return False
    
    def update_heartbeat(self) -> bool:
        """Atualiza timestamp de heartbeat"""
        return self.update(
            last_heartbeat=datetime.now(),
            status='online'
        )
    
    def update_sync_status(self, domains_count: int, status: str = 'success') -> bool:
        """Atualiza status de sincronização"""
        return self.update(
            last_sync=datetime.now(),
            domains_count=domains_count,
            status='online' if status == 'success' else 'error'
        )
    
    def regenerate_api_key(self) -> str:
        """Gera nova API key"""
        new_key = self.generate_api_key()
        self.update(api_key=new_key)
        self.api_key = new_key
        return new_key
    
    def deactivate(self) -> bool:
        """Desativa cliente"""
        return self.update(active=False, status='offline')
    
    def activate(self) -> bool:
        """Ativa cliente"""
        return self.update(active=True)
    
    def delete(self) -> bool:
        """Remove cliente permanentemente"""
        query = "DELETE FROM dns_clients WHERE id = %s"
        db.execute_query(query, (self.id,), fetch=False)
        return True
    
    def __repr__(self) -> str:
        return f"<DNSClient {self.name} ({self.status})>"
