#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Domain Model
===============================
Modelo de domínio bloqueado

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from backend.database.db import db


class Domain:
    """Modelo de domínio bloqueado"""
    
    def __init__(
        self,
        id: Optional[int] = None,
        domain: str = None,
        added_at: Optional[datetime] = None,
        added_by: Optional[str] = None,
        source: Optional[str] = None,
        source_reference: Optional[str] = None,
        active: bool = True,
        notes: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        self.id = id
        self.domain = domain
        self.added_at = added_at
        self.added_by = added_by
        self.source = source
        self.source_reference = source_reference
        self.active = active
        self.notes = notes
        self.metadata = metadata or {}
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Domain':
        """Cria instância a partir de dicionário"""
        metadata = data.get('metadata', {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        return cls(
            id=data.get('id'),
            domain=data.get('domain'),
            added_at=data.get('added_at'),
            added_by=data.get('added_by'),
            source=data.get('source'),
            source_reference=data.get('source_reference'),
            active=data.get('active', True),
            notes=data.get('notes'),
            metadata=metadata
        )
    
    def to_dict(self) -> Dict:
        """Converte para dicionário"""
        return {
            'id': self.id,
            'domain': self.domain,
            'added_at': self.added_at.isoformat() if self.added_at else None,
            'added_by': self.added_by,
            'source': self.source,
            'source_reference': self.source_reference,
            'active': self.active,
            'notes': self.notes,
            'metadata': self.metadata
        }
    
    @classmethod
    def create(
        cls,
        domain: str,
        added_by: Optional[str] = None,
        source: str = 'manual',
        source_reference: Optional[str] = None,
        notes: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> 'Domain':
        """Cria novo domínio"""
        query = """
        INSERT INTO domains (domain, added_by, source, source_reference, notes, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, domain, added_at, added_by, source, source_reference, active, notes, metadata
        """
        
        metadata_json = json.dumps(metadata) if metadata else '{}'
        
        result = db.execute_query(
            query,
            (domain, added_by, source, source_reference, notes, metadata_json)
        )
        
        return cls.from_dict(result[0])
    
    @classmethod
    def bulk_create(
        cls,
        domains: List[str],
        added_by: Optional[str] = None,
        source: str = 'bulk',
        source_reference: Optional[str] = None
    ) -> Tuple[int, int]:
        """
        Cria múltiplos domínios de uma vez
        Retorna: (quantidade_adicionada, quantidade_duplicada)
        """
        query = """
        INSERT INTO domains (domain, added_by, source, source_reference)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (domain) DO NOTHING
        """
        
        params_list = [
            (domain.strip().lower(), added_by, source, source_reference)
            for domain in domains
            if domain.strip()
        ]
        
        total = len(params_list)
        added = db.execute_many(query, params_list)
        duplicated = total - added
        
        return added, duplicated
    
    @classmethod
    def get_by_id(cls, domain_id: int) -> Optional['Domain']:
        """Busca domínio por ID"""
        query = "SELECT * FROM domains WHERE id = %s"
        result = db.execute_query(query, (domain_id,))
        
        if result:
            return cls.from_dict(result[0])
        return None
    
    @classmethod
    def get_by_domain(cls, domain: str) -> Optional['Domain']:
        """Busca domínio por nome"""
        query = "SELECT * FROM domains WHERE domain = %s"
        result = db.execute_query(query, (domain.lower(),))
        
        if result:
            return cls.from_dict(result[0])
        return None
    
    @classmethod
    def exists(cls, domain: str) -> bool:
        """Verifica se domínio existe"""
        query = "SELECT COUNT(*) as count FROM domains WHERE domain = %s"
        result = db.execute_query(query, (domain.lower(),))
        return result[0]['count'] > 0
    
    @classmethod
    def get_all(
        cls,
        active_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0,
        search: Optional[str] = None
    ) -> List['Domain']:
        """Lista domínios com filtros"""
        conditions = []
        params = []
        
        if active_only:
            conditions.append("active = TRUE")
        
        if search:
            conditions.append("domain ILIKE %s")
            params.append(f"%{search}%")
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"""
        SELECT * FROM domains
        {where_clause}
        ORDER BY added_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"
        
        result = db.execute_query(query, tuple(params) if params else None)
        return [cls.from_dict(row) for row in result]
    
    @classmethod
    def count(cls, active_only: bool = True, search: Optional[str] = None) -> int:
        """Conta total de domínios"""
        conditions = []
        params = []
        
        if active_only:
            conditions.append("active = TRUE")
        
        if search:
            conditions.append("domain ILIKE %s")
            params.append(f"%{search}%")
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"SELECT COUNT(*) as count FROM domains {where_clause}"
        result = db.execute_query(query, tuple(params) if params else None)
        return result[0]['count']
    
    @classmethod
    def get_active_domains_list(cls) -> List[str]:
        """Retorna lista simples de domínios ativos (para cache)"""
        query = "SELECT domain FROM domains WHERE active = TRUE ORDER BY domain"
        result = db.execute_query(query)
        return [row['domain'] for row in result]
    
    def update(self, **kwargs) -> bool:
        """Atualiza dados do domínio"""
        allowed_fields = ['active', 'notes', 'metadata']
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
        query = f"UPDATE domains SET {', '.join(updates)} WHERE id = %s"
        
        db.execute_query(query, tuple(params), fetch=False)
        
        # Recarregar dados
        updated = self.get_by_id(self.id)
        if updated:
            self.__dict__.update(updated.__dict__)
            return True
        
        return False
    
    def deactivate(self) -> bool:
        """Desativa domínio (soft delete)"""
        return self.update(active=False)
    
    def activate(self) -> bool:
        """Ativa domínio"""
        return self.update(active=True)
    
    def delete(self) -> bool:
        """Remove domínio permanentemente"""
        query = "DELETE FROM domains WHERE id = %s"
        db.execute_query(query, (self.id,), fetch=False)
        return True
    
    def __repr__(self) -> str:
        status = "ativo" if self.active else "inativo"
        return f"<Domain {self.domain} ({status})>"
