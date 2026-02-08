#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Domain History Model
=======================================
Modelo de histórico de domínios

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

from backend.database.db import db


class DomainHistory:
    """Modelo de histórico de domínio"""
    
    def __init__(
        self,
        id: Optional[int] = None,
        domain_id: Optional[int] = None,
        domain: str = None,
        action: str = None,
        performed_by: Optional[str] = None,
        old_value: Optional[Dict] = None,
        new_value: Optional[Dict] = None,
        performed_at: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ):
        self.id = id
        self.domain_id = domain_id
        self.domain = domain
        self.action = action
        self.performed_by = performed_by
        self.old_value = old_value
        self.new_value = new_value
        self.performed_at = performed_at
        self.metadata = metadata or {}
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DomainHistory':
        """Cria instância a partir de dicionário"""
        old_value = data.get('old_value', {})
        if isinstance(old_value, str):
            old_value = json.loads(old_value) if old_value else {}
        
        new_value = data.get('new_value', {})
        if isinstance(new_value, str):
            new_value = json.loads(new_value) if new_value else {}
        
        metadata = data.get('metadata', {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        return cls(
            id=data.get('id'),
            domain_id=data.get('domain_id'),
            domain=data.get('domain'),
            action=data.get('action'),
            performed_by=data.get('performed_by'),
            old_value=old_value,
            new_value=new_value,
            performed_at=data.get('performed_at'),
            metadata=metadata
        )
    
    def to_dict(self) -> Dict:
        """Converte para dicionário"""
        return {
            'id': self.id,
            'domain_id': self.domain_id,
            'domain': self.domain,
            'action': self.action,
            'performed_by': self.performed_by,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'performed_at': self.performed_at.isoformat() if self.performed_at else None,
            'metadata': self.metadata
        }
    
    @classmethod
    def create(
        cls,
        domain_id: Optional[int],
        domain: str,
        action: str,
        performed_by: Optional[str] = None,
        old_value: Optional[Dict] = None,
        new_value: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> 'DomainHistory':
        """Cria novo registro de histórico"""
        query = """
        INSERT INTO domain_history (domain_id, domain, action, performed_by, old_value, new_value, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, domain_id, domain, action, performed_by, old_value, new_value, performed_at, metadata
        """
        
        old_value_json = json.dumps(old_value) if old_value else None
        new_value_json = json.dumps(new_value) if new_value else None
        metadata_json = json.dumps(metadata) if metadata else '{}'
        
        result = db.execute_query(
            query,
            (domain_id, domain, action, performed_by, old_value_json, new_value_json, metadata_json)
        )
        
        return cls.from_dict(result[0])
    
    @classmethod
    def log_addition(
        cls,
        domain_id: int,
        domain: str,
        performed_by: Optional[str] = None,
        source: Optional[str] = None
    ) -> 'DomainHistory':
        """Registra adição de domínio"""
        metadata = {'source': source} if source else {}
        return cls.create(
            domain_id=domain_id,
            domain=domain,
            action='added',
            performed_by=performed_by,
            new_value={'active': True},
            metadata=metadata
        )
    
    @classmethod
    def log_removal(
        cls,
        domain_id: int,
        domain: str,
        performed_by: Optional[str] = None
    ) -> 'DomainHistory':
        """Registra remoção de domínio"""
        return cls.create(
            domain_id=domain_id,
            domain=domain,
            action='removed',
            performed_by=performed_by,
            old_value={'active': True},
            new_value={'active': False}
        )
    
    @classmethod
    def log_activation(
        cls,
        domain_id: int,
        domain: str,
        performed_by: Optional[str] = None
    ) -> 'DomainHistory':
        """Registra ativação de domínio"""
        return cls.create(
            domain_id=domain_id,
            domain=domain,
            action='activated',
            performed_by=performed_by,
            old_value={'active': False},
            new_value={'active': True}
        )
    
    @classmethod
    def log_deactivation(
        cls,
        domain_id: int,
        domain: str,
        performed_by: Optional[str] = None
    ) -> 'DomainHistory':
        """Registra desativação de domínio"""
        return cls.create(
            domain_id=domain_id,
            domain=domain,
            action='deactivated',
            performed_by=performed_by,
            old_value={'active': True},
            new_value={'active': False}
        )
    
    @classmethod
    def get_by_domain_id(cls, domain_id: int, limit: int = 50) -> List['DomainHistory']:
        """Lista histórico de um domínio"""
        query = """
        SELECT * FROM domain_history
        WHERE domain_id = %s
        ORDER BY performed_at DESC
        LIMIT %s
        """
        
        result = db.execute_query(query, (domain_id, limit))
        return [cls.from_dict(row) for row in result]
    
    @classmethod
    def get_by_domain_name(cls, domain: str, limit: int = 50) -> List['DomainHistory']:
        """Lista histórico de um domínio por nome"""
        query = """
        SELECT * FROM domain_history
        WHERE domain = %s
        ORDER BY performed_at DESC
        LIMIT %s
        """
        
        result = db.execute_query(query, (domain, limit))
        return [cls.from_dict(row) for row in result]
    
    @classmethod
    def get_recent(cls, limit: int = 100) -> List['DomainHistory']:
        """Lista histórico recente"""
        query = """
        SELECT * FROM domain_history
        ORDER BY performed_at DESC
        LIMIT %s
        """
        
        result = db.execute_query(query, (limit,))
        return [cls.from_dict(row) for row in result]
    
    @classmethod
    def get_by_action(cls, action: str, limit: int = 100) -> List['DomainHistory']:
        """Lista histórico por tipo de ação"""
        query = """
        SELECT * FROM domain_history
        WHERE action = %s
        ORDER BY performed_at DESC
        LIMIT %s
        """
        
        result = db.execute_query(query, (action, limit))
        return [cls.from_dict(row) for row in result]
    
    def __repr__(self) -> str:
        return f"<DomainHistory {self.domain} action={self.action}>"
