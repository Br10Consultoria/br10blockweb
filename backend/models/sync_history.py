#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Sync History Model
=====================================
Modelo de histórico de sincronizações

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

from backend.database.db import db


class SyncHistory:
    """Modelo de histórico de sincronização"""
    
    def __init__(
        self,
        id: Optional[int] = None,
        client_id: Optional[int] = None,
        domains_sent: int = 0,
        domains_applied: int = 0,
        status: str = 'pending',
        message: Optional[str] = None,
        error_details: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        synced_at: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ):
        self.id = id
        self.client_id = client_id
        self.domains_sent = domains_sent
        self.domains_applied = domains_applied
        self.status = status
        self.message = message
        self.error_details = error_details
        self.duration_seconds = duration_seconds
        self.synced_at = synced_at
        self.metadata = metadata or {}
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SyncHistory':
        """Cria instância a partir de dicionário"""
        metadata = data.get('metadata', {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        return cls(
            id=data.get('id'),
            client_id=data.get('client_id'),
            domains_sent=data.get('domains_sent', 0),
            domains_applied=data.get('domains_applied', 0),
            status=data.get('status', 'pending'),
            message=data.get('message'),
            error_details=data.get('error_details'),
            duration_seconds=data.get('duration_seconds'),
            synced_at=data.get('synced_at'),
            metadata=metadata
        )
    
    def to_dict(self) -> Dict:
        """Converte para dicionário"""
        return {
            'id': self.id,
            'client_id': self.client_id,
            'domains_sent': self.domains_sent,
            'domains_applied': self.domains_applied,
            'status': self.status,
            'message': self.message,
            'error_details': self.error_details,
            'duration_seconds': self.duration_seconds,
            'synced_at': self.synced_at.isoformat() if self.synced_at else None,
            'metadata': self.metadata
        }
    
    @classmethod
    def create(
        cls,
        client_id: int,
        domains_sent: int = 0,
        status: str = 'pending',
        message: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> 'SyncHistory':
        """Cria novo registro de sincronização"""
        query = """
        INSERT INTO sync_history (client_id, domains_sent, status, message, metadata)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, client_id, domains_sent, domains_applied, status, message, 
                  error_details, duration_seconds, synced_at, metadata
        """
        
        metadata_json = json.dumps(metadata) if metadata else '{}'
        
        result = db.execute_query(
            query,
            (client_id, domains_sent, status, message, metadata_json)
        )
        
        return cls.from_dict(result[0])
    
    @classmethod
    def get_by_id(cls, sync_id: int) -> Optional['SyncHistory']:
        """Busca sincronização por ID"""
        query = "SELECT * FROM sync_history WHERE id = %s"
        result = db.execute_query(query, (sync_id,))
        
        if result:
            return cls.from_dict(result[0])
        return None
    
    @classmethod
    def get_by_client(
        cls,
        client_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List['SyncHistory']:
        """Lista sincronizações de um cliente"""
        query = """
        SELECT * FROM sync_history
        WHERE client_id = %s
        ORDER BY synced_at DESC
        LIMIT %s OFFSET %s
        """
        
        result = db.execute_query(query, (client_id, limit, offset))
        return [cls.from_dict(row) for row in result]
    
    @classmethod
    def get_recent(cls, limit: int = 100) -> List['SyncHistory']:
        """Lista sincronizações recentes"""
        query = """
        SELECT * FROM sync_history
        ORDER BY synced_at DESC
        LIMIT %s
        """
        
        result = db.execute_query(query, (limit,))
        return [cls.from_dict(row) for row in result]
    
    def update(self, **kwargs) -> bool:
        """Atualiza dados da sincronização"""
        allowed_fields = ['domains_applied', 'status', 'message', 
                         'error_details', 'duration_seconds', 'metadata']
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
        query = f"UPDATE sync_history SET {', '.join(updates)} WHERE id = %s"
        
        db.execute_query(query, tuple(params), fetch=False)
        
        # Recarregar dados
        updated = self.get_by_id(self.id)
        if updated:
            self.__dict__.update(updated.__dict__)
            return True
        
        return False
    
    def mark_success(self, domains_applied: int, duration_seconds: int) -> bool:
        """Marca sincronização como sucesso"""
        return self.update(
            status='success',
            domains_applied=domains_applied,
            duration_seconds=duration_seconds,
            message='Sincronização concluída com sucesso'
        )
    
    def mark_failed(self, error_message: str, duration_seconds: Optional[int] = None) -> bool:
        """Marca sincronização como falha"""
        return self.update(
            status='failed',
            error_details=error_message,
            duration_seconds=duration_seconds,
            message='Falha na sincronização'
        )
    
    def __repr__(self) -> str:
        return f"<SyncHistory client_id={self.client_id} status={self.status}>"
