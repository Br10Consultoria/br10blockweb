FROM python:3.11-slim

# Definir variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    unbound-utils \
    dnsutils \
    iputils-ping \
    net-tools \
    iproute2 \
    procps \
    sysstat \
    htop \
    iotop \
    systemctl \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário não-root
RUN groupadd -r br10 && useradd -r -g br10 br10

# Criar diretórios necessários
RUN mkdir -p /opt/br10dashboard/logs \
    /opt/br10dashboard/data/history \
    /opt/br10dashboard/config \
    /opt/br10dashboard/reports \
    /var/lib/br10api \
    && chown -R br10:br10 /opt/br10dashboard

# Definir diretório de trabalho
WORKDIR /opt/br10dashboard

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicação
COPY app.py system_resources.py ./
COPY templates/ templates/
COPY static/ static/

# Configurar permissões
RUN chown -R br10:br10 /opt/br10dashboard

# Criar volumes
VOLUME ["/opt/br10dashboard/config", "/opt/br10dashboard/logs", "/opt/br10dashboard/data", "/var/lib/br10api"]

# Expor porta
EXPOSE 8084

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8084/api/stats || exit 1

# Mudar para usuário não-root
USER br10

# Comando de entrada
ENTRYPOINT ["python3", "app.py"]
