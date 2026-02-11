FROM python:3.11-slim

# Instala cron e dependências do sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends cron tzdata && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Define o timezone (sobrescrito pelo .env via docker-compose)
ENV TZ=America/Bahia
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Diretório de trabalho
WORKDIR /app

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia os arquivos da aplicação
COPY backup_olts.py .
COPY olts_config.py .
COPY crontab .
COPY entrypoint.sh .

# Cria diretório de backups
RUN mkdir -p /app/backups

# Permissões
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
