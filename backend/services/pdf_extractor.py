#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - PDF Extractor Service
========================================
Serviço para extração de domínios de arquivos PDF

Suporta dois formatos principais:
  1. PDF com domínios em tabelas (ex: Planilha Modelo Anexo Operacao)
     - Formato: [marca | domínio | coluna_extra]
  2. PDF com domínios em texto corrido (ex: Ofícios do CyberGaeco/ABTA)
     - Formato: um domínio por linha ou inline no texto

Autor: BR10 Team
Versão: 3.1.0
Data: 2026-03-07
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import PyPDF2
import pdfplumber

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Serviço de extração de domínios de PDF"""

    # Regex para identificar domínios em texto corrido
    DOMAIN_PATTERN = re.compile(
        r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)'
        r'+[a-zA-Z]{2,63}\b',
        re.IGNORECASE
    )

    # TLDs válidos mais comuns — usados para filtrar falsos positivos
    # Lista não exaustiva; a validação principal é pelo padrão do domínio
    COMMON_TLDS = {
        'com', 'net', 'org', 'br', 'io', 'co', 'info', 'biz', 'me',
        'tv', 'cc', 'app', 'dev', 'online', 'site', 'web', 'xyz',
        'live', 'stream', 'top', 'club', 'vip', 'fun', 'pro', 'one',
        'bet', 'win', 'games', 'store', 'shop', 'click', 'link',
        'digital', 'tech', 'media', 'news', 'blog', 'wiki', 'space',
        'host', 'cloud', 'network', 'systems', 'solutions', 'group',
        'global', 'world', 'center', 'zone', 'hub', 'plus', 'max',
        'ultra', 'mega', 'super', 'best', 'free', 'fast', 'easy',
        'smart', 'safe', 'secure', 'direct', 'express', 'prime',
        'premium', 'elite', 'master', 'expert', 'pro', 'star',
        # TLDs de países comuns
        'us', 'uk', 'ca', 'au', 'de', 'fr', 'es', 'it', 'pt', 'mx',
        'ar', 'cl', 'pe', 'co', 'ec', 'bo', 'py', 'uy', 've', 'cr',
        'do', 'gt', 'hn', 'ni', 'pa', 'sv', 'cu', 'ht', 'jm', 'tt',
        'nz', 'za', 'ng', 'ke', 'gh', 'eg', 'ma', 'tn', 'dz', 'ly',
        'cn', 'jp', 'kr', 'in', 'pk', 'bd', 'lk', 'np', 'vn', 'th',
        'id', 'my', 'sg', 'ph', 'hk', 'tw', 'ru', 'ua', 'pl', 'cz',
        'sk', 'hu', 'ro', 'bg', 'hr', 'rs', 'si', 'ba', 'mk', 'al',
        'gr', 'tr', 'il', 'sa', 'ae', 'kw', 'qa', 'bh', 'om', 'jo',
        'lb', 'sy', 'iq', 'ir', 'af', 'uz', 'kz', 'az', 'ge', 'am',
        # TLDs genéricos novos
        'academy', 'accountant', 'actor', 'adult', 'agency', 'airforce',
        'apartments', 'app', 'art', 'associates', 'auction', 'audio',
        'band', 'bar', 'bargains', 'beer', 'bet', 'bid', 'bike',
        'bingo', 'black', 'blue', 'boutique', 'broker', 'build',
        'builders', 'business', 'buzz', 'cab', 'cafe', 'camera',
        'camp', 'capital', 'cards', 'care', 'careers', 'cash',
        'casino', 'catering', 'ceo', 'chat', 'cheap', 'church',
        'city', 'claims', 'cleaning', 'clinic', 'clothing', 'coach',
        'codes', 'coffee', 'community', 'company', 'computer',
        'consulting', 'contact', 'contractors', 'cool', 'coupons',
        'credit', 'cruises', 'dance', 'dating', 'deals', 'delivery',
        'democrat', 'dental', 'design', 'diamonds', 'diet', 'digital',
        'direct', 'directory', 'discount', 'dog', 'domains', 'education',
        'email', 'energy', 'engineering', 'enterprises', 'equipment',
        'estate', 'events', 'exchange', 'expert', 'exposed', 'express',
        'fail', 'farm', 'finance', 'financial', 'fish', 'fitness',
        'flights', 'florist', 'fm', 'football', 'forsale', 'foundation',
        'fund', 'furniture', 'fyi', 'gallery', 'gifts', 'gives',
        'glass', 'global', 'gold', 'golf', 'graphics', 'gratis',
        'green', 'gripe', 'guide', 'guitars', 'guru', 'healthcare',
        'hockey', 'holdings', 'holiday', 'homes', 'horse', 'hospital',
        'house', 'icu', 'immo', 'immobilien', 'industries', 'institute',
        'insure', 'international', 'investments', 'jewelry', 'kitchen',
        'land', 'law', 'lease', 'legal', 'life', 'lighting', 'limited',
        'limo', 'loans', 'maison', 'management', 'marketing', 'mba',
        'memorial', 'mobi', 'moda', 'money', 'mortgage', 'movie',
        'name', 'ninja', 'observer', 'partners', 'parts', 'photo',
        'photography', 'photos', 'pictures', 'pink', 'pizza', 'place',
        'plumbing', 'pm', 'poker', 'productions', 'properties',
        'property', 'pub', 'recipes', 'red', 'reisen', 'rentals',
        'repair', 'report', 'republican', 'restaurant', 'reviews',
        'rich', 'rip', 'rocks', 'run', 'sale', 'salon', 'school',
        'services', 'show', 'singles', 'soccer', 'social', 'solar',
        'solutions', 'studio', 'style', 'support', 'surf', 'surgery',
        'sx', 'systems', 'tattoo', 'tax', 'taxi', 'team', 'technology',
        'tennis', 'theater', 'tienda', 'tips', 'tires', 'today',
        'tools', 'tours', 'town', 'toys', 'trade', 'training',
        'tube', 'uno', 'vacations', 'ventures', 'video', 'villas',
        'vin', 'vision', 'voyage', 'watch', 'website', 'wedding',
        'wiki', 'works', 'wtf', 'yoga', 'zone',
    }

    # Palavras que parecem domínios mas são falsos positivos
    IGNORE_DOMAINS = {
        'example.com', 'example.org', 'example.net',
        'localhost', 'test.com', 'domain.com',
        'email.com', 'website.com', 'page.com',
        'google.com', 'facebook.com', 'twitter.com',
        'instagram.com', 'youtube.com', 'whatsapp.com',
        'microsoft.com', 'apple.com', 'amazon.com',
    }

    # Palavras que NÃO são domínios (evitar falsos positivos de texto)
    NOT_DOMAIN_WORDS = {
        'art', 'fig', 'tab', 'ref', 'obs', 'ver', 'vide',
        'inc', 'ltda', 'eireli', 'me', 'sa', 'sas',
        'jan', 'fev', 'mar', 'abr', 'mai', 'jun',
        'jul', 'ago', 'set', 'out', 'nov', 'dez',
        'seg', 'ter', 'qua', 'qui', 'sex', 'sab', 'dom',
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
        """
        Valida se uma string é um domínio válido para bloqueio.
        Mais permissivo que o validador de formulário — aceita TLDs novos.
        """
        domain = domain.strip().lower()

        # Tamanho
        if len(domain) < 4 or len(domain) > 255:
            return False

        # Lista de ignorados explícita
        if domain in PDFExtractor.IGNORE_DOMAINS:
            return False

        # Deve ter pelo menos um ponto
        if '.' not in domain:
            return False

        # Não pode começar/terminar com ponto ou hífen
        if domain[0] in ('.', '-') or domain[-1] in ('.', '-'):
            return False

        # Não pode conter caracteres inválidos
        if re.search(r'[^a-z0-9.\-]', domain):
            return False

        parts = domain.split('.')

        # Cada parte deve ser válida
        for part in parts:
            if not part:
                return False
            if part[0] == '-' or part[-1] == '-':
                return False
            if not re.match(r'^[a-z0-9\-]+$', part):
                return False

        # TLD deve ter pelo menos 2 caracteres e não ser só números
        tld = parts[-1]
        if len(tld) < 2:
            return False
        if tld.isdigit():
            return False

        # Deve ter pelo menos 2 partes (ex: dominio.tld)
        if len(parts) < 2:
            return False

        # Parte principal (SLD) deve ter pelo menos 1 caractere
        if len(parts[-2]) < 1:
            return False

        # Filtrar palavras comuns que não são domínios
        if len(parts) == 2 and parts[0] in PDFExtractor.NOT_DOMAIN_WORDS:
            return False

        # Filtrar IPs disfarçados (ex: 1.2.3.4)
        if all(p.isdigit() for p in parts):
            return False

        # Filtrar números de processo judicial (ex: 1031339-38.2022.8.26.0050)
        if re.match(r'^\d+[-\d]*\.\d+', domain):
            return False

        # Filtrar datas e números (ex: 13.02.2025, 29.0001.0082235)
        if re.match(r'^\d+\.\d+\.\d+', domain):
            return False

        return True

    @staticmethod
    def extract_domains_from_text(text: str) -> Set[str]:
        """Extrai domínios de texto corrido usando regex"""
        domains = set()
        if not text:
            return domains

        # Normalizar espaços e quebras de linha que podem fragmentar domínios
        # Juntar linhas onde a linha anterior termina com parte de domínio
        lines = text.split('\n')
        normalized_lines = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # Se a linha parece ser a primeira parte de um domínio quebrado
            # (termina com ponto ou com parte sem TLD)
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Verificar se juntar as duas linhas forma um domínio válido
                if line.endswith('.') and next_line and not next_line.startswith(' '):
                    combined = line + next_line
                    if PDFExtractor.DOMAIN_PATTERN.match(combined):
                        normalized_lines.append(combined)
                        i += 2
                        continue
            normalized_lines.append(line)
            i += 1

        normalized_text = '\n'.join(normalized_lines)

        matches = PDFExtractor.DOMAIN_PATTERN.findall(normalized_text)
        for match in matches:
            domain = match.strip().lower().rstrip('.')
            if PDFExtractor.validate_domain(domain):
                domains.add(domain)

        return domains

    @staticmethod
    def extract_domains_from_table_cell(cell: Optional[str]) -> Optional[str]:
        """
        Extrai domínio de uma célula de tabela.
        Retorna o domínio se válido, None caso contrário.
        """
        if not cell:
            return None
        cell = cell.strip().lower()
        # Remover prefixos http/https/www
        cell = re.sub(r'^https?://', '', cell)
        cell = re.sub(r'^www\.', '', cell)
        # Remover path e query string
        cell = cell.split('/')[0].split('?')[0].split('#')[0]
        # Remover porta
        cell = re.sub(r':\d+$', '', cell)
        cell = cell.strip().rstrip('.')

        if PDFExtractor.validate_domain(cell):
            return cell
        return None

    @classmethod
    def extract_with_pdfplumber(cls, file_path: Path) -> Tuple[Set[str], Dict]:
        """
        Extrai domínios usando pdfplumber.
        Tenta extrair de tabelas primeiro (mais preciso), depois de texto corrido.
        """
        domains = set()
        metadata = {
            'method': 'pdfplumber',
            'pages': 0,
            'tables_found': 0,
            'errors': []
        }

        try:
            with pdfplumber.open(file_path) as pdf:
                metadata['pages'] = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        # 1. Tentar extrair de tabelas (PDFs tipo planilha)
                        tables = page.extract_tables()
                        if tables:
                            metadata['tables_found'] += len(tables)
                            for table in tables:
                                for row in table:
                                    if not row:
                                        continue
                                    for cell in row:
                                        domain = cls.extract_domains_from_table_cell(cell)
                                        if domain:
                                            domains.add(domain)

                        # 2. Extrair de texto corrido (PDFs tipo ofício)
                        text = page.extract_text()
                        if text:
                            page_domains = cls.extract_domains_from_text(text)
                            domains.update(page_domains)
                            logger.debug(f"Página {page_num}: {len(page_domains)} domínios no texto")

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
    def extract_with_pypdf2(cls, file_path: Path) -> Tuple[Set[str], Dict]:
        """Extrai domínios usando PyPDF2 (fallback)"""
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
    def extract_domains(cls, file_path: Path, method: str = 'auto') -> Dict:
        """
        Extrai domínios de um arquivo PDF.

        Args:
            file_path: Caminho do arquivo PDF
            method: Método de extração ('pypdf2', 'pdfplumber', 'auto')

        Returns:
            Dict com domínios extraídos e metadados
        """
        logger.info(f"Iniciando extração de domínios: {file_path}")

        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

        file_hash = cls.calculate_file_hash(file_path)
        file_size = file_path.stat().st_size

        domains: Set[str] = set()
        extraction_metadata: Dict = {}

        # pdfplumber primeiro (suporta tabelas + texto)
        if method in ['auto', 'pdfplumber']:
            try:
                domains_plumber, metadata_plumber = cls.extract_with_pdfplumber(file_path)
                if domains_plumber:
                    domains.update(domains_plumber)
                    extraction_metadata = metadata_plumber
                    logger.info(f"pdfplumber: {len(domains_plumber)} domínios extraídos")
            except Exception as e:
                logger.warning(f"Falha com pdfplumber: {e}")

        # PyPDF2 como fallback ou quando explicitamente solicitado
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

        tlds: Dict[str, int] = {}
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
