from motor_rescisao_profissional import analisar_rescisao_profissional
from motor_afastamento import (
    classificar_beneficio,
    calcular_responsabilidade_pagamento,
    verificar_estabilidade_acidentaria,
    verificar_demissao_durante_afastamento,
    verificar_prazo_cat
)


def detectar_riscos_criticos(dados):
    """
    Mantido como fallback de segurança
    """

    texto = str(dados).lower()

    indicadores_alto = [
        "ofensa", "humilha", "xing", "assédio", "assedio",
        "gritou", "exposição", "exposicao", "constrangimento",
        "agressão", "agressao", "dano moral"
    ]

    indicadores_medio = [
        "discussão", "discussao", "conflito",
        "advertência", "advertencia",
        "clima ruim", "problema com gestor"
    ]

    for termo in indicadores_alto:
        if termo in texto:
            return "ALTO", 70

    for termo in indicadores_medio:
        if termo in texto:
            return "MÉDIO", 40

    return "BAIXO", 10


def analisar_caso(tipo_caso, dados):

    texto = str(dados).lower()
    tipo_risco = str(dados.get("tipo_risco", "")).lower()

    # =====================================================
    # 🔥 PRIORIDADE ABSOLUTA — ASSÉDIO (BLINDAGEM TOTAL)
    # =====================================================

    if (
        tipo_risco == "assedio_moral"
        or any(p in texto for p in [
            "ofensa", "humilha", "xing", "assedio", "assédio",
            "constrangimento", "gritou", "exposição", "exposicao"
        ])
    ):
        return {
            "tipo": "Assédio moral",
            "risco": "ALTO",
            "pontuacao": 90,
            "alertas": [{
                "tipo": "ASSÉDIO",
                "nivel": "ALTO",
                "mensagem": "Conduta pode caracterizar assédio moral com alta probabilidade de condenação"
            }]
        }

    # =====================================================
    # 🔥 ACIDENTE
    # =====================================================

    if (
        tipo_risco == "acidente_trabalho"
        or any(p in texto for p in [
            "acidente", "queda", "machucou", "lesão", "lesao"
        ])
    ):
        return {
            "tipo": "Acidente de trabalho",
            "risco": "ALTO",
            "pontuacao": 90,
            "alertas": [{
                "tipo": "ACIDENTE",
                "nivel": "ALTO",
                "mensagem": "Possível responsabilidade da empresa em acidente de trabalho"
            }]
        }

    # =====================================================
    # 🔶 CONFLITO
    # =====================================================

    if tipo_risco == "conflito_interpessoal":
        return {
            "tipo": "Conflito interpessoal",
            "risco": "MÉDIO",
            "pontuacao": 45,
            "alertas": [{
                "tipo": "CONFLITO",
                "nivel": "MÉDIO",
                "mensagem": "Situação pode evoluir para risco trabalhista"
            }]
        }

    # =====================================================
    # RESCISÃO (MANTIDO)
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
    # AFASTAMENTO (MANTIDO)
    # =====================================================

    elif tipo_caso in ["afastamento", "acidente_trabalho", "atestado"]:

        dias = dados.get("dias_afastamento") or 15

        pagamento = calcular_responsabilidade_pagamento(dias)
        tipo_beneficio = classificar_beneficio("a_servico")

        alertas = []

        alerta_estabilidade = verificar_estabilidade_acidentaria(
            tipo_beneficio, None, None
        )
        if alerta_estabilidade:
            alertas.append(alerta_estabilidade)

        alerta_demissao = verificar_demissao_durante_afastamento(
            dias, None
        )
        if alerta_demissao:
            alertas.append(alerta_demissao)

        alerta_cat = verificar_prazo_cat(
            None, None, "a_servico"
        )
        if alerta_cat:
            alertas.append(alerta_cat)

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
    # OUTROS (COM SEGURANÇA REAL)
    # =====================================================

    risco_detectado, pontuacao = detectar_riscos_criticos(dados)

    return {
        "tipo": "Dúvida trabalhista",
        "risco": risco_detectado,
        "pontuacao": pontuacao,
        "alertas": [
            {
                "tipo": "ANÁLISE CONTEXTUAL",
                "nivel": risco_detectado,
                "mensagem": "Classificação baseada em análise do contexto do relato"
            }
        ]
    }