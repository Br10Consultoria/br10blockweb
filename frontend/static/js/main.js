// BR10 Block Web - Main JavaScript

// Configuração global
const API_BASE = '/api/v1';

// Utilitários
const utils = {
    // Formatar timestamp
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleString('pt-BR');
    },
    
    // Formatar tamanho de arquivo
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    },
    
    // Mostrar toast
    showToast(message, type = 'info') {
        const alertClass = type === 'error' ? 'danger' : type;
        const alert = `
            <div class="alert alert-${alertClass} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        $('#toast-container').html(alert);
        setTimeout(() => {
            $('.alert').alert('close');
        }, 5000);
    },
    
    // Mostrar loading
    showLoading() {
        const spinner = `
            <div class="spinner-overlay" id="loading-spinner">
                <div class="spinner-border text-light" role="status" style="width: 3rem; height: 3rem;">
                    <span class="visually-hidden">Carregando...</span>
                </div>
            </div>
        `;
        $('body').append(spinner);
    },
    
    // Esconder loading
    hideLoading() {
        $('#loading-spinner').remove();
    }
};

// Upload de PDF com drag & drop
class PDFUploader {
    constructor(dropAreaId, fileInputId) {
        this.dropArea = document.getElementById(dropAreaId);
        this.fileInput = document.getElementById(fileInputId);
        
        if (this.dropArea && this.fileInput) {
            this.init();
        }
    }
    
    init() {
        // Prevenir comportamento padrão
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            this.dropArea.addEventListener(eventName, this.preventDefaults, false);
        });
        
        // Highlight ao arrastar
        ['dragenter', 'dragover'].forEach(eventName => {
            this.dropArea.addEventListener(eventName, () => {
                this.dropArea.classList.add('dragover');
            }, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            this.dropArea.addEventListener(eventName, () => {
                this.dropArea.classList.remove('dragover');
            }, false);
        });
        
        // Handle drop
        this.dropArea.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            this.handleFiles(files);
        }, false);
        
        // Handle click
        this.dropArea.addEventListener('click', () => {
            this.fileInput.click();
        });
        
        // Handle file input change
        this.fileInput.addEventListener('change', (e) => {
            this.handleFiles(e.target.files);
        });
    }
    
    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    handleFiles(files) {
        if (files.length === 0) return;
        
        const file = files[0];
        
        // Validar tipo
        if (!file.type.includes('pdf')) {
            utils.showToast('Por favor, selecione um arquivo PDF', 'error');
            return;
        }
        
        // Validar tamanho (50MB)
        if (file.size > 50 * 1024 * 1024) {
            utils.showToast('Arquivo muito grande. Máximo: 50MB', 'error');
            return;
        }
        
        this.uploadFile(file);
    }
    
    uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        utils.showLoading();
        
        fetch(`${API_BASE}/admin/domains/upload`, {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            utils.hideLoading();
            
            if (data.success) {
                utils.showToast(
                    `Upload concluído! ${data.domains_added} domínios adicionados, ${data.domains_duplicated} duplicados.`,
                    'success'
                );
                
                // Mostrar preview
                if (data.domains_preview) {
                    this.showPreview(data.domains_preview);
                }
                
                // Recarregar página após 3 segundos
                setTimeout(() => {
                    window.location.reload();
                }, 3000);
            } else {
                utils.showToast(`Erro: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            utils.hideLoading();
            utils.showToast(`Erro no upload: ${error.message}`, 'error');
        });
    }
    
    showPreview(preview) {
        const previewHtml = `
            <div class="card mt-4">
                <div class="card-header">
                    <h5>Preview dos Domínios Extraídos</h5>
                </div>
                <div class="card-body">
                    <p><strong>Total:</strong> ${preview.total} domínios</p>
                    <p><strong>TLDs únicos:</strong> ${preview.statistics.unique_tlds}</p>
                    <div class="mt-3">
                        <h6>Primeiros domínios:</h6>
                        <ul class="list-unstyled">
                            ${preview.preview.slice(0, 10).map(d => `<li><code>${d}</code></li>`).join('')}
                        </ul>
                        ${preview.has_more ? `<p class="text-muted">... e mais ${preview.total - preview.showing} domínios</p>` : ''}
                    </div>
                </div>
            </div>
        `;
        
        $('#upload-preview').html(previewHtml);
    }
}

// API Client Manager
class APIClientManager {
    static async regenerateKey(clientId) {
        if (!confirm('Tem certeza que deseja regenerar a API key? A chave antiga será invalidada.')) {
            return;
        }
        
        utils.showLoading();
        
        try {
            const response = await fetch(`${API_BASE}/admin/clients/${clientId}/regenerate-key`, {
                method: 'POST'
            });
            
            const data = await response.json();
            utils.hideLoading();
            
            if (data.success) {
                utils.showToast('API key regenerada com sucesso!', 'success');
                
                // Mostrar nova chave
                const modal = `
                    <div class="modal fade" id="apiKeyModal" tabindex="-1">
                        <div class="modal-dialog">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title">Nova API Key</h5>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                </div>
                                <div class="modal-body">
                                    <p class="alert alert-warning">
                                        <i class="fas fa-exclamation-triangle"></i>
                                        Copie esta chave agora. Ela não será mostrada novamente!
                                    </p>
                                    <div class="input-group">
                                        <input type="text" class="form-control" id="newApiKey" value="${data.api_key}" readonly>
                                        <button class="btn btn-outline-secondary" onclick="copyApiKey()">
                                            <i class="fas fa-copy"></i> Copiar
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                
                $('body').append(modal);
                const modalInstance = new bootstrap.Modal(document.getElementById('apiKeyModal'));
                modalInstance.show();
            } else {
                utils.showToast(`Erro: ${data.error}`, 'error');
            }
        } catch (error) {
            utils.hideLoading();
            utils.showToast(`Erro: ${error.message}`, 'error');
        }
    }
}

// Copiar API key
function copyApiKey() {
    const input = document.getElementById('newApiKey');
    input.select();
    document.execCommand('copy');
    utils.showToast('API key copiada!', 'success');
}

// Auto-refresh de status
function startAutoRefresh(interval = 30000) {
    setInterval(() => {
        // Atualizar status dos clientes se estiver na página
        if ($('#clients-status').length) {
            refreshClientsStatus();
        }
    }, interval);
}

async function refreshClientsStatus() {
    try {
        const response = await fetch(`${API_BASE}/admin/clients`);
        const data = await response.json();
        
        if (data.success) {
            // Atualizar badges de status
            data.clients.forEach(client => {
                const badge = $(`#client-${client.id}-status`);
                if (badge.length) {
                    badge.removeClass('bg-success bg-warning bg-secondary bg-danger');
                    
                    if (client.status === 'online') {
                        badge.addClass('bg-success').text('Online');
                    } else if (client.status === 'syncing') {
                        badge.addClass('bg-warning').text('Syncing');
                    } else if (client.status === 'error') {
                        badge.addClass('bg-danger').text('Error');
                    } else {
                        badge.addClass('bg-secondary').text('Offline');
                    }
                }
            });
        }
    } catch (error) {
        console.error('Erro ao atualizar status:', error);
    }
}

// Inicialização
$(document).ready(function() {
    // Criar container de toasts
    if (!$('#toast-container').length) {
        $('main').prepend('<div id="toast-container" class="container mt-3"></div>');
    }
    
    // Inicializar uploader se existir
    if ($('#upload-area').length) {
        new PDFUploader('upload-area', 'file-input');
    }
    
    // Auto-refresh
    startAutoRefresh();
    
    // Tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
