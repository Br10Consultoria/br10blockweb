#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Main Application
===================================
Aplicação Flask principal refatorada

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import logging
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from backend.config import Config
from backend.database.db import db
from backend.api.client_routes import client_api
from backend.api.admin_routes import admin_api
from backend.api.auth import require_admin
from backend.models.user import User
from backend.models.domain import Domain
from backend.models.dns_client import DNSClient
from backend.models.sync_history import SyncHistory
from backend.models.pdf_upload import PDFUpload
from backend.services.cache_service import cache
from backend.services.history_service import HistoryService

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app(config=None):
    """Factory para criar aplicação Flask"""
    app = Flask(
        __name__,
        template_folder='../frontend/templates',
        static_folder='../frontend/static'
    )
    
    # Configuração
    if config:
        app.config.from_object(config)
    else:
        app.config.from_object(Config)
    
    # Secret key para sessões
    app.secret_key = Config.SECRET_KEY
    
    # Registrar blueprints
    app.register_blueprint(client_api)
    app.register_blueprint(admin_api)
    
    # Criar diretórios necessários
    Config.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    Config.DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    
    # Inicializar banco de dados
    try:
        db.initialize()
        logger.info("Banco de dados inicializado")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco: {e}")
    
    # Verificar Redis
    if cache.is_available:
        logger.info("Cache Redis disponível")
    else:
        logger.warning("Cache Redis não disponível - funcionando sem cache")
    
    return app


# Criar aplicação
app = create_app()


