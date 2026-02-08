#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - PDF Extractor Service
========================================
Serviço para extração de domínios de arquivos PDF

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

import PyPDF2
import pdfplumber

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Serviço de extração de domínios de PDF"""
    
    # Regex para identificar domínios
    DOMAIN_PATTERN = re.compile(
        r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b',
        re.IGNORECASE
    )
    
    # Domínios comuns para ignorar (falsos positivos)
    IGNORE_DOMAINS = {
        'example.com', 'example.org', 'example.net',
        'localhost', 'test.com', 'domain.com',
        'email.com', 'website.com', 'page.com'
    }
    
    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        """Calcula hash SHA-256 do arquivo"""
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    @staticmethod
    def validate_domain(domain: str) -> bool:
        """Valida se o domínio é válido"""
        # Remover espaços
        domain = domain.strip().lower()
        
        # Verificar tamanho
        if len(domain) < 4 or len(domain) > 255:
            return False
        
        # Verificar se está na lista de ignorados
        if domain in PDFExtractor.IGNORE_DOMAINS:
            return False
        
        # Verificar se tem pelo menos um ponto
        if '.' not in domain:
            return False
        
        # Verificar se não começa ou termina com ponto ou hífen
        if domain.startswith('.') or domain.endswith('.'):
            return False
        if domain.startswith('-') or domain.endswith('-'):
            return False
        
        # Verificar se não contém caracteres inválidos
        if any(char in domain for char in [' ', '/', '\\', '@', '#', '$', '%', '&', '*']):
            return False
        
        # Verificar TLD válido (pelo menos 2 caracteres)
        parts = domain.split('.')
        if len(parts[-1]) < 2:
            return False
        
        return True
    
    @staticmethod
    def extract_domains_from_text(text: str) -> Set[str]:
        """Extrai domínios de um texto"""
        domains = set()
        
        # Encontrar todos os padrões que parecem domínios
        matches = PDFExtractor.DOMAIN_PATTERN.findall(text)
        
        for match in matches:
            domain = match.strip().lower()
            
            # Validar domínio
            if PDFExtractor.validate_domain(domain):
                domains.add(domain)
        
        return domains
    
    @classmethod
    def extract_with_pypdf2(cls, file_path: Path) -> Tuple[Set[str], Dict]:
        """Extrai domínios usando PyPDF2"""
        domains = set()
        metadata = {
            'method': 'pypdf2',
            'pages': 0,
            'errors': []
        }
        
        try:
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                metadata['pages'] = len(pdf_reader.pages)
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    try:
                        text = page.extract_text()
                        if text:
                            page_domains = cls.extract_domains_from_text(text)
                            domains.update(page_domains)
                            logger.debug(f"Página {page_num}: {len(page_domains)} domínios encontrados")
                    except Exception as e:
                        error_msg = f"Erro na página {page_num}: {str(e)}"
                        metadata['errors'].append(error_msg)
                        logger.warning(error_msg)
        
        except Exception as e:
            error_msg = f"Erro ao processar PDF com PyPDF2: {str(e)}"
            metadata['errors'].append(error_msg)
            logger.error(error_msg)
        
        return domains, metadata
    
    @classmethod
    def extract_with_pdfplumber(cls, file_path: Path) -> Tuple[Set[str], Dict]:
        """Extrai domínios usando pdfplumber (mais preciso)"""
        domains = set()
        metadata = {
            'method': 'pdfplumber',
            'pages': 0,
            'errors': []
        }
        
        try:
            with pdfplumber.open(file_path) as pdf:
                metadata['pages'] = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        text = page.extract_text()
                        if text:
                            page_domains = cls.extract_domains_from_text(text)
                            domains.update(page_domains)
                            logger.debug(f"Página {page_num}: {len(page_domains)} domínios encontrados")
                    except Exception as e:
                        error_msg = f"Erro na página {page_num}: {str(e)}"
                        metadata['errors'].append(error_msg)
                        logger.warning(error_msg)
        
        except Exception as e:
            error_msg = f"Erro ao processar PDF com pdfplumber: {str(e)}"
            metadata['errors'].append(error_msg)
            logger.error(error_msg)
        
        return domains, metadata
    
    @classmethod
    def extract_domains(cls, file_path: Path, method: str = 'auto') -> Dict:
        """
        Extrai domínios de um arquivo PDF
        
        Args:
            file_path: Caminho do arquivo PDF
            method: Método de extração ('pypdf2', 'pdfplumber', 'auto')
        
        Returns:
            Dict com domínios extraídos e metadados
        """
        logger.info(f"Iniciando extração de domínios: {file_path}")
        
        # Verificar se arquivo existe
        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        
        # Calcular hash do arquivo
        file_hash = cls.calculate_file_hash(file_path)
        file_size = file_path.stat().st_size
        
        domains = set()
        extraction_metadata = {}
        
        # Tentar com pdfplumber primeiro (mais preciso)
        if method in ['auto', 'pdfplumber']:
            try:
                domains_plumber, metadata_plumber = cls.extract_with_pdfplumber(file_path)
                if domains_plumber:
                    domains.update(domains_plumber)
                    extraction_metadata = metadata_plumber
                    logger.info(f"pdfplumber: {len(domains_plumber)} domínios extraídos")
            except Exception as e:
                logger.warning(f"Falha com pdfplumber: {e}")
        
        # Se não encontrou domínios ou método é pypdf2, tentar com PyPDF2
        if (not domains and method in ['auto', 'pypdf2']) or method == 'pypdf2':
            try:
                domains_pypdf2, metadata_pypdf2 = cls.extract_with_pypdf2(file_path)
                if domains_pypdf2:
                    domains.update(domains_pypdf2)
                    if not extraction_metadata:
                        extraction_metadata = metadata_pypdf2
                    logger.info(f"PyPDF2: {len(domains_pypdf2)} domínios extraídos")
            except Exception as e:
                logger.warning(f"Falha com PyPDF2: {e}")
        
        # Ordenar domínios
        domains_list = sorted(list(domains))
        
        result = {
            'success': len(domains) > 0,
            'domains': domains_list,
            'total_domains': len(domains),
            'file_hash': file_hash,
            'file_size': file_size,
            'extraction_metadata': extraction_metadata
        }
        
        logger.info(f"Extração concluída: {len(domains)} domínios únicos encontrados")
        
        return result
    
    @staticmethod
    def preview_domains(domains: List[str], limit: int = 20) -> Dict:
        """Gera preview dos domínios para visualização"""
        total = len(domains)
        preview = domains[:limit]
        
        # Estatísticas básicas
        tlds = {}
        for domain in domains:
            tld = domain.split('.')[-1]
            tlds[tld] = tlds.get(tld, 0) + 1
        
        top_tlds = sorted(tlds.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            'total': total,
            'preview': preview,
            'showing': len(preview),
            'has_more': total > limit,
            'statistics': {
                'total_domains': total,
                'unique_tlds': len(tlds),
                'top_tlds': [{'tld': tld, 'count': count} for tld, count in top_tlds]
            }
        }
