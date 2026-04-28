from banco import (
    atualizar_onboarding_etapa,
    concluir_onboarding_usuario,
    garantir_onboarding_usuario,
    obter_onboarding_usuario,
)


def obter_onboarding_status(usuario_id, total_empresas, uso_analises):
    garantir_onboarding_usuario(usuario_id)
    onboarding = obter_onboarding_usuario(usuario_id) or {
        "etapa_atual": 1,
        "concluido": False,
        "concluido_em": None,
    }

    if onboarding.get("concluido"):
        return {"ativo": False, "etapa_atual": 3, "concluido": True}

    etapa_calculada = 1
    if total_empresas > 0:
        etapa_calculada = 2
    if total_empresas > 0 and uso_analises > 0:
        etapa_calculada = 3

    if etapa_calculada != onboarding.get("etapa_atual", 1):
        atualizar_onboarding_etapa(usuario_id, etapa_calculada)

    return {
        "ativo": True,
        "etapa_atual": etapa_calculada,
        "concluido": False,
    }


def finalizar_onboarding(usuario_id):
    concluir_onboarding_usuario(usuario_id)