# === Rotas de Autenticação ===

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Usuário e senha são obrigatórios', 'error')
            return render_template('login.html')
        
        user = User.get_by_username(username)
        
        if user and user.verify_password(password):
            if not user.active:
                flash('Usuário inativo', 'error')
                return render_template('login.html')
            
            # Criar sessão
            session['user'] = {
                'id': user.id,
                'username': user.username,
                'role': user.role
            }
            
            logger.info(f"Login bem-sucedido: {username}")
            
            next_url = request.args.get('next')
            return redirect(next_url or url_for('dashboard'))
        else:
            flash('Usuário ou senha inválidos', 'error')
            logger.warning(f"Tentativa de login falha: {username}")
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout"""
    username = session.get('user', {}).get('username', 'Unknown')
    session.clear()
    logger.info(f"Logout: {username}")
    flash('Logout realizado com sucesso', 'success')
    return redirect(url_for('login'))


# === Rotas Principais ===

@app.route('/')
def index():
    """Página inicial - redireciona para dashboard ou login"""
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/dashboard')
@require_admin
def dashboard():
    """Dashboard principal"""
    try:
        # Estatísticas gerais
        stats = {
            'domains': {
                'total': Domain.count(active_only=False),
                'active': Domain.count(active_only=True)
            },
            'clients': {
                'total': DNSClient.count(active_only=False),
                'active': DNSClient.count(active_only=True),
                'online': len([c for c in DNSClient.get_all() if c.status == 'online'])
            },
            'uploads': {
                'total': len(PDFUpload.get_recent(limit=1000)),
                'recent': len(PDFUpload.get_recent(limit=10))
            }
        }
        
        # Timeline recente
        timeline = HistoryService.get_timeline(limit=20, days=7)
        
        # Clientes recentes
        clients = DNSClient.get_all(active_only=True)[:10]
        
        # Sincronizações recentes
        recent_syncs = SyncHistory.get_recent(limit=10)
        
        return render_template(
            'dashboard.html',
            stats=stats,
            timeline=timeline,
            clients=clients,
            recent_syncs=recent_syncs
        )
    
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
        flash('Erro ao carregar dashboard', 'error')
        return render_template('dashboard.html', stats={}, timeline=[], clients=[], recent_syncs=[])


@app.route('/domains')
@require_admin
def domains_list():
    """Lista de domínios"""
    try:
        page = int(request.args.get('page', 1))
        search = request.args.get('search', '').strip()
        
        domains = Domain.get_all(active_only=True, search=search)
        total = Domain.count(active_only=True, search=search)
        
        return render_template(
            'domains.html',
            domains=domains[:50],  # Limitar para performance
            total=total,
            page=page,
            search=search
        )
    
    except Exception as e:
        logger.error(f"Erro ao listar domínios: {e}")
        flash('Erro ao carregar domínios', 'error')
        return render_template('domains.html', domains=[], total=0)


@app.route('/domains/upload')
@require_admin
def domains_upload():
    """Página de upload de PDF"""
    return render_template('upload.html')


@app.route('/clients')
@require_admin
def clients_list():
    """Lista de clientes DNS"""
    try:
        clients = DNSClient.get_all(active_only=False)
        
        return render_template('clients.html', clients=clients)
    
    except Exception as e:
        logger.error(f"Erro ao listar clientes: {e}")
        flash('Erro ao carregar clientes', 'error')
        return render_template('clients.html', clients=[])


@app.route('/clients/<int:client_id>')
@require_admin
def client_detail(client_id):
    """Detalhes de um cliente"""
    try:
        client = DNSClient.get_by_id(client_id)
        
        if not client:
            flash('Cliente não encontrado', 'error')
            return redirect(url_for('clients_list'))
        
        # Histórico de sincronizações
        sync_history = SyncHistory.get_by_client(client_id, limit=50)
        
        # Relatório
        report = HistoryService.get_client_sync_report(client_id, days=30)
        
        return render_template(
            'client_detail.html',
            client=client,
            sync_history=sync_history,
            report=report
        )
    
    except Exception as e:
        logger.error(f"Erro ao carregar cliente {client_id}: {e}")
        flash('Erro ao carregar cliente', 'error')
        return redirect(url_for('clients_list'))


@app.route('/history')
@require_admin
def history():
    """Histórico completo"""
    try:
        event_type = request.args.get('type', 'all')
        days = int(request.args.get('days', 7))
        
        if event_type == 'all':
            timeline = HistoryService.get_timeline(limit=100, days=days)
        else:
            timeline = HistoryService.get_timeline(
                limit=100,
                days=days,
                event_types=[event_type]
            )
        
        return render_template(
            'history.html',
            timeline=timeline,
            event_type=event_type,
            days=days
        )
    
    except Exception as e:
        logger.error(f"Erro ao carregar histórico: {e}")
        flash('Erro ao carregar histórico', 'error')
        return render_template('history.html', timeline=[])


@app.route('/settings')
@require_admin
def settings():
    """Configurações do sistema"""
    try:
        # Estatísticas do Redis
        redis_stats = cache.get_stats()
        
        # Estatísticas do banco
        db_stats = {
            'domains': Domain.count(active_only=False),
            'clients': DNSClient.count(active_only=False),
            'uploads': len(PDFUpload.get_recent(limit=10000))
        }
        
        return render_template(
            'settings.html',
            redis_stats=redis_stats,
            db_stats=db_stats
        )
    
    except Exception as e:
        logger.error(f"Erro ao carregar configurações: {e}")
        flash('Erro ao carregar configurações', 'error')
        return render_template('settings.html')


# === Handlers de Erro ===

@app.errorhandler(404)
def not_found(error):
    """Página não encontrada"""
    return render_template('error.html', error='Página não encontrada', code=404), 404


@app.errorhandler(500)
def internal_error(error):
    """Erro interno"""
    logger.error(f"Erro interno: {error}")
    return render_template('error.html', error='Erro interno do servidor', code=500), 500


# === Context Processors ===

@app.context_processor
def inject_globals():
    """Injeta variáveis globais nos templates"""
    return {
        'app_name': 'BR10 Block Web',
        'app_version': '3.0.0',
        'current_year': datetime.now().year,
        'user': session.get('user')
    }


if __name__ == '__main__':
    # Modo de desenvolvimento
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
