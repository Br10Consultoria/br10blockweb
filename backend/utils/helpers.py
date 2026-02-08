#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Helpers
==========================
Funções auxiliares

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


def generate_random_string(length: int = 32, include_special: bool = False) -> str:
    """Gera string aleatória"""
    if include_special:
        chars = string.ascii_letters + string.digits + string.punctuation
    else:
        chars = string.ascii_letters + string.digits
    
    return ''.join(secrets.choice(chars) for _ in range(length))


def generate_api_key() -> str:
    """Gera uma API key segura"""
    return secrets.token_urlsafe(32)


def format_file_size(size_bytes: int) -> str:
    """Formata tamanho de arquivo para leitura humana"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def format_duration(seconds: int) -> str:
    """Formata duração em segundos para leitura humana"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def format_timestamp(dt: datetime, format: str = 'full') -> str:
    """Formata timestamp"""
    if format == 'full':
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    elif format == 'date':
        return dt.strftime('%Y-%m-%d')
    elif format == 'time':
        return dt.strftime('%H:%M:%S')
    elif format == 'iso':
        return dt.isoformat()
    else:
        return str(dt)


def time_ago(dt: datetime) -> str:
    """Retorna tempo relativo (ex: '2 horas atrás')"""
    now = datetime.now()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "agora mesmo"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minuto{'s' if minutes > 1 else ''} atrás"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hora{'s' if hours > 1 else ''} atrás"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} dia{'s' if days > 1 else ''} atrás"
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f"{weeks} semana{'s' if weeks > 1 else ''} atrás"
    elif seconds < 31536000:
        months = int(seconds / 2592000)
        return f"{months} {'mês' if months == 1 else 'meses'} atrás"
    else:
        years = int(seconds / 31536000)
        return f"{years} ano{'s' if years > 1 else ''} atrás"


def paginate(
    items: list,
    page: int = 1,
    per_page: int = 50
) -> Dict[str, Any]:
    """Pagina uma lista de itens"""
    total = len(items)
    total_pages = (total + per_page - 1) // per_page
    
    # Validar página
    if page < 1:
        page = 1
    if page > total_pages and total_pages > 0:
        page = total_pages
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    return {
        'items': items[start_idx:end_idx],
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages
    }


def get_client_ip(request) -> Optional[str]:
    """Obtém IP do cliente da requisição"""
    # Verificar headers de proxy
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr


def safe_int(value: Any, default: int = 0) -> int:
    """Converte valor para int de forma segura"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Converte valor para float de forma segura"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """Converte valor para bool de forma segura"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ['true', '1', 'yes', 'on']
    if isinstance(value, int):
        return value != 0
    return default


def truncate_string(text: str, length: int = 100, suffix: str = '...') -> str:
    """Trunca string adicionando sufixo"""
    if len(text) <= length:
        return text
    return text[:length - len(suffix)] + suffix


def merge_dicts(*dicts: Dict) -> Dict:
    """Mescla múltiplos dicionários"""
    result = {}
    for d in dicts:
        result.update(d)
    return result


def chunk_list(items: list, chunk_size: int) -> list:
    """Divide lista em chunks"""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def deduplicate_list(items: list, preserve_order: bool = True) -> list:
    """Remove duplicatas de lista"""
    if preserve_order:
        seen = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result
    else:
        return list(set(items))
