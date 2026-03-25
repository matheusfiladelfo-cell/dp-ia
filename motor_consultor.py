from motor_rescisao_profissional import analisar_rescisao_profissional
from motor_afastamento import (
    classificar_beneficio,
    calcular_responsabilidade_pagamento,
    verificar_estabilidade_acidentaria,
    verificar_demissao_durante_afastamento,
    verificar_prazo_cat
)


def analisar_caso(tipo_caso, dados):

    # =====================================================
    # RESCISÃO
    # =====================================================

    if tipo_caso == "rescisao":

        dados_basicos = {
            "tipo_rescisao": dados.get("tipo_rescisao") or "demissao_sem_justa_causa",
            "gestante": dados.get("gestante", False),
            "cipa": dados.get("cipa", False),
            "dirigente_sindical": dados.get("dirigente_sindical", False),
            "estabilidade_cct": False,
            "advertencias": 0,
            "suspensoes": 0,
            "prova_documental": False,
            "falta_grave": False,
            "beneficio_b91": dados.get("acidente_trabalho", False),
            "afastamento_recente": dados.get("retorno_inss", False),
            "cid_sensivel": False,
            "aviso_previo_aplicado": True,
            "documentacao_ok": True,
            "prazo_pagamento_irregular": False
        }

        analise = analisar_rescisao_profissional(dados_basicos)

        return {
            "tipo": "Rescisão",
            "risco": analise["risco_final"],
            "pontuacao": analise["pontuacao_total"],
            "alertas": analise["alertas"],
            "tipo_rescisao": dados_basicos["tipo_rescisao"],
            "tempo_empresa_meses": dados.get("tempo_empresa_meses")
        }

    # =====================================================
    # AFASTAMENTO
    # =====================================================

    elif tipo_caso in ["afastamento", "acidente_trabalho", "atestado"]:

        dias = dados.get("dias_afastamento") or 15

        pagamento = calcular_responsabilidade_pagamento(dias)

        tipo_beneficio = classificar_beneficio("a_servico")

        alertas = []

        # Estabilidade acidentária
        alerta_estabilidade = verificar_estabilidade_acidentaria(
            tipo_beneficio,
            None,
            None
        )

        if alerta_estabilidade:
            alertas.append(alerta_estabilidade)

        # Demissão durante afastamento
        alerta_demissao = verificar_demissao_durante_afastamento(
            dias,
            None
        )

        if alerta_demissao:
            alertas.append(alerta_demissao)

        # CAT
        alerta_cat = verificar_prazo_cat(
            None,
            None,
            "a_servico"
        )

        if alerta_cat:
            alertas.append(alerta_cat)

        # Classificação de risco
        risco = "BAIXO"

        for alerta in alertas:
            if alerta["nivel"] == "ALTO":
                risco = "ALTO"
                break
            elif alerta["nivel"] == "MÉDIO":
                risco = "MÉDIO"

        pontuacao = {
            "ALTO": 85,
            "MÉDIO": 50,
            "BAIXO": 10
        }[risco]

        return {
            "tipo": "Afastamento",
            "dias_afastamento": dias,
            "empresa_paga": pagamento["empresa_paga"],
            "inss_paga": pagamento["inss_paga"],
            "beneficio": tipo_beneficio,
            "risco": risco,
            "pontuacao": pontuacao,
            "alertas": alertas
        }

    # =====================================================
    # OUTROS
    # =====================================================

    return {
        "tipo": "Dúvida trabalhista",
        "risco": "BAIXO",
        "pontuacao": 0,
        "alertas": []
    }