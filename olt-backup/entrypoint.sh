#!/bin/bash
set -e

# Exporta todas as variáveis de ambiente para um arquivo que o cron pode ler
printenv | grep -v "no_proxy" > /etc/environment

# Instala o crontab
crontab /app/crontab

# Cria o arquivo de log
touch /var/log/cron.log

echo "============================================="
echo " OLT Backup Docker Container"
echo " Cron agendado: 13:00 e 22:00 ($TZ)"
echo " $(date)"
echo "============================================="

# Inicia o cron em foreground e exibe o log
cron && tail -f /var/log/cron.log
