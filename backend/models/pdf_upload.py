#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - PDF Upload Model
===================================
Modelo de upload de PDF

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

from backend.database.db import db


class PDFUpload:
    """Modelo de upload de PDF"""
    
    def __init__(
        self,
        id: Optional[int] = None,
        filename: str = None,
        original_filename: str = None,
        file_size: Optional[int] = None,
        file_hash: Optional[str] = None,
        domains_extracted: int = 0,
        domains_added: int = 0,
        domains_duplicated: int = 0,
        uploaded_by: Optional[str] = None,
        uploaded_at: Optional[datetime] = None,
        processed: bool = False,
        processing_error: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        self.id = id
        self.filename = filename
        self.original_filename = original_filename
        self.file_size = file_size
        self.file_hash = file_hash
        self.domains_extracted = domains_extracted
        self.domains_added = domains_added
        self.domains_duplicated = domains_duplicated
        self.uploaded_by = uploaded_by
        self.uploaded_at = uploaded_at
        self.processed = processed
        self.processing_error = processing_error
        self.metadata = metadata or {}
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PDFUpload':
        """Cria instância a partir de dicionário"""
        metadata = data.get('metadata', {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        return cls(
            id=data.get('id'),
            filename=data.get('filename'),
            original_filename=data.get('original_filename'),
            file_size=data.get('file_size'),
            file_hash=data.get('file_hash'),
            domains_extracted=data.get('domains_extracted', 0),
            domains_added=data.get('domains_added', 0),
            domains_duplicated=data.get('domains_duplicated', 0),
            uploaded_by=data.get('uploaded_by'),
            uploaded_at=data.get('uploaded_at'),
            processed=data.get('processed', False),
            processing_error=data.get('processing_error'),
            metadata=metadata
        )
    
    def to_dict(self) -> Dict:
        """Converte para dicionário"""
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'file_hash': self.file_hash,
            'domains_extracted': self.domains_extracted,
            'domains_added': self.domains_added,
            'domains_duplicated': self.domains_duplicated,
            'uploaded_by': self.uploaded_by,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'processed': self.processed,
            'processing_error': self.processing_error,
            'metadata': self.metadata
        }
    
    @classmethod
    def create(
        cls,
        filename: str,
        original_filename: str,
        file_size: int,
        file_hash: str,
        uploaded_by: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> 'PDFUpload':
        """Cria novo registro de upload"""
        query = """
        INSERT INTO pdf_uploads (filename, original_filename, file_size, file_hash, uploaded_by, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, filename, original_filename, file_size, file_hash, domains_extracted,
                  domains_added, domains_duplicated, uploaded_by, uploaded_at, processed,
                  processing_error, metadata
        """
        
        metadata_json = json.dumps(metadata) if metadata else '{}'
        
        result = db.execute_query(
            query,
            (filename, original_filename, file_size, file_hash, uploaded_by, metadata_json)
        )
        
        return cls.from_dict(result[0])
    
    @classmethod
    def get_by_id(cls, upload_id: int) -> Optional['PDFUpload']:
        """Busca upload por ID"""
        query = "SELECT * FROM pdf_uploads WHERE id = %s"
        result = db.execute_query(query, (upload_id,))
        
        if result:
            return cls.from_dict(result[0])
        return None
    
    @classmethod
    def get_by_hash(cls, file_hash: str) -> Optional['PDFUpload']:
        """Busca upload por hash do arquivo"""
        query = "SELECT * FROM pdf_uploads WHERE file_hash = %s ORDER BY uploaded_at DESC LIMIT 1"
        result = db.execute_query(query, (file_hash,))
        
        if result:
            return cls.from_dict(result[0])
        return None
    
    @classmethod
    def get_recent(cls, limit: int = 50) -> List['PDFUpload']:
        """Lista uploads recentes"""
        query = """
        SELECT * FROM pdf_uploads
        ORDER BY uploaded_at DESC
        LIMIT %s
        """
        
        result = db.execute_query(query, (limit,))
        return [cls.from_dict(row) for row in result]
    
    @classmethod
    def get_by_user(cls, username: str, limit: int = 50) -> List['PDFUpload']:
        """Lista uploads de um usuário"""
        query = """
        SELECT * FROM pdf_uploads
        WHERE uploaded_by = %s
        ORDER BY uploaded_at DESC
        LIMIT %s
        """
        
        result = db.execute_query(query, (username, limit))
        return [cls.from_dict(row) for row in result]
    
    def update(self, **kwargs) -> bool:
        """Atualiza dados do upload"""
        allowed_fields = ['domains_extracted', 'domains_added', 'domains_duplicated',
                         'processed', 'processing_error', 'metadata']
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
        query = f"UPDATE pdf_uploads SET {', '.join(updates)} WHERE id = %s"
        
        db.execute_query(query, tuple(params), fetch=False)
        
        # Recarregar dados
        updated = self.get_by_id(self.id)
        if updated:
            self.__dict__.update(updated.__dict__)
            return True
        
        return False
    
    def mark_processed(
        self,
        domains_extracted: int,
        domains_added: int,
        domains_duplicated: int
    ) -> bool:
        """Marca upload como processado"""
        return self.update(
            processed=True,
            domains_extracted=domains_extracted,
            domains_added=domains_added,
            domains_duplicated=domains_duplicated
        )
    
    def mark_error(self, error_message: str) -> bool:
        """Marca upload com erro"""
        return self.update(
            processed=True,
            processing_error=error_message
        )
    
    def __repr__(self) -> str:
        status = "processado" if self.processed else "pendente"
        return f"<PDFUpload {self.original_filename} ({status})>"
