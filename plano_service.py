from banco import obter_uso_usuario

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


def get_plano_usuario():
    # depois vamos buscar do banco
    return PLANO_FREE


def pode_fazer_analise(usuario_id):
    plano = get_plano_usuario()
    uso = obter_uso_usuario(usuario_id)
    limite = LIMITES[plano]["analises"]

    return uso < limite


def get_limite_analises(plano):
    return LIMITES[plano]["analises"]


def pode_gerar_pdf(plano):
    return LIMITES[plano]["pdf"]