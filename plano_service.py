from banco import (
    obter_uso_usuario,
    obter_plano_usuario_db,
    garantir_plano_usuario,
)

PLANO_FREE = "FREE"
PLANO_PRO = "PRO"
PLANO_PREMIUM = "PREMIUM"

LIMITES = {
    PLANO_FREE: {
        "analises": 10,
        "empresas": 1,
        "pdf": False
    },
    PLANO_PRO: {
        "analises": 200,
        "empresas": 5,
        "pdf": True
    },
    PLANO_PREMIUM: {
        "analises": float("inf"),
        "empresas": float("inf"),
        "pdf": True
    }
}


# 🔥 CORRIGIDO
def get_plano_usuario(usuario_id):
    plano = obter_plano_usuario_db(usuario_id)
    if plano in LIMITES:
        return plano
    garantir_plano_usuario(usuario_id, plano_default=PLANO_FREE)
    return PLANO_FREE


# 🔥 CORRIGIDO
def pode_fazer_analise(usuario_id):
    plano = get_plano_usuario(usuario_id)
    uso = obter_uso_usuario(usuario_id)
    limite = LIMITES[plano]["analises"]

    return uso < limite


def get_limite_analises(plano):
    return LIMITES[plano]["analises"]


def pode_gerar_pdf(plano):
    return LIMITES[plano]["pdf"]


def get_limite_empresas(plano):
    return LIMITES[plano]["empresas"]


def pode_cadastrar_empresa(usuario_id, total_empresas_atual):
    plano = get_plano_usuario(usuario_id)
    limite_empresas = get_limite_empresas(plano)
    return total_empresas_atual < limite_empresas