#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Client Sync Service
======================================
Serviço de sincronização com clientes DNS

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

from backend.models.dns_client import DNSClient
from backend.models.domain import Domain
from backend.models.sync_history import SyncHistory

logger = logging.getLogger(__name__)


class ClientSyncService:
    """Serviço de sincronização com clientes DNS"""
    
    DEFAULT_TIMEOUT = 30  # segundos
    
    @staticmethod
    def push_domains_to_client(
        client: DNSClient,
        domains: Optional[List[str]] = None,
        timeout: int = DEFAULT_TIMEOUT
    ) -> Dict:
        """
        Envia domínios para um cliente via push (se cliente suportar)
        
        Returns:
            Dict com resultado da operação
        """
        try:
            start_time = time.time()
            
            # Se não forneceu domínios, buscar ativos
            if domains is None:
                domains = Domain.get_active_domains_list()
            
            # Criar registro de sincronização
            sync = SyncHistory.create(
                client_id=client.id,
                domains_sent=len(domains),
                status='pending',
                message='Sincronização push iniciada'
            )
            
            # Verificar se cliente tem endpoint configurado
            push_endpoint = client.metadata.get('push_endpoint')
            if not push_endpoint:
                sync.mark_failed("Cliente não possui endpoint de push configurado")
                return {
                    'success': False,
                    'error': 'Cliente não suporta push',
                    'sync_id': sync.id
                }
            
            # Preparar payload
            payload = {
                'domains': domains,
                'total': len(domains),
                'timestamp': datetime.now().isoformat(),
                'sync_id': sync.id
            }
            
            # Headers com API key
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': client.api_key,
                'User-Agent': 'BR10-Server/3.0'
            }
            
            # Enviar requisição
            response = requests.post(
                push_endpoint,
                json=payload,
                headers=headers,
                timeout=timeout
            )
            
            duration = int(time.time() - start_time)
            
            if response.status_code == 200:
                result = response.json()
                domains_applied = result.get('domains_applied', len(domains))
                
                # Atualizar sincronização
                sync.mark_success(domains_applied, duration)
                
                # Atualizar cliente
                client.update_sync_status(domains_applied, 'success')
                
                logger.info(f"Push bem-sucedido para {client.name}: {domains_applied} domínios")
                
                return {
                    'success': True,
                    'sync_id': sync.id,
                    'domains_sent': len(domains),
                    'domains_applied': domains_applied,
                    'duration': duration
                }
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                sync.mark_failed(error_msg, duration)
                
                logger.error(f"Erro no push para {client.name}: {error_msg}")
                
                return {
                    'success': False,
                    'error': error_msg,
                    'sync_id': sync.id
                }
        
        except requests.exceptions.Timeout:
            error_msg = "Timeout na conexão com cliente"
            sync.mark_failed(error_msg)
            logger.error(f"Timeout no push para {client.name}")
            return {'success': False, 'error': error_msg, 'sync_id': sync.id}
        
        except Exception as e:
            error_msg = str(e)
            sync.mark_failed(error_msg)
            logger.error(f"Erro no push para {client.name}: {e}")
            return {'success': False, 'error': error_msg, 'sync_id': sync.id}
    
    @staticmethod
    def push_to_all_clients(
        active_only: bool = True,
        parallel: bool = False
    ) -> Dict:
        """
        Envia domínios para todos os clientes
        
        Returns:
            Dict com resumo das operações
        """
        clients = DNSClient.get_all(active_only=active_only)
        domains = Domain.get_active_domains_list()
        
        results = {
            'total_clients': len(clients),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }
        
        for client in clients:
            # Verificar se cliente suporta push
            if not client.metadata.get('push_endpoint'):
                results['skipped'] += 1
                results['details'].append({
                    'client_id': client.id,
                    'client_name': client.name,
                    'status': 'skipped',
                    'reason': 'No push endpoint'
                })
                continue
            
            # Enviar domínios
            result = ClientSyncService.push_domains_to_client(client, domains)
            
            if result['success']:
                results['success'] += 1
                status = 'success'
            else:
                results['failed'] += 1
                status = 'failed'
            
            results['details'].append({
                'client_id': client.id,
                'client_name': client.name,
                'status': status,
                'sync_id': result.get('sync_id'),
                'error': result.get('error')
            })
        
        logger.info(f"Push para todos os clientes: {results['success']} sucesso, "
                   f"{results['failed']} falhas, {results['skipped']} ignorados")
        
        return results
    
    @staticmethod
    def check_client_health(
        client: DNSClient,
        timeout: int = 10
    ) -> Dict:
        """
        Verifica saúde de um cliente
        
        Returns:
            Dict com status de saúde
        """
        try:
            health_endpoint = client.metadata.get('health_endpoint')
            if not health_endpoint:
                return {
                    'success': False,
                    'error': 'Cliente não possui endpoint de health'
                }
            
            start_time = time.time()
            
            response = requests.get(
                health_endpoint,
                headers={'X-API-Key': client.api_key},
                timeout=timeout
            )
            
            latency = int((time.time() - start_time) * 1000)  # ms
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'status': 'online',
                    'latency_ms': latency,
                    'data': data
                }
            else:
                return {
                    'success': False,
                    'status': 'error',
                    'error': f"HTTP {response.status_code}"
                }
        
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'status': 'timeout',
                'error': 'Timeout na conexão'
            }
        
        except Exception as e:
            return {
                'success': False,
                'status': 'error',
                'error': str(e)
            }
    
    @staticmethod
    def get_stale_clients(hours: int = 24) -> List[DNSClient]:
        """
        Retorna clientes que não sincronizam há X horas
        
        Returns:
            Lista de clientes desatualizados
        """
        all_clients = DNSClient.get_all(active_only=True)
        threshold = datetime.now() - timedelta(hours=hours)
        
        stale = []
        for client in all_clients:
            if not client.last_sync or client.last_sync < threshold:
                stale.append(client)
        
        return stale
    
    @staticmethod
    def get_offline_clients(minutes: int = 30) -> List[DNSClient]:
        """
        Retorna clientes offline (sem heartbeat há X minutos)
        
        Returns:
            Lista de clientes offline
        """
        all_clients = DNSClient.get_all(active_only=True)
        threshold = datetime.now() - timedelta(minutes=minutes)
        
        offline = []
        for client in all_clients:
            if not client.last_heartbeat or client.last_heartbeat < threshold:
                offline.append(client)
        
        return offline
    
    @staticmethod
    def get_sync_statistics(days: int = 7) -> Dict:
        """
        Retorna estatísticas de sincronização
        
        Returns:
            Dict com estatísticas
        """
        threshold = datetime.now() - timedelta(days=days)
        recent_syncs = SyncHistory.get_recent(limit=1000)
        
        # Filtrar por período
        period_syncs = [s for s in recent_syncs if s.synced_at >= threshold]
        
        stats = {
            'period_days': days,
            'total_syncs': len(period_syncs),
            'successful': len([s for s in period_syncs if s.status == 'success']),
            'failed': len([s for s in period_syncs if s.status == 'failed']),
            'pending': len([s for s in period_syncs if s.status == 'pending']),
            'total_domains_sent': sum(s.domains_sent for s in period_syncs),
            'total_domains_applied': sum(s.domains_applied for s in period_syncs),
            'average_duration': 0
        }
        
        # Calcular duração média
        durations = [s.duration_seconds for s in period_syncs if s.duration_seconds]
        if durations:
            stats['average_duration'] = sum(durations) // len(durations)
        
        # Taxa de sucesso
        if stats['total_syncs'] > 0:
            stats['success_rate'] = (stats['successful'] / stats['total_syncs']) * 100
        else:
            stats['success_rate'] = 0
        
        return stats
