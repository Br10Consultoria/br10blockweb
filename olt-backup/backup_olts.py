#!/usr/bin/env python3
"""
Script unificado de backup de OLTs (Datacom, ZTE, ZTE Titan)
com envio automático de notificações para o Telegram.

- Cada OLT é processada individualmente.
- Logo após o backup de cada OLT, uma mensagem é enviada ao Telegram
  informando sucesso ou falha.
- Ao final, um resumo geral é enviado.

Todas as credenciais são lidas de variáveis de ambiente (.env).
"""

import os
import sys
import time
import telnetlib
import logging
from datetime import datetime

import requests

from olts_config import get_olts

# ============================================================
# Logging
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("olt-backup")

# ============================================================
# Variáveis de ambiente
# ============================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TFTP_IP = os.getenv("TFTP_IP", "")
FTP_IP = os.getenv("FTP_IP", "")
FTP_USER = os.getenv("FTP_USER", "")
FTP_PASSWORD = os.getenv("FTP_PASSWORD", "")

BACKUP_DIR = "/app/backups"

# ============================================================
# Telegram helpers
# ============================================================

def telegram_send_message(text: str):
    """Envia uma mensagem de texto para o chat do Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram não configurado. Mensagem não enviada.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        resp = requests.post(url, data=data, timeout=30)
        if resp.status_code == 200:
            log.info("Mensagem Telegram enviada com sucesso.")
        else:
            log.error("Erro ao enviar mensagem Telegram: %s", resp.text)
    except Exception as exc:
        log.error("Exceção ao enviar mensagem Telegram: %s", exc)


def telegram_send_file(filepath: str):
    """Envia um arquivo para o chat do Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram não configurado. Arquivo não enviado.")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    data = {"chat_id": TELEGRAM_CHAT_ID}
    try:
        with open(filepath, "rb") as f:
            resp = requests.post(url, data=data, files={"document": f}, timeout=120)
        if resp.status_code == 200:
            log.info("Arquivo %s enviado ao Telegram.", filepath)
            return True
        else:
            log.error("Erro ao enviar arquivo %s: %s", filepath, resp.text)
            return False
    except Exception as exc:
        log.error("Exceção ao enviar arquivo %s: %s", filepath, exc)
        return False


# ============================================================
# Telnet helpers
# ============================================================

def send_command(tn, command: str, wait_time: int = 2) -> str:
    """Envia um comando via Telnet e retorna a resposta."""
    log.info("Enviando comando: %s", command)
    tn.write(command.encode("ascii") + b"\n")
    time.sleep(wait_time)
    response = tn.read_very_eager().decode("ascii", errors="replace")
    log.info("Resposta: %s", response.strip()[:500])
    return response


# ============================================================
# Backup Datacom
# ============================================================

def backup_olt_datacom(olt_name: str, olt_info: dict) -> str | None:
    """Realiza backup de uma OLT Datacom via Telnet + TFTP."""
    try:
        log.info("Conectando à OLT %s (%s) via Telnet...", olt_name, olt_info["ip"])

        tn = telnetlib.Telnet(olt_info["ip"], olt_info["port"], timeout=15)

        # Login
        tn.read_until(b"login:", timeout=10)
        tn.write(olt_info["user"].encode("ascii") + b"\n")
        tn.read_until(b"Password:", timeout=10)
        tn.write(olt_info["password"].encode("ascii") + b"\n")

        tn.read_until(b"Welcome to the DmOS CLI", timeout=10)
        log.info("Conexão estabelecida na OLT %s", olt_name)

        # Modo de configuração
        send_command(tn, "config")

        # Nome do arquivo de backup
        ts = datetime.now().strftime("%d%m%y_%H%M")
        backup_filename = f"backupolt{olt_name.lower()}{ts}.txt"

        # Salvar backup
        send_command(tn, f"save {backup_filename}")

        log.info("Aguardando 60s para garantir que o backup foi salvo...")
        time.sleep(60)

        # Enviar para TFTP
        send_command(tn, f"copy file {backup_filename} tftp://{TFTP_IP}")
        tn.read_until(b"Transfer complete.", timeout=30)
        log.info("Backup da OLT %s transferido para TFTP.", olt_name)

        tn.write(b"exit\n")
        tn.close()
        log.info("Backup da OLT %s concluído.", olt_name)
        return backup_filename

    except Exception as exc:
        log.error("Erro ao fazer backup da OLT %s: %s", olt_name, exc)
        return None


# ============================================================
# Backup ZTE
# ============================================================

def backup_zte_olt(olt_name: str, olt_info: dict) -> str | None:
    """Realiza backup de uma OLT ZTE via Telnet + FTP."""
    try:
        log.info("Conectando à OLT %s (%s) via Telnet...", olt_name, olt_info["ip"])

        tn = telnetlib.Telnet(olt_info["ip"], olt_info["port"], timeout=15)

        # Login
        tn.read_until(b"login:", timeout=10)
        tn.write(olt_info["user"].encode("ascii") + b"\n")
        tn.read_until(b"Password:", timeout=10)
        tn.write(olt_info["password"].encode("ascii") + b"\n")

        send_command(tn, "configure terminal")

        ftp_cmd = (
            f"file upload cfg-startup startrun.dat ftp ipaddress {FTP_IP} "
            f"user {FTP_USER} password {FTP_PASSWORD}"
        )
        send_command(tn, ftp_cmd)
        send_command(tn, "manual-backup all")

        tn.write(b"exit\n")
        tn.close()
        log.info("Backup da OLT %s via Telnet concluído.", olt_name)

        ts = datetime.now().strftime("%d%m%y_%H%M")
        return f"backupolt{olt_name.lower()}{ts}.dat"

    except Exception as exc:
        log.error("Erro ao fazer backup da OLT %s: %s", olt_name, exc)
        return None


