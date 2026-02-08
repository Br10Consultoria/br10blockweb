#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - History Service
==================================
Serviço de gerenciamento de histórico

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from backend.models.domain_history import DomainHistory
from backend.models.sync_history import SyncHistory
from backend.models.pdf_upload import PDFUpload
from backend.models.dns_client import DNSClient

logger = logging.getLogger(__name__)


class HistoryService:
    """Serviço de gerenciamento de histórico"""
    
    @staticmethod
    def get_timeline(
        limit: int = 100,
        days: int = 30,
        event_types: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Retorna timeline unificada de eventos
        
        Args:
            limit: Número máximo de eventos
            days: Dias para trás
            event_types: Tipos de eventos a incluir ['domains', 'syncs', 'uploads']
        
        Returns:
            Lista de eventos ordenados por data
        """
        if event_types is None:
            event_types = ['domains', 'syncs', 'uploads']
        
        threshold = datetime.now() - timedelta(days=days)
        events = []
        
        # Eventos de domínios
        if 'domains' in event_types:
            domain_history = DomainHistory.get_recent(limit=limit)
            for item in domain_history:
                if item.performed_at >= threshold:
                    events.append({
                        'type': 'domain',
                        'action': item.action,
                        'timestamp': item.performed_at,
                        'domain': item.domain,
                        'performed_by': item.performed_by,
                        'details': {
                            'old_value': item.old_value,
                            'new_value': item.new_value
                        }
                    })
        
        # Eventos de sincronização
        if 'syncs' in event_types:
            sync_history = SyncHistory.get_recent(limit=limit)
            for item in sync_history:
                if item.synced_at >= threshold:
                    client = DNSClient.get_by_id(item.client_id)
                    events.append({
                        'type': 'sync',
                        'action': 'sync',
                        'timestamp': item.synced_at,
                        'client_name': client.name if client else 'Unknown',
                        'status': item.status,
                        'details': {
                            'domains_sent': item.domains_sent,
                            'domains_applied': item.domains_applied,
                            'duration': item.duration_seconds,
                            'message': item.message
                        }
                    })
        
        # Eventos de upload
        if 'uploads' in event_types:
            uploads = PDFUpload.get_recent(limit=limit)
            for item in uploads:
                if item.uploaded_at >= threshold:
                    events.append({
                        'type': 'upload',
                        'action': 'pdf_upload',
                        'timestamp': item.uploaded_at,
                        'filename': item.original_filename,
                        'uploaded_by': item.uploaded_by,
                        'processed': item.processed,
                        'details': {
                            'domains_extracted': item.domains_extracted,
                            'domains_added': item.domains_added,
                            'domains_duplicated': item.domains_duplicated,
                            'file_size': item.file_size,
                            'error': item.processing_error
                        }
                    })
        
        # Ordenar por timestamp (mais recente primeiro)
        events.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return events[:limit]
    
    @staticmethod
    def get_domain_changes_summary(days: int = 7) -> Dict:
        """
        Retorna resumo de mudanças em domínios
        
        Returns:
            Dict com estatísticas de mudanças
        """
        threshold = datetime.now() - timedelta(days=days)
        history = DomainHistory.get_recent(limit=1000)
        
        # Filtrar por período
        period_history = [h for h in history if h.performed_at >= threshold]
        
        summary = {
            'period_days': days,
            'total_changes': len(period_history),
            'added': len([h for h in period_history if h.action == 'added']),
            'removed': len([h for h in period_history if h.action == 'removed']),
            'activated': len([h for h in period_history if h.action == 'activated']),
            'deactivated': len([h for h in period_history if h.action == 'deactivated']),
            'by_source': {},
            'by_user': {},
            'top_contributors': []
        }
        
        # Agrupar por fonte
        for item in period_history:
            if item.action == 'added':
                source = item.metadata.get('source', 'unknown')
                summary['by_source'][source] = summary['by_source'].get(source, 0) + 1
        
        # Agrupar por usuário
        for item in period_history:
            if item.performed_by:
                summary['by_user'][item.performed_by] = summary['by_user'].get(item.performed_by, 0) + 1
        
        # Top contribuidores
        if summary['by_user']:
            summary['top_contributors'] = sorted(
                summary['by_user'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        
        return summary
    
    @staticmethod
    def get_client_sync_report(client_id: int, days: int = 30) -> Dict:
        """
        Retorna relatório de sincronização de um cliente
        
        Returns:
            Dict com relatório detalhado
        """
        threshold = datetime.now() - timedelta(days=days)
        history = SyncHistory.get_by_client(client_id, limit=1000)
        
        # Filtrar por período
        period_history = [h for h in history if h.synced_at >= threshold]
        
        client = DNSClient.get_by_id(client_id)
        
        report = {
            'client_id': client_id,
            'client_name': client.name if client else 'Unknown',
            'period_days': days,
            'total_syncs': len(period_history),
            'successful': len([h for h in period_history if h.status == 'success']),
            'failed': len([h for h in period_history if h.status == 'failed']),
            'pending': len([h for h in period_history if h.status == 'pending']),
            'success_rate': 0,
            'total_domains_sent': sum(h.domains_sent for h in period_history),
            'total_domains_applied': sum(h.domains_applied for h in period_history),
            'average_duration': 0,
            'last_sync': None,
            'last_success': None,
            'recent_errors': []
        }
        
        # Taxa de sucesso
        if report['total_syncs'] > 0:
            report['success_rate'] = (report['successful'] / report['total_syncs']) * 100
        
        # Duração média
        durations = [h.duration_seconds for h in period_history if h.duration_seconds]
        if durations:
            report['average_duration'] = sum(durations) // len(durations)
        
        # Última sincronização
        if period_history:
            report['last_sync'] = period_history[0].synced_at.isoformat()
        
        # Última sincronização bem-sucedida
        successful = [h for h in period_history if h.status == 'success']
        if successful:
            report['last_success'] = successful[0].synced_at.isoformat()
        
        # Erros recentes
        failed = [h for h in period_history if h.status == 'failed'][:5]
        report['recent_errors'] = [
            {
                'timestamp': h.synced_at.isoformat(),
                'error': h.error_details,
                'message': h.message
            }
            for h in failed
        ]
        
        return report
    
    @staticmethod
    def get_upload_statistics(days: int = 30) -> Dict:
        """
        Retorna estatísticas de uploads de PDF
        
        Returns:
            Dict com estatísticas
        """
        threshold = datetime.now() - timedelta(days=days)
        uploads = PDFUpload.get_recent(limit=1000)
        
        # Filtrar por período
        period_uploads = [u for u in uploads if u.uploaded_at >= threshold]
        
        stats = {
            'period_days': days,
            'total_uploads': len(period_uploads),
            'processed': len([u for u in period_uploads if u.processed]),
            'with_errors': len([u for u in period_uploads if u.processing_error]),
            'total_domains_extracted': sum(u.domains_extracted for u in period_uploads),
            'total_domains_added': sum(u.domains_added for u in period_uploads),
            'total_domains_duplicated': sum(u.domains_duplicated for u in period_uploads),
            'total_file_size': sum(u.file_size for u in period_uploads),
            'by_user': {},
            'recent_uploads': []
        }
        
        # Agrupar por usuário
        for upload in period_uploads:
            if upload.uploaded_by:
                stats['by_user'][upload.uploaded_by] = stats['by_user'].get(upload.uploaded_by, 0) + 1
        
        # Uploads recentes
        stats['recent_uploads'] = [
            {
                'filename': u.original_filename,
                'uploaded_at': u.uploaded_at.isoformat(),
                'uploaded_by': u.uploaded_by,
                'domains_extracted': u.domains_extracted,
                'domains_added': u.domains_added,
                'processed': u.processed,
                'error': u.processing_error
            }
            for u in period_uploads[:10]
        ]
        
        return stats
    
    @staticmethod
    def export_history_to_csv(
        output_path: str,
        event_types: Optional[List[str]] = None,
        days: int = 30
    ) -> bool:
        """
        Exporta histórico para arquivo CSV
        
        Returns:
            True se sucesso
        """
        try:
            import csv
            
            timeline = HistoryService.get_timeline(
                limit=10000,
                days=days,
                event_types=event_types
            )
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Cabeçalho
                writer.writerow([
                    'Timestamp',
                    'Type',
                    'Action',
                    'Details'
                ])
                
                # Dados
                for event in timeline:
                    writer.writerow([
                        event['timestamp'].isoformat(),
                        event['type'],
                        event['action'],
                        str(event.get('details', {}))
                    ])
            
            logger.info(f"Histórico exportado para: {output_path}")
            return True
        
        except Exception as e:
            logger.error(f"Erro ao exportar histórico: {e}")
            return False
