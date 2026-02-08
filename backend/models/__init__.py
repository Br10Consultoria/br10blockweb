#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Models
========================
Modelos de dados da aplicação

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

from backend.models.user import User
from backend.models.domain import Domain
from backend.models.dns_client import DNSClient
from backend.models.sync_history import SyncHistory
from backend.models.pdf_upload import PDFUpload
from backend.models.domain_history import DomainHistory

__all__ = [
    'User',
    'Domain',
    'DNSClient',
    'SyncHistory',
    'PDFUpload',
    'DomainHistory'
]
