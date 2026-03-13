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
import logging
import secrets
from datetime import datetime
from typing import Dict, List, Optional

from backend.database.db import db

logger = logging.getLogger(__name__)


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
        
        # Converter ip_address para string (PostgreSQL INET retorna como string, mas garantir)
        ip_addr = data.get('ip_address')
        if ip_addr is not None:
            ip_addr = str(ip_addr)
        
        return cls(
            id=data.get('id'),
            name=data.get('name'),
            api_key=data.get('api_key'),
            ip_address=ip_addr,
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
        
        # Tratar ip_address vazio como None para compatibilidade com tipo INET do PostgreSQL
        if ip_address is not None and str(ip_address).strip() == '':
            ip_address = None
        
        metadata_json = json.dumps(metadata) if metadata else '{}'
        
        logger.info(f"Criando cliente DNS: name={name}, ip_address={ip_address}")
        
        query = """
        INSERT INTO dns_clients (name, api_key, description, ip_address, metadata)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, name, api_key, ip_address, description, status, last_sync, 
                  last_heartbeat, domains_count, active, created_at, updated_at, metadata
        """
        
        try:
            result = db.execute_query(
                query,
                (name, api_key, description, ip_address, metadata_json)
            )
        except Exception as e:
            logger.error(f"Erro ao executar INSERT de cliente DNS: {e}")
            raise
        
        if not result:
            logger.error(f"INSERT de cliente DNS não retornou dados. Query executada mas sem RETURNING.")
            raise Exception('Falha ao criar cliente: nenhum resultado retornado do banco de dados')
        
        logger.info(f"Cliente DNS criado com sucesso: id={result[0].get('id')}, name={result[0].get('name')}")
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
        logger.info(f"DNSClient.get_all(active_only={active_only}): {len(result)} resultados")
        return [cls.from_dict(row) for row in result]
    
    @classmethod
    def count(cls, active_only: bool = True) -> int:
        """Conta total de clientes"""
        if active_only:
            query = "SELECT COUNT(*) as count FROM dns_clients WHERE active = TRUE"
        else:
            query = "SELECT COUNT(*) as count FROM dns_clients"
        
        result = db.execute_query(query)
        count_val = result[0]['count'] if result else 0
        logger.info(f"DNSClient.count(active_only={active_only}): {count_val}")
        return count_val
    
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
    
    def update_sync_status(self, domains_count: int, status: str = 'success', unbound_status: str = None) -> bool:
        """Atualiza status de sincronização"""
        # Determinar status geral e status granulares
        if status == 'success':
            client_status = 'online'
            sync_ok = True
            unbound_ok = True
        elif status == 'partial':
            client_status = 'online'  # sincronizou, mas Unbound não recarregou
            sync_ok = True
            unbound_ok = False
        else:  # failed
            client_status = 'error'
            sync_ok = False
            unbound_ok = False
        
        # Atualizar metadata com status granulares
        current_metadata = self.metadata or {}
        current_metadata['sync_status'] = 'ok' if sync_ok else 'error'
        current_metadata['unbound_status'] = 'ok' if unbound_ok else 'down'
        if unbound_status:
            current_metadata['unbound_status'] = unbound_status
        current_metadata['last_sync_result'] = status
        
        return self.update(
            last_sync=datetime.now(),
            domains_count=domains_count,
            status=client_status,
            metadata=current_metadata
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
