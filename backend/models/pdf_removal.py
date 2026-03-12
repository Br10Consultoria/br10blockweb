#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - PDF Removal Model
=====================================
Modelo de upload de PDF para remoção de domínios
Autor: BR10 Team
Versão: 3.1.0
Data: 2026-03-12
"""
import json
from datetime import datetime
from typing import Dict, List, Optional
from backend.database.db import db


class PDFRemoval:
    """Modelo de upload de PDF para remoção de domínios"""

    def __init__(
        self,
        id: Optional[int] = None,
        filename: str = None,
        original_filename: str = None,
        file_size: Optional[int] = None,
        file_hash: Optional[str] = None,
        domains_extracted: int = 0,
        domains_removed: int = 0,
        domains_not_found: int = 0,
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
        self.domains_removed = domains_removed
        self.domains_not_found = domains_not_found
        self.uploaded_by = uploaded_by
        self.uploaded_at = uploaded_at
        self.processed = processed
        self.processing_error = processing_error
        self.metadata = metadata or {}

    @classmethod
    def from_dict(cls, data: Dict) -> 'PDFRemoval':
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
            domains_removed=data.get('domains_removed', 0),
            domains_not_found=data.get('domains_not_found', 0),
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
            'domains_removed': self.domains_removed,
            'domains_not_found': self.domains_not_found,
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
        file_size: Optional[int] = None,
        file_hash: Optional[str] = None,
        domains_extracted: int = 0,
        domains_removed: int = 0,
        domains_not_found: int = 0,
        uploaded_by: Optional[str] = None,
        processed: bool = True,
        processing_error: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> 'PDFRemoval':
        """Cria novo registro de remoção"""
        query = """
        INSERT INTO pdf_removals (
            filename, original_filename, file_size, file_hash,
            domains_extracted, domains_removed, domains_not_found,
            uploaded_by, processed, processing_error, metadata
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """
        result = db.execute_query(query, (
            filename, original_filename, file_size, file_hash,
            domains_extracted, domains_removed, domains_not_found,
            uploaded_by, processed, processing_error,
            json.dumps(metadata or {})
        ))
        if result:
            return cls.from_dict(result[0])
        raise RuntimeError("Falha ao criar registro de remoção")

    @classmethod
    def get_recent(cls, limit: int = 20) -> List['PDFRemoval']:
        """Retorna os uploads mais recentes"""
        query = "SELECT * FROM pdf_removals ORDER BY uploaded_at DESC LIMIT %s"
        result = db.execute_query(query, (limit,))
        return [cls.from_dict(row) for row in result]

    @classmethod
    def get_by_id(cls, removal_id: int) -> Optional['PDFRemoval']:
        """Busca por ID"""
        query = "SELECT * FROM pdf_removals WHERE id = %s"
        result = db.execute_query(query, (removal_id,))
        if result:
            return cls.from_dict(result[0])
        return None
