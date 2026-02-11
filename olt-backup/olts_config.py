"""
Configuração das OLTs carregada a partir de variáveis de ambiente.
Cada OLT é definida com IP, usuário, senha, tipo de conexão e porta.
"""

import os


def get_olts():
    """Retorna o dicionário de OLTs com credenciais lidas do ambiente."""

    olts = {
        # ===================== OLTs Datacom =====================
        "OURICANGAS": {
            "ip": os.getenv("OLT_OURICANGAS_IP", ""),
            "user": os.getenv("OLT_OURICANGAS_USER", ""),
            "password": os.getenv("OLT_OURICANGAS_PASS", ""),
            "type": "datacom",
            "port": int(os.getenv("OLT_OURICANGAS_PORT", "23")),
        },
        "OURICANGUINHA": {
            "ip": os.getenv("OLT_OURICANGUINHA_IP", ""),
            "user": os.getenv("OLT_OURICANGUINHA_USER", ""),
            "password": os.getenv("OLT_OURICANGUINHA_PASS", ""),
            "type": "datacom",
            "port": int(os.getenv("OLT_OURICANGUINHA_PORT", "23")),
        },
        "POP_FORMIGA": {
            "ip": os.getenv("OLT_POP_FORMIGA_IP", ""),
            "user": os.getenv("OLT_POP_FORMIGA_USER", ""),
            "password": os.getenv("OLT_POP_FORMIGA_PASS", ""),
            "type": "datacom",
            "port": int(os.getenv("OLT_POP_FORMIGA_PORT", "23")),
        },
        "POP_SAO_FELIX": {
            "ip": os.getenv("OLT_POP_SAO_FELIX_IP", ""),
            "user": os.getenv("OLT_POP_SAO_FELIX_USER", ""),
            "password": os.getenv("OLT_POP_SAO_FELIX_PASS", ""),
            "type": "datacom",
            "port": int(os.getenv("OLT_POP_SAO_FELIX_PORT", "23")),
        },
        "POP_PEDRAO_GPON": {
            "ip": os.getenv("OLT_POP_PEDRAO_GPON_IP", ""),
            "user": os.getenv("OLT_POP_PEDRAO_GPON_USER", ""),
            "password": os.getenv("OLT_POP_PEDRAO_GPON_PASS", ""),
            "type": "datacom",
            "port": int(os.getenv("OLT_POP_PEDRAO_GPON_PORT", "23")),
        },
        "OLT_CATU_DATACOM": {
            "ip": os.getenv("OLT_OLT_CATU_DATACOM_IP", ""),
            "user": os.getenv("OLT_OLT_CATU_DATACOM_USER", ""),
            "password": os.getenv("OLT_OLT_CATU_DATACOM_PASS", ""),
            "type": "datacom",
            "port": int(os.getenv("OLT_OLT_CATU_DATACOM_PORT", "23")),
        },
        "POP_BARREIRO_02_38": {
            "ip": os.getenv("OLT_POP_BARREIRO_02_38_IP", ""),
            "user": os.getenv("OLT_POP_BARREIRO_02_38_USER", ""),
            "password": os.getenv("OLT_POP_BARREIRO_02_38_PASS", ""),
            "type": "datacom",
            "port": int(os.getenv("OLT_POP_BARREIRO_02_38_PORT", "23")),
        },
        "POP_BARREIRO_34": {
            "ip": os.getenv("OLT_POP_BARREIRO_34_IP", ""),
            "user": os.getenv("OLT_POP_BARREIRO_34_USER", ""),
            "password": os.getenv("OLT_POP_BARREIRO_34_PASS", ""),
            "type": "datacom",
            "port": int(os.getenv("OLT_POP_BARREIRO_34_PORT", "23")),
        },
        "CATU_04": {
            "ip": os.getenv("OLT_CATU_04_IP", ""),
            "user": os.getenv("OLT_CATU_04_USER", ""),
            "password": os.getenv("OLT_CATU_04_PASS", ""),
            "type": "datacom",
            "port": int(os.getenv("OLT_CATU_04_PORT", "23")),
        },
        "CATU_03": {
            "ip": os.getenv("OLT_CATU_03_IP", ""),
            "user": os.getenv("OLT_CATU_03_USER", ""),
            "password": os.getenv("OLT_CATU_03_PASS", ""),
            "type": "datacom",
            "port": int(os.getenv("OLT_CATU_03_PORT", "23")),
        },
        "PEDRO_BRAGA_NOVA": {
            "ip": os.getenv("OLT_PEDRO_BRAGA_NOVA_IP", ""),
            "user": os.getenv("OLT_PEDRO_BRAGA_NOVA_USER", ""),
            "password": os.getenv("OLT_PEDRO_BRAGA_NOVA_PASS", ""),
            "type": "datacom",
            "port": int(os.getenv("OLT_PEDRO_BRAGA_NOVA_PORT", "23")),
        },

        # ===================== OLTs ZTE =====================
        "ZTE_ARAMARI": {
            "ip": os.getenv("OLT_ZTE_ARAMARI_IP", ""),
            "user": os.getenv("OLT_ZTE_ARAMARI_USER", ""),
            "password": os.getenv("OLT_ZTE_ARAMARI_PASS", ""),
            "type": "zte",
            "port": int(os.getenv("OLT_ZTE_ARAMARI_PORT", "23")),
        },
        "ZTE_CAMBUBE": {
            "ip": os.getenv("OLT_ZTE_CAMBUBE_IP", ""),
            "user": os.getenv("OLT_ZTE_CAMBUBE_USER", ""),
            "password": os.getenv("OLT_ZTE_CAMBUBE_PASS", ""),
            "type": "zte",
            "port": int(os.getenv("OLT_ZTE_CAMBUBE_PORT", "23")),
        },

        # ===================== OLT ZTE Titan =====================
        "ZTE_TITAN_CANAVIEIRAS": {
            "ip": os.getenv("OLT_ZTE_TITAN_CANAVIEIRAS_IP", ""),
            "user": os.getenv("OLT_ZTE_TITAN_CANAVIEIRAS_USER", ""),
            "password": os.getenv("OLT_ZTE_TITAN_CANAVIEIRAS_PASS", ""),
            "type": "zte_titan",
            "port": int(os.getenv("OLT_ZTE_TITAN_CANAVIEIRAS_PORT", "23")),
        },
    }

    return olts
