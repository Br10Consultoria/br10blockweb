#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Validators
=============================
Funções de validação

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import re
from pathlib import Path
from typing import Optional, Tuple

from backend.config import Config


def validate_domain(domain: str) -> Tuple[bool, Optional[str]]:
    """
    Valida um domínio
    
    Returns:
        (válido, mensagem_erro)
    """
    if not domain:
        return False, "Domínio não pode ser vazio"
    
    domain = domain.strip().lower()
    
    # Tamanho
    if len(domain) < 4:
        return False, "Domínio muito curto (mínimo 4 caracteres)"
    
    if len(domain) > 255:
        return False, "Domínio muito longo (máximo 255 caracteres)"
    
    # Padrão básico
    pattern = re.compile(
        r'^(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$'
    )
    
    if not pattern.match(domain):
        return False, "Formato de domínio inválido"
    
    # Verificar se tem pelo menos um ponto
    if '.' not in domain:
        return False, "Domínio deve conter pelo menos um ponto"
    
    # Verificar TLD
    parts = domain.split('.')
    if len(parts[-1]) < 2:
        return False, "TLD inválido"
    
    return True, None


def validate_ip_address(ip: str) -> Tuple[bool, Optional[str]]:
    """
    Valida um endereço IP (IPv4 ou IPv6)
    
    Returns:
        (válido, mensagem_erro)
    """
    if not ip:
        return False, "IP não pode ser vazio"
    
    # IPv4
    ipv4_pattern = re.compile(
        r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
        r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    )
    
    if ipv4_pattern.match(ip):
        return True, None
    
    # IPv6 (simplificado)
    ipv6_pattern = re.compile(
        r'^(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|'
        r'([0-9a-fA-F]{1,4}:){1,7}:|'
        r'([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|'
        r'::)$'
    )
    
    if ipv6_pattern.match(ip):
        return True, None
    
    return False, "Formato de IP inválido"


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Valida um endereço de email
    
    Returns:
        (válido, mensagem_erro)
    """
    if not email:
        return False, "Email não pode ser vazio"
    
    pattern = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    if not pattern.match(email):
        return False, "Formato de email inválido"
    
    return True, None


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """
    Valida um nome de usuário
    
    Returns:
        (válido, mensagem_erro)
    """
    if not username:
        return False, "Username não pode ser vazio"
    
    if len(username) < 3:
        return False, "Username muito curto (mínimo 3 caracteres)"
    
    if len(username) > 50:
        return False, "Username muito longo (máximo 50 caracteres)"
    
    pattern = re.compile(r'^[a-zA-Z0-9_-]+$')
    
    if not pattern.match(username):
        return False, "Username deve conter apenas letras, números, _ e -"
    
    return True, None


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    Valida uma senha
    
    Returns:
        (válido, mensagem_erro)
    """
    if not password:
        return False, "Senha não pode ser vazia"
    
    if len(password) < 6:
        return False, "Senha muito curta (mínimo 6 caracteres)"
    
    if len(password) > 128:
        return False, "Senha muito longa (máximo 128 caracteres)"
    
    return True, None


def validate_file_upload(
    filename: str,
    file_size: int,
    allowed_extensions: set = None
) -> Tuple[bool, Optional[str]]:
    """
    Valida um arquivo para upload
    
    Returns:
        (válido, mensagem_erro)
    """
    if not filename:
        return False, "Nome do arquivo não pode ser vazio"
    
    # Extensão
    if allowed_extensions is None:
        allowed_extensions = Config.ALLOWED_EXTENSIONS
    
    file_ext = Path(filename).suffix.lower().lstrip('.')
    
    if file_ext not in allowed_extensions:
        return False, f"Extensão não permitida. Permitidas: {', '.join(allowed_extensions)}"
    
    # Tamanho
    if file_size > Config.MAX_CONTENT_LENGTH:
        max_mb = Config.MAX_CONTENT_LENGTH / (1024 * 1024)
        return False, f"Arquivo muito grande (máximo {max_mb}MB)"
    
    if file_size == 0:
        return False, "Arquivo vazio"
    
    return True, None


def sanitize_filename(filename: str) -> str:
    """Remove caracteres perigosos do nome do arquivo"""
    # Remover path traversal
    filename = Path(filename).name
    
    # Remover caracteres especiais
    filename = re.sub(r'[^\w\s.-]', '', filename)
    
    # Limitar tamanho
    if len(filename) > 255:
        name, ext = Path(filename).stem, Path(filename).suffix
        filename = name[:250] + ext
    
    return filename


def validate_api_key(api_key: str) -> Tuple[bool, Optional[str]]:
    """
    Valida uma API key
    
    Returns:
        (válido, mensagem_erro)
    """
    if not api_key:
        return False, "API key não pode ser vazia"
    
    if len(api_key) < 32:
        return False, "API key inválida"
    
    # Verificar se contém apenas caracteres válidos
    pattern = re.compile(r'^[a-zA-Z0-9_-]+$')
    
    if not pattern.match(api_key):
        return False, "API key contém caracteres inválidos"
    
    return True, None
