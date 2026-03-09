#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Admin API Routes
===================================
Rotas da API administrativa

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import logging
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from backend.api.auth import require_admin_api
from backend.config import Config
from backend.models.domain import Domain
from backend.models.domain_history import DomainHistory
from backend.models.dns_client import DNSClient
from backend.models.pdf_upload import PDFUpload
from backend.models.sync_history import SyncHistory
from backend.services.domain_manager import DomainManager
from backend.utils.helpers import paginate, safe_int
from backend.utils.validators import validate_file_upload, sanitize_filename

logger = logging.getLogger(__name__)

# Blueprint para rotas administrativas
admin_api = Blueprint('admin_api', __name__, url_prefix='/api/v1/admin')


# === Gerenciamento de Domínios ===

@admin_api.route('/domains', methods=['GET'])
@require_admin_api
def list_domains():
    """Lista domínios com paginação e busca"""
    try:
        page = safe_int(request.args.get('page', 1), 1)
        per_page = safe_int(request.args.get('per_page', 50), 50)
        search = request.args.get('search', '').strip()
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        # Buscar domínios
        domains = Domain.get_all(active_only=active_only, search=search)
        total = Domain.count(active_only=active_only, search=search)
        
        # Paginar
        paginated = paginate(domains, page, per_page)
        
        return jsonify({
            'success': True,
            'domains': [d.to_dict() for d in paginated['items']],
            'pagination': {
                'page': paginated['page'],
                'per_page': paginated['per_page'],
                'total': paginated['total'],
                'total_pages': paginated['total_pages'],
                'has_prev': paginated['has_prev'],
                'has_next': paginated['has_next']
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Erro ao listar domínios: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_api.route('/domains', methods=['POST'])
@require_admin_api
def add_domain():
    """Adiciona um domínio"""
    try:
        data = request.get_json()
        domain = data.get('domain', '').strip().lower()
        notes = data.get('notes', '')
        
        if not domain:
            return jsonify({'success': False, 'error': 'Domínio não fornecido'}), 400
        
        success, message, domain_obj = DomainManager.add_domain(
            domain=domain,
            added_by=request.user.username,
            source='manual',
            notes=notes
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'domain': domain_obj.to_dict() if domain_obj else None
            }), 201
        else:
            return jsonify({'success': False, 'error': message}), 400
    
    except Exception as e:
        logger.error(f"Erro ao adicionar domínio: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_api.route('/domains/bulk', methods=['POST'])
@require_admin_api
def add_domains_bulk():
    """Adiciona múltiplos domínios"""
    try:
        data = request.get_json()
        domains = data.get('domains', [])
        
        if not domains:
            return jsonify({'success': False, 'error': 'Lista de domínios vazia'}), 400
        
        result = DomainManager.add_domains_bulk(
            domains=domains,
            added_by=request.user.username,
            source='bulk_manual'
        )
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Erro na adição em massa: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_api.route('/domains/<int:domain_id>', methods=['DELETE'])
@require_admin_api
def remove_domain(domain_id):
    """Remove um domínio"""
    try:
        permanent = request.args.get('permanent', 'false').lower() == 'true'
        
        domain = Domain.get_by_id(domain_id)
        if not domain:
            return jsonify({'success': False, 'error': 'Domínio não encontrado'}), 404
        
        success, message = DomainManager.remove_domain(
            domain=domain.domain,
            performed_by=request.user.username,
            permanent=permanent
        )
        
        if success:
            return jsonify({'success': True, 'message': message}), 200
        else:
            return jsonify({'success': False, 'error': message}), 400
    
    except Exception as e:
        logger.error(f"Erro ao remover domínio: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_api.route('/domains/upload', methods=['POST'])
@require_admin_api
def upload_pdf():
    """Upload e processamento de PDF"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Nome de arquivo vazio'}), 400
        
        # Validar extensão (sem verificar tamanho ainda — arquivo não foi lido)
        valid, error = validate_file_upload(file.filename, -1)  # -1 = ignorar checagem de tamanho
        if not valid:
            return jsonify({'success': False, 'error': error}), 400
        
        # Salvar arquivo
        original_filename = file.filename
        safe_filename = sanitize_filename(original_filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{safe_filename}"
        
        file_path = Config.UPLOAD_FOLDER / filename
        file.save(str(file_path))
        
        # Verificar tamanho real após salvar
        real_size = file_path.stat().st_size
        if real_size == 0:
            file_path.unlink(missing_ok=True)
            return jsonify({'success': False, 'error': 'Arquivo enviado está vazio'}), 400
        
        # Processar PDF
        result = DomainManager.process_pdf_upload(
            file_path=file_path,
            original_filename=original_filename,
            uploaded_by=request.user.username
        )
        
        return jsonify(result), 200 if result['success'] else 400
    
    except Exception as e:
        logger.error(f"Erro no upload de PDF: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# === Gerenciamento de Clientes DNS ===

@admin_api.route('/clients', methods=['GET'])
@require_admin_api
def list_clients():
    """Lista clientes DNS"""
    try:
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        clients = DNSClient.get_all(active_only=active_only)
        logger.info(f"Listando clientes: active_only={active_only}, total={len(clients)}")
        
        return jsonify({
            'success': True,
            'clients': [c.to_dict(include_api_key=False) for c in clients],
            'total': len(clients)
        }), 200
    
    except Exception as e:
        logger.error(f"Erro ao listar clientes: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_api.route('/clients', methods=['POST'])
@require_admin_api
def create_client():
    """Cria novo cliente DNS"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Dados não fornecidos (JSON inválido)'}), 400

        name = data.get('name', '').strip()
        description = data.get('description', '') or ''
        ip_address = data.get('ip_address', '') or ''
        ip_address = ip_address.strip() if ip_address else None
        
        if not name:
            return jsonify({'success': False, 'error': 'Nome não fornecido'}), 400
        
        # Validar formato do IP se fornecido
        if ip_address:
            import ipaddress as ipaddress_mod
            try:
                ipaddress_mod.ip_address(ip_address)
            except ValueError:
                # Tentar como rede (ex: 192.168.1.0/24)
                try:
                    ipaddress_mod.ip_network(ip_address, strict=False)
                except ValueError:
                    return jsonify({'success': False, 'error': f'Endereço IP inválido: {ip_address}'}), 400
        
        logger.info(f"Criando cliente: name={name}, ip={ip_address}, user={request.user.username}")
        
        client = DNSClient.create(
            name=name,
            description=description,
            ip_address=ip_address
        )
        
        logger.info(f"Cliente criado com sucesso: id={client.id}, name={client.name}")
        
        # Verificar imediatamente se o cliente foi persistido
        verify = DNSClient.get_by_id(client.id)
        if not verify:
            logger.error(f"ALERTA: Cliente {client.id} criado mas não encontrado no SELECT subsequente!")
        else:
            logger.info(f"Verificação OK: Cliente {verify.id} encontrado no banco após criação")
        
        return jsonify({
            'success': True,
            'message': 'Cliente criado com sucesso',
            'client': client.to_dict(include_api_key=True)
        }), 201
    
    except Exception as e:
        logger.error(f"Erro ao criar cliente: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_api.route('/clients/<int:client_id>', methods=['GET'])
@require_admin_api
def get_client(client_id):
    """Obtém detalhes de um cliente"""
    try:
        client = DNSClient.get_by_id(client_id)
        
        if not client:
            return jsonify({'success': False, 'error': 'Cliente não encontrado'}), 404
        
        # Buscar histórico recente
        history = SyncHistory.get_by_client(client_id, limit=10)
        
        return jsonify({
            'success': True,
            'client': client.to_dict(include_api_key=True),
            'recent_syncs': [s.to_dict() for s in history]
        }), 200
    
    except Exception as e:
        logger.error(f"Erro ao buscar cliente: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_api.route('/clients/<int:client_id>/regenerate-key', methods=['POST'])
@require_admin_api
def regenerate_client_key(client_id):
    """Regenera API key de um cliente"""
    try:
        client = DNSClient.get_by_id(client_id)
        
        if not client:
            return jsonify({'success': False, 'error': 'Cliente não encontrado'}), 404
        
        new_key = client.regenerate_api_key()
        
        return jsonify({
            'success': True,
            'message': 'API key regenerada com sucesso',
            'api_key': new_key
        }), 200
    
    except Exception as e:
        logger.error(f"Erro ao regenerar API key: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# === Histórico ===

@admin_api.route('/history/domains', methods=['GET'])
@require_admin_api
def get_domain_history():
    """Obtém histórico de domínios"""
    try:
        limit = safe_int(request.args.get('limit', 100), 100)
        action = request.args.get('action', '')
        
        if action:
            history = DomainHistory.get_by_action(action, limit)
        else:
            history = DomainHistory.get_recent(limit)
        
        return jsonify({
            'success': True,
            'history': [h.to_dict() for h in history],
            'total': len(history)
        }), 200
    
    except Exception as e:
        logger.error(f"Erro ao buscar histórico: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_api.route('/history/syncs', methods=['GET'])
@require_admin_api
def get_sync_history():
    """Obtém histórico de sincronizações"""
    try:
        limit = safe_int(request.args.get('limit', 100), 100)
        
        history = SyncHistory.get_recent(limit)
        
        return jsonify({
            'success': True,
            'history': [h.to_dict() for h in history],
            'total': len(history)
        }), 200
    
    except Exception as e:
        logger.error(f"Erro ao buscar histórico de sincronizações: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_api.route('/history/uploads', methods=['GET'])
@require_admin_api
def get_upload_history():
    """Obtém histórico de uploads de PDF"""
    try:
        limit = safe_int(request.args.get('limit', 50), 50)
        
        uploads = PDFUpload.get_recent(limit)
        
        return jsonify({
            'success': True,
            'uploads': [u.to_dict() for u in uploads],
            'total': len(uploads)
        }), 200
    
    except Exception as e:
        logger.error(f"Erro ao buscar histórico de uploads: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# === Gerenciamento de Clientes (complemento) ===

@admin_api.route('/clients/<int:client_id>', methods=['DELETE'])
@require_admin_api
def delete_client(client_id):
    """Remove um cliente DNS"""
    try:
        client = DNSClient.get_by_id(client_id)
        if not client:
            return jsonify({'success': False, 'error': 'Cliente não encontrado'}), 404
        
        client.delete()
        return jsonify({'success': True, 'message': 'Cliente removido com sucesso'}), 200
    
    except Exception as e:
        logger.error(f"Erro ao remover cliente {client_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# === Usuários ===

@admin_api.route('/users/change-password', methods=['POST'])
@require_admin_api
def change_password():
    """Altera senha do usuário logado"""
    try:
        from backend.models.user import User
        data = request.get_json() or {}
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        
        if not current_password or not new_password:
            return jsonify({'success': False, 'error': 'Campos obrigatórios não preenchidos'}), 400
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'error': 'Nova senha deve ter pelo menos 6 caracteres'}), 400
        
        user = User.get_by_username(request.user.username)
        if not user or not user.verify_password(current_password):
            return jsonify({'success': False, 'error': 'Senha atual incorreta'}), 400
        
        user.change_password(new_password)
        return jsonify({'success': True, 'message': 'Senha alterada com sucesso'}), 200
    
    except Exception as e:
        logger.error(f"Erro ao alterar senha: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# === Diagnóstico ===

@admin_api.route('/debug/clients', methods=['GET'])
@require_admin_api
def debug_clients():
    """Endpoint de diagnóstico para verificar clientes diretamente no banco"""
    try:
        from backend.database.db import db
        
        # Query direta ao banco
        raw_result = db.execute_query("SELECT id, name, ip_address, status, active, created_at FROM dns_clients ORDER BY id")
        count_result = db.execute_query("SELECT COUNT(*) as total FROM dns_clients")
        
        return jsonify({
            'success': True,
            'raw_count': count_result[0]['total'] if count_result else 0,
            'raw_clients': [dict(row) for row in raw_result] if raw_result else [],
            'model_count_all': DNSClient.count(active_only=False),
            'model_count_active': DNSClient.count(active_only=True),
            'model_get_all': [c.to_dict() for c in DNSClient.get_all(active_only=False)]
        }), 200
    except Exception as e:
        logger.error(f"Erro no debug de clientes: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# === Cache ===

@admin_api.route('/cache/clear', methods=['POST'])
@require_admin_api
def clear_cache():
    """Limpa o cache Redis"""
    try:
        from backend.services.cache_service import cache
        cache.delete_pattern('*')
        return jsonify({'success': True, 'message': 'Cache limpo com sucesso'}), 200
    except Exception as e:
        logger.error(f"Erro ao limpar cache: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# === Estatísticas ===

@admin_api.route('/stats', methods=['GET'])
@require_admin_api
def get_stats():
    """Obtém estatísticas gerais"""
    try:
        stats = {
            'domains': {
                'total': Domain.count(active_only=False),
                'active': Domain.count(active_only=True),
                'inactive': Domain.count(active_only=False) - Domain.count(active_only=True)
            },
            'clients': {
                'total': DNSClient.count(active_only=False),
                'active': DNSClient.count(active_only=True),
                'online': len([c for c in DNSClient.get_all() if c.status == 'online'])
            },
            'syncs': {
                'recent': len(SyncHistory.get_recent(limit=100)),
                'last_24h': len([s for s in SyncHistory.get_recent(limit=1000) 
                                if (datetime.now() - s.synced_at).days < 1])
            }
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
    
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
