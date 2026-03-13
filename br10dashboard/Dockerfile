FROM python:3.11-slim

# Definir variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Bahia

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    dnsutils \
    iputils-ping \
    net-tools \
    iproute2 \
    procps \
    tzdata \
    && ln -sf /usr/share/zoneinfo/America/Bahia /etc/localtime \
    && echo "America/Bahia" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário não-root
RUN groupadd -r br10 && useradd -r -g br10 br10

# Criar diretórios necessários
RUN mkdir -p /opt/br10dashboard/logs \
    /opt/br10dashboard/data/history \
    /opt/br10dashboard/config \
    /opt/br10dashboard/reports \
    /opt/br10dashboard/scripts \
    /var/lib/br10api \
    && chown -R br10:br10 /opt/br10dashboard /var/lib/br10api

# Definir diretório de trabalho
WORKDIR /opt/br10dashboard

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Copiar aplicação
COPY app.py system_resources.py ./
COPY templates/ templates/
COPY scripts/ scripts/

# Tornar scripts executáveis
RUN chmod +x scripts/*.sh 2>/dev/null || true

# Configurar permissões
RUN chown -R br10:br10 /opt/br10dashboard

# Criar volumes
VOLUME ["/opt/br10dashboard/config", "/opt/br10dashboard/logs", "/opt/br10dashboard/data", "/var/lib/br10api"]

# Expor porta
EXPOSE 8085

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8085/api/stats || exit 1

# Mudar para usuário não-root
USER br10

# Comando de entrada via gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8085", "--workers", "2", "--timeout", "120", "app:app"]