# ============================================================
# Backup ZTE Titan
# ============================================================

def backup_zte_titan(olt_name: str, olt_info: dict) -> str | None:
    """Realiza backup da OLT ZTE Titan Canavieiras via Telnet + FTP."""
    try:
        log.info("Conectando à OLT %s (%s) via Telnet...", olt_name, olt_info["ip"])

        tn = telnetlib.Telnet(olt_info["ip"], olt_info["port"], timeout=15)

        # Login
        tn.read_until(b"login:", timeout=10)
        tn.write(olt_info["user"].encode("ascii") + b"\n")
        tn.read_until(b"Password:", timeout=10)
        tn.write(olt_info["password"].encode("ascii") + b"\n")

        time.sleep(3)

        backup_cmd = (
            f"copy ftp root: /datadisk0/DATA0/startrun.dat "
            f"//{FTP_IP}/startrun.dat@{FTP_USER}:{FTP_PASSWORD}"
        )
        send_command(tn, backup_cmd, wait_time=10)

        log.info("Aguardando 30s para conclusão do backup ZTE Titan...")
        time.sleep(30)

        tn.write(b"exit\n")
        tn.close()
        log.info("Backup da OLT %s concluído.", olt_name)

        ts = datetime.now().strftime("%d%m%y_%H%M")
        return f"backupolt{olt_name.lower()}{ts}.dat"

    except Exception as exc:
        log.error("Erro ao fazer backup da OLT %s: %s", olt_name, exc)
        return None


# ============================================================
# Envio de backups locais para Telegram
# ============================================================

def enviar_backups_telegram():
    """Busca arquivos de backup no diretório local, envia ao Telegram e apaga."""
    if not os.path.isdir(BACKUP_DIR):
        log.info("Diretório de backups %s não encontrado.", BACKUP_DIR)
        return

    arquivos = [f for f in os.listdir(BACKUP_DIR) if f.endswith((".txt", ".dat"))]
    if not arquivos:
        log.info("Nenhum arquivo de backup local para enviar ao Telegram.")
        return

    enviados = 0
    for arq in arquivos:
        caminho = os.path.join(BACKUP_DIR, arq)
        if telegram_send_file(caminho):
            enviados += 1
            try:
                os.remove(caminho)
                log.info("Arquivo %s removido após envio.", arq)
            except Exception as exc:
                log.error("Erro ao remover %s: %s", arq, exc)

    if enviados:
        telegram_send_message(
            f"✅ {enviados} arquivo(s) de backup local enviado(s) com sucesso."
        )


# ============================================================
# Função principal
# ============================================================

def run_backups():
    """Executa o backup de todas as OLTs, notificando o Telegram após cada uma."""
    olts = get_olts()
    total = len(olts)

    ts_inicio = datetime.now().strftime("%d/%m/%Y %H:%M")
    log.info("=" * 60)
    log.info("Iniciando backups de %d OLTs...", total)
    log.info("=" * 60)

    telegram_send_message(
        f"🔄 Iniciando backup de {total} OLTs — {ts_inicio}"
    )

    resultados_ok = []
    resultados_erro = []

    for idx, (olt_name, olt_info) in enumerate(olts.items(), start=1):
        progresso = f"[{idx}/{total}]"

        if not olt_info.get("ip"):
            log.warning("OLT %s sem IP configurado. Pulando.", olt_name)
            resultados_erro.append(olt_name)
            telegram_send_message(
                f"⚠️ {progresso} {olt_name} — sem IP configurado, pulando."
            )
            continue

        olt_type = olt_info.get("type", "")
        backup_file = None

        if olt_type == "datacom":
            backup_file = backup_olt_datacom(olt_name, olt_info)
        elif olt_type == "zte":
            backup_file = backup_zte_olt(olt_name, olt_info)
        elif olt_type == "zte_titan":
            backup_file = backup_zte_titan(olt_name, olt_info)
        else:
            log.warning("Tipo desconhecido para OLT %s: %s", olt_name, olt_type)
            resultados_erro.append(olt_name)
            telegram_send_message(
                f"⚠️ {progresso} {olt_name} — tipo desconhecido '{olt_type}'."
            )
            continue

        # ---- Notifica o Telegram imediatamente após cada OLT ----
        if backup_file:
            resultados_ok.append(olt_name)
            telegram_send_message(
                f"✅ {progresso} {olt_name} — backup concluído ({backup_file})"
            )
        else:
            resultados_erro.append(olt_name)
            telegram_send_message(
                f"❌ {progresso} {olt_name} — falha no backup"
            )

    # Enviar backups locais (se houver) para Telegram
    enviar_backups_telegram()

    # Resumo final via Telegram
    ts_fim = datetime.now().strftime("%d/%m/%Y %H:%M")
    resumo = (
        f"📋 Resumo do backup OLT — {ts_fim}\n\n"
        f"✅ Sucesso ({len(resultados_ok)}): "
        f"{', '.join(resultados_ok) if resultados_ok else 'nenhum'}\n"
        f"❌ Falha ({len(resultados_erro)}): "
        f"{', '.join(resultados_erro) if resultados_erro else 'nenhum'}"
    )
    telegram_send_message(resumo)

    log.info("Processo de backup finalizado.")


if __name__ == "__main__":
    run_backups()
