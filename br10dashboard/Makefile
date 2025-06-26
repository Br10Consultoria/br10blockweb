.PHONY: help build run stop clean logs shell status setup-complete dev

# Colors
RED = \033[31m
GREEN = \033[32m
YELLOW = \033[33m
BLUE = \033[34m
NC = \033[0m

help: ## Mostrar este menu de ajuda
	@echo "$(BLUE)BR10 DNS System - Comandos Docker$(NC)"
	@echo "$(YELLOW)Comandos disponíveis:$(NC)"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup-complete: ## Setup completo: Docker + Nginx + SSL (INTERATIVO)
	@echo "$(BLUE)Iniciando setup completo BR10...$(NC)"
	@if [ "$(shell id -u)" != "0" ]; then \
		echo "$(RED)Execute como root: sudo make setup-complete$(NC)"; \
		exit 1; \
	fi
	@chmod +x setup_br10_complete.sh
	@./setup_br10_complete.sh

build: ## Construir imagens Docker
	@echo "$(BLUE)Construindo imagens BR10...$(NC)"
	docker-compose build

run: ## Iniciar todos os serviços
	@echo "$(GREEN)Iniciando sistema BR10...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)Sistema iniciado!$(NC)"
	@echo "$(YELLOW)Dashboard interno: http://localhost:8084$(NC)"

stop: ## Parar todos os serviços
	@echo "$(YELLOW)Parando sistema BR10...$(NC)"
	docker-compose down

restart: stop run ## Reiniciar todos os serviços

clean: ## Limpar containers e imagens
	@echo "$(RED)Limpando sistema BR10...$(NC)"
	docker-compose down -v
	docker system prune -f

logs: ## Ver logs de todos os serviços
	docker-compose logs -f

logs-dashboard: ## Ver logs do dashboard
	docker-compose logs -f br10-dashboard

logs-api: ## Ver logs do API client
	docker-compose logs -f br10-api-client

logs-nginx: ## Ver logs do Nginx (host)
	@if [ -f /var/log/nginx/br10_access.log ]; then \
		echo "$(BLUE)Logs de acesso Nginx:$(NC)"; \
		tail -f /var/log/nginx/br10_access.log; \
	else \
		echo "$(YELLOW)Logs do Nginx não encontrados$(NC)"; \
	fi

shell-dashboard: ## Acesso shell ao container dashboard
	docker exec -it br10-dashboard /bin/bash

shell-api: ## Acesso shell ao container API
	docker exec -it br10-api-client /bin/bash

status: ## Mostrar status dos serviços
	@echo "$(BLUE)Status dos containers:$(NC)"
	docker-compose ps
	@echo
	@echo "$(BLUE)Status do Nginx (host):$(NC)"
	@systemctl is-active nginx || echo "Nginx não está rodando"

test-ssl: ## Testar certificado SSL
	@if [ -f /etc/br10_domain.conf ]; then \
		DOMAIN=$$(cat /etc/br10_domain.conf); \
		echo "$(BLUE)Testando SSL para $$DOMAIN...$(NC)"; \
		curl -I https://$$DOMAIN || echo "$(YELLOW)HTTPS não disponível$(NC)"; \
	else \
		echo "$(YELLOW)Domínio não configurado$(NC)"; \
	fi

renew-ssl: ## Renovar certificado SSL manualmente
	@echo "$(BLUE)Renovando certificado SSL...$(NC)"
	@sudo certbot renew

dev: ## Modo desenvolvimento (logs em tempo real)
	docker-compose up --build

backup: ## Fazer backup dos dados
	@echo "$(BLUE)Criando backup...$(NC)"
	@mkdir -p backups/$(shell date +%Y%m%d_%H%M%S)
	@tar czf backups/$(shell date +%Y%m%d_%H%M%S)/br10-backup.tar.gz \
		config/ logs/ data/ shared-data/
	@echo "$(GREEN)Backup criado em backups/$(NC)"

monitor: ## Monitorar recursos dos containers
	docker stats br10-dashboard br10-api-client br10-redis br10-unbound
