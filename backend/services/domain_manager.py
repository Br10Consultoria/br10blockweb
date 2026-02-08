#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BR10 Block Web - Domain Manager Service
=========================================
Serviço para gerenciamento de domínios bloqueados

Autor: BR10 Team
Versão: 3.0.0
Data: 2026-02-08
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.config import Config
from backend.models.domain import Domain
from backend.models.domain_history import DomainHistory
from backend.models.pdf_upload import PDFUpload
from backend.services.pdf_extractor import PDFExtractor

logger = logging.getLogger(__name__)


class DomainManager:
    """Serviço de gerenciamento de domínios"""
    
    @staticmethod
    def add_domain(
        domain: str,
        added_by: Optional[str] = None,
        source: str = 'manual',
        source_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Domain]]:
        """
        Adiciona um domínio
        
        Returns:
            (sucesso, mensagem, domínio)
        """
        try:
            # Verificar se já existe
            if Domain.exists(domain):
                existing = Domain.get_by_domain(domain)
                if existing.active:
                    return False, "Domínio já existe e está ativo", existing
                else:
                    # Reativar domínio inativo
                    existing.activate()
                    DomainHistory.log_activation(
                        domain_id=existing.id,
                        domain=domain,
                        performed_by=added_by
                    )
                    return True, "Domínio reativado com sucesso", existing
            
            # Criar novo domínio
            new_domain = Domain.create(
                domain=domain,
                added_by=added_by,
                source=source,
                source_reference=source_reference,
                notes=notes
            )
            
            # Registrar no histórico
            DomainHistory.log_addition(
                domain_id=new_domain.id,
                domain=domain,
                performed_by=added_by,
                source=source
            )
            
            logger.info(f"Domínio adicionado: {domain} por {added_by}")
            return True, "Domínio adicionado com sucesso", new_domain
        
        except Exception as e:
            logger.error(f"Erro ao adicionar domínio {domain}: {e}")
            return False, f"Erro ao adicionar domínio: {str(e)}", None
    
    @staticmethod
    def add_domains_bulk(
        domains: List[str],
        added_by: Optional[str] = None,
        source: str = 'bulk',
        source_reference: Optional[str] = None
    ) -> Dict:
        """
        Adiciona múltiplos domínios
        
        Returns:
            Dict com estatísticas da operação
        """
        try:
            # Filtrar domínios válidos
            valid_domains = [d.strip().lower() for d in domains if d.strip()]
            valid_domains = [d for d in valid_domains if PDFExtractor.validate_domain(d)]
            
            # Adicionar em massa
            added, duplicated = Domain.bulk_create(
                domains=valid_domains,
                added_by=added_by,
                source=source,
                source_reference=source_reference
            )
            
            # Registrar no histórico (apenas os adicionados)
            if added > 0:
                # Buscar domínios recém adicionados para registrar no histórico
                recent_domains = Domain.get_all(limit=added)
                for domain in recent_domains:
                    if domain.source == source and domain.source_reference == source_reference:
                        DomainHistory.log_addition(
                            domain_id=domain.id,
                            domain=domain.domain,
                            performed_by=added_by,
                            source=source
                        )
            
            logger.info(f"Adição em massa: {added} adicionados, {duplicated} duplicados")
            
            return {
                'success': True,
                'total_submitted': len(valid_domains),
                'added': added,
                'duplicated': duplicated,
                'invalid': len(domains) - len(valid_domains)
            }
        
        except Exception as e:
            logger.error(f"Erro na adição em massa: {e}")
            return {
                'success': False,
                'error': str(e),
                'added': 0,
                'duplicated': 0
            }
    
    @staticmethod
    def process_pdf_upload(
        file_path: Path,
        original_filename: str,
        uploaded_by: Optional[str] = None
    ) -> Dict:
        """
        Processa upload de PDF e extrai domínios
        
        Returns:
            Dict com resultado do processamento
        """
        try:
            # Calcular hash e tamanho
            file_hash = PDFExtractor.calculate_file_hash(file_path)
            file_size = file_path.stat().st_size
            
            # Verificar se já foi processado
            existing_upload = PDFUpload.get_by_hash(file_hash)
            if existing_upload and existing_upload.processed:
                logger.warning(f"PDF já foi processado anteriormente: {original_filename}")
                return {
                    'success': False,
                    'error': 'Este arquivo já foi processado anteriormente',
                    'previous_upload': existing_upload.to_dict()
                }
            
            # Criar registro de upload
            pdf_upload = PDFUpload.create(
                filename=file_path.name,
                original_filename=original_filename,
                file_size=file_size,
                file_hash=file_hash,
                uploaded_by=uploaded_by
            )
            
            # Extrair domínios
            extraction_result = PDFExtractor.extract_domains(file_path)
            
            if not extraction_result['success'] or not extraction_result['domains']:
                pdf_upload.mark_error("Nenhum domínio encontrado no PDF")
                return {
                    'success': False,
                    'error': 'Nenhum domínio encontrado no PDF',
                    'upload_id': pdf_upload.id
                }
            
            domains = extraction_result['domains']
            
            # Adicionar domínios ao banco
            bulk_result = DomainManager.add_domains_bulk(
                domains=domains,
                added_by=uploaded_by,
                source='pdf',
                source_reference=original_filename
            )
            
            # Atualizar registro de upload
            pdf_upload.mark_processed(
                domains_extracted=len(domains),
                domains_added=bulk_result['added'],
                domains_duplicated=bulk_result['duplicated']
            )
            
            logger.info(f"PDF processado: {original_filename} - {len(domains)} domínios extraídos")
            
            return {
                'success': True,
                'upload_id': pdf_upload.id,
                'domains_extracted': len(domains),
                'domains_added': bulk_result['added'],
                'domains_duplicated': bulk_result['duplicated'],
                'domains_preview': PDFExtractor.preview_domains(domains),
                'extraction_metadata': extraction_result['extraction_metadata']
            }
        
        except Exception as e:
            logger.error(f"Erro ao processar PDF {original_filename}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def remove_domain(
        domain: str,
        performed_by: Optional[str] = None,
        permanent: bool = False
    ) -> Tuple[bool, str]:
        """
        Remove um domínio (soft ou hard delete)
        
        Returns:
            (sucesso, mensagem)
        """
        try:
            domain_obj = Domain.get_by_domain(domain)
            
            if not domain_obj:
                return False, "Domínio não encontrado"
            
            if permanent:
                # Registrar antes de deletar
                DomainHistory.log_removal(
                    domain_id=domain_obj.id,
                    domain=domain,
                    performed_by=performed_by
                )
                domain_obj.delete()
                logger.info(f"Domínio removido permanentemente: {domain}")
                return True, "Domínio removido permanentemente"
            else:
                # Soft delete
                domain_obj.deactivate()
                DomainHistory.log_deactivation(
                    domain_id=domain_obj.id,
                    domain=domain,
                    performed_by=performed_by
                )
                logger.info(f"Domínio desativado: {domain}")
                return True, "Domínio desativado"
        
        except Exception as e:
            logger.error(f"Erro ao remover domínio {domain}: {e}")
            return False, f"Erro ao remover domínio: {str(e)}"
    
    @staticmethod
    def export_to_file(
        file_path: Path,
        active_only: bool = True,
        format: str = 'txt'
    ) -> Tuple[bool, str]:
        """
        Exporta domínios para arquivo
        
        Returns:
            (sucesso, mensagem)
        """
        try:
            domains = Domain.get_active_domains_list() if active_only else [d.domain for d in Domain.get_all(active_only=False)]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                if format == 'txt':
                    f.write('\n'.join(domains))
                elif format == 'rpz':
                    # Formato RPZ para Unbound
                    f.write('; BR10 Block Web - RPZ Zone File\n')
                    f.write(f'; Total domains: {len(domains)}\n')
                    f.write(f'; Generated: {Path.ctime(file_path)}\n\n')
                    for domain in domains:
                        f.write(f'{domain} CNAME .\n')
            
            logger.info(f"Domínios exportados para: {file_path}")
            return True, f"{len(domains)} domínios exportados"
        
        except Exception as e:
            logger.error(f"Erro ao exportar domínios: {e}")
            return False, f"Erro ao exportar: {str(e)}"
    
    @staticmethod
    def sync_to_unbound() -> Tuple[bool, str]:
        """
        Sincroniza domínios com arquivo de zona do Unbound
        
        Returns:
            (sucesso, mensagem)
        """
        try:
            zone_file = Config.UNBOUND_ZONE_FILE
            
            # Exportar para arquivo de zona
            success, message = DomainManager.export_to_file(
                file_path=zone_file,
                active_only=True,
                format='rpz'
            )
            
            if success:
                # Recarregar Unbound (se disponível)
                try:
                    import subprocess
                    subprocess.run(['unbound-control', 'reload'], check=True, timeout=10)
                    logger.info("Unbound recarregado com sucesso")
                    return True, f"{message} e Unbound recarregado"
                except Exception as e:
                    logger.warning(f"Não foi possível recarregar Unbound: {e}")
                    return True, f"{message} (Unbound não recarregado)"
            
            return False, message
        
        except Exception as e:
            logger.error(f"Erro ao sincronizar com Unbound: {e}")
            return False, f"Erro na sincronização: {str(e)}"
