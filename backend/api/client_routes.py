#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Client API Routes
====================================
Rotas da API para clientes DNS

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import logging
import time
from datetime import datetime

from flask import Blueprint, jsonify, request

from backend.api.auth import require_api_key, log_api_request
from backend.models.domain import Domain
from backend.models.sync_history import SyncHistory
from backend.utils.helpers import get_client_ip

logger = logging.getLogger(__name__)

# Blueprint para rotas de clientes
client_api = Blueprint('client_api', __name__, url_prefix='/api/v1/client')


@client_api.route('/ping', methods=['GET'])
@require_api_key
def ping():
    """Endpoint de ping/healthcheck"""
    start_time = time.time()
    
    try:
        client = request.client
        
        # Atualizar heartbeat
        client.update_heartbeat()
        
        response = {
            'success': True,
            'message': 'pong',
            'client': {
                'id': client.id,
                'name': client.name,
                'status': client.status
            },
            'server_time': datetime.now().isoformat()
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_api_request(client, '/api/v1/client/ping', 200, duration_ms)
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Erro no ping: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@client_api.route('/domains', methods=['GET'])
@require_api_key
def get_domains():
    """Retorna lista de domínios bloqueados"""
    start_time = time.time()
    
    try:
        client = request.client
        
        # Parâmetros opcionais
        format_type = request.args.get('format', 'json')  # json, txt, rpz
        include_metadata = request.args.get('metadata', 'false').lower() == 'true'
        
        # Buscar domínios ativos
        domains = Domain.get_active_domains_list()
        
        # Formato de resposta
        if format_type == 'txt':
            response = '\n'.join(domains)
            content_type = 'text/plain'
        elif format_type == 'rpz':
            rpz_lines = [f'{domain} CNAME .' for domain in domains]
            response = '\n'.join(rpz_lines)
            content_type = 'text/plain'
        else:  # json
            response_data = {
                'success': True,
                'total': len(domains),
                'domains': domains,
                'timestamp': datetime.now().isoformat()
            }
            
            if include_metadata:
                response_data['metadata'] = {
                    'client_id': client.id,
                    'client_name': client.name,
                    'last_sync': client.last_sync.isoformat() if client.last_sync else None
                }
            
            response = jsonify(response_data)
            content_type = 'application/json'
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_api_request(client, '/api/v1/client/domains', 200, duration_ms)
        
        if format_type in ['txt', 'rpz']:
            return response, 200, {'Content-Type': content_type}
        return response, 200
    
    except Exception as e:
        logger.error(f"Erro ao buscar domínios: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@client_api.route('/domains/count', methods=['GET'])
@require_api_key
def get_domains_count():
    """Retorna apenas a contagem de domínios"""
    start_time = time.time()
    
    try:
        client = request.client
        
        count = Domain.count(active_only=True)
        
        response = {
            'success': True,
            'count': count,
            'timestamp': datetime.now().isoformat()
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_api_request(client, '/api/v1/client/domains/count', 200, duration_ms)
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Erro ao contar domínios: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@client_api.route('/sync/start', methods=['POST'])
@require_api_key
def start_sync():
    """Inicia processo de sincronização"""
    start_time = time.time()
    
    try:
        client = request.client
        
        # Buscar domínios
        domains = Domain.get_active_domains_list()
        
        # Criar registro de sincronização
        sync = SyncHistory.create(
            client_id=client.id,
            domains_sent=len(domains),
            status='pending',
            message='Sincronização iniciada'
        )
        
        # Atualizar status do cliente
        client.update(status='syncing')
        
        response = {
            'success': True,
            'sync_id': sync.id,
            'domains_count': len(domains),
            'message': 'Sincronização iniciada. Use /sync/complete para finalizar.'
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_api_request(client, '/api/v1/client/sync/start', 200, duration_ms)
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Erro ao iniciar sincronização: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@client_api.route('/sync/complete', methods=['POST'])
@require_api_key
def complete_sync():
    """Finaliza processo de sincronização com feedback"""
    start_time = time.time()
    
    try:
        client = request.client
        data = request.get_json() or {}
        
        sync_id = data.get('sync_id')
        domains_applied = data.get('domains_applied', 0)
        status = data.get('status', 'success')  # success, failed, partial
        message = data.get('message', '')
        error_details = data.get('error_details')
        duration_seconds = data.get('duration_seconds', 0)
        
        # Buscar sincronização
        if sync_id:
            sync = SyncHistory.get_by_id(sync_id)
            if sync and sync.client_id == client.id:
                # Atualizar sincronização
                sync.update(
                    domains_applied=domains_applied,
                    status=status,
                    message=message,
                    error_details=error_details,
                    duration_seconds=duration_seconds
                )
            else:
                logger.warning(f"Sync ID inválido ou não pertence ao cliente: {sync_id}")
        
        # Atualizar cliente
        client.update_sync_status(domains_applied, status)
        
        response = {
            'success': True,
            'message': 'Sincronização registrada com sucesso',
            'client_status': client.status
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_api_request(client, '/api/v1/client/sync/complete', 200, duration_ms)
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Erro ao completar sincronização: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@client_api.route('/sync/history', methods=['GET'])
@require_api_key
def get_sync_history():
    """Retorna histórico de sincronizações do cliente"""
    start_time = time.time()
    
    try:
        client = request.client
        
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        # Buscar histórico
        history = SyncHistory.get_by_client(client.id, limit, offset)
        
        response = {
            'success': True,
            'client_id': client.id,
            'client_name': client.name,
            'history': [sync.to_dict() for sync in history],
            'total': len(history)
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_api_request(client, '/api/v1/client/sync/history', 200, duration_ms)
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Erro ao buscar histórico: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@client_api.route('/status', methods=['GET'])
@require_api_key
def get_status():
    """Retorna status detalhado do cliente"""
    start_time = time.time()
    
    try:
        client = request.client
        
        # Buscar última sincronização
        recent_syncs = SyncHistory.get_by_client(client.id, limit=1)
        last_sync = recent_syncs[0].to_dict() if recent_syncs else None
        
        response = {
            'success': True,
            'client': client.to_dict(include_api_key=False),
            'last_sync': last_sync,
            'current_domains_count': Domain.count(active_only=True),
            'server_time': datetime.now().isoformat()
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_api_request(client, '/api/v1/client/status', 200, duration_ms)
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Erro ao buscar status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@client_api.errorhandler(404)
def not_found(error):
    """Handler para rotas não encontradas"""
    return jsonify({
        'success': False,
        'error': 'Endpoint não encontrado',
        'code': 'NOT_FOUND'
    }), 404


@client_api.errorhandler(500)
def internal_error(error):
    """Handler para erros internos"""
    logger.error(f"Erro interno na API: {error}")
    return jsonify({
        'success': False,
        'error': 'Erro interno do servidor',
        'code': 'INTERNAL_ERROR'
    }), 500
