# BR10 Block Web - Dockerfile
# Versão: 3.0.0
# Data: 2026-02-08

FROM python:3.11-slim

# Metadados
LABEL maintainer="BR10 Team"
LABEL version="3.0.0"
LABEL description="BR10 Block Web - Sistema de Bloqueio de Domínios"

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Criar diretório da aplicação
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copiar código da aplicação
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY .env.example .env

# Criar diretórios necessários
RUN mkdir -p uploads data/backups logs

# Expor porta
EXPOSE 8084

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8084/health || exit 1

# Comando de inicialização
CMD ["python", "-m", "backend.app"]
