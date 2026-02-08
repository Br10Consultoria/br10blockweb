#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - API Authentication
=====================================
Autenticação para API de clientes DNS

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import logging
from functools import wraps
from typing import Optional, Tuple

from flask import request, jsonify

from backend.models.dns_client import DNSClient
from backend.models.user import User
from backend.utils.helpers import get_client_ip
from backend.utils.validators import validate_api_key

logger = logging.getLogger(__name__)


def get_api_key_from_request() -> Optional[str]:
    """Extrai API key da requisição"""
    # Tentar header Authorization
    auth_header = request.headers.get('Authorization')
    if auth_header:
        # Formato: "Bearer <api_key>" ou "ApiKey <api_key>"
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() in ['bearer', 'apikey']:
            return parts[1]
        # Formato direto: "<api_key>"
        return auth_header
    
    # Tentar header X-API-Key
    api_key = request.headers.get('X-API-Key')
    if api_key:
        return api_key
    
    # Tentar query parameter
    api_key = request.args.get('api_key')
    if api_key:
        return api_key
    
    return None


def authenticate_client() -> Tuple[bool, Optional[DNSClient], Optional[str]]:
    """
    Autentica cliente DNS via API key
    
    Returns:
        (autenticado, cliente, mensagem_erro)
    """
    api_key = get_api_key_from_request()
    
    if not api_key:
        return False, None, "API key não fornecida"
    
    # Validar formato
    valid, error = validate_api_key(api_key)
    if not valid:
        return False, None, error
    
    # Buscar cliente
    client = DNSClient.get_by_api_key(api_key)
    
    if not client:
        logger.warning(f"Tentativa de acesso com API key inválida: {api_key[:8]}...")
        return False, None, "API key inválida"
    
    if not client.active:
        logger.warning(f"Tentativa de acesso com cliente inativo: {client.name}")
        return False, None, "Cliente inativo"
    
    return True, client, None


def require_api_key(f):
    """Decorator para exigir autenticação via API key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        authenticated, client, error = authenticate_client()
        
        if not authenticated:
            return jsonify({
                'success': False,
                'error': error,
                'code': 'UNAUTHORIZED'
            }), 401
        
        # Adicionar cliente ao contexto da requisição
        request.client = client
        request.client_ip = get_client_ip(request)
        
        return f(*args, **kwargs)
    
    return decorated_function


def authenticate_admin() -> Tuple[bool, Optional[User], Optional[str]]:
    """
    Autentica usuário admin via sessão
    
    Returns:
        (autenticado, usuário, mensagem_erro)
    """
    from flask import session
    
    if 'user' not in session:
        return False, None, "Não autenticado"
    
    user_data = session['user']
    user = User.get_by_username(user_data.get('username'))
    
    if not user:
        return False, None, "Usuário não encontrado"
    
    if not user.active:
        return False, None, "Usuário inativo"
    
    return True, user, None


def require_admin(f):
    """Decorator para exigir autenticação de admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        authenticated, user, error = authenticate_admin()
        
        if not authenticated:
            from flask import redirect, url_for
            return redirect(url_for('login', next=request.url))
        
        # Adicionar usuário ao contexto da requisição
        request.user = user
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_admin_api(f):
    """Decorator para exigir autenticação de admin em rotas API"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        authenticated, user, error = authenticate_admin()
        
        if not authenticated:
            return jsonify({
                'success': False,
                'error': error,
                'code': 'UNAUTHORIZED'
            }), 401
        
        if user.role != 'admin':
            return jsonify({
                'success': False,
                'error': 'Permissão negada',
                'code': 'FORBIDDEN'
            }), 403
        
        # Adicionar usuário ao contexto da requisição
        request.user = user
        
        return f(*args, **kwargs)
    
    return decorated_function


def log_api_request(client: DNSClient, endpoint: str, status_code: int, duration_ms: int):
    """Registra requisição da API no banco"""
    try:
        from backend.database.db import db
        
        query = """
        INSERT INTO api_logs (client_id, endpoint, method, ip_address, status_code, duration_ms)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        db.execute_query(
            query,
            (
                client.id,
                endpoint,
                request.method,
                get_client_ip(request),
                status_code,
                duration_ms
            ),
            fetch=False
        )
    except Exception as e:
        logger.error(f"Erro ao registrar log de API: {e}")
