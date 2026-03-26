import json


def validar_parecer(resposta_texto):

    try:
        # limpa markdown se vier
        if "```" in resposta_texto:
            partes = resposta_texto.split("```")
            resposta_texto = partes[1] if len(partes) > 1 else partes[0]

        data = json.loads(resposta_texto)

    except:
        return gerar_fallback()

    # =========================
    # 🔥 PADRONIZAÇÃO DE RISCO
    # =========================
    risco_raw = str(data.get("risco", "")).upper()

    if "ALTO" in risco_raw:
        data["risco"] = "ALTO"
    elif "MEDIO" in risco_raw or "MÉDIO" in risco_raw:
        data["risco"] = "MÉDIO"
    else:
        data["risco"] = "BAIXO"

    # =========================
    # CAMPOS OBRIGATÓRIOS
    # =========================
    campos = [
        "risco",
        "diagnostico",
        "fundamentacao",
        "impactos",
        "impacto_financeiro",
        "recomendacao"
    ]

    fallback = gerar_fallback()

    for campo in campos:
        if campo not in data or data[campo] in [None, "", []]:
            data[campo] = fallback[campo]

    # =========================
    # TRATAMENTO DE IMPACTO
    # =========================
    try:
        data["impacto_financeiro"] = float(data.get("impacto_financeiro", 0))
    except:
        data["impacto_financeiro"] = 0

    return data


def gerar_fallback():
    return {
        "risco": "MÉDIO",
        "diagnostico": "Foram identificados indícios de risco trabalhista no cenário analisado.",
        "fundamentacao": "A legislação trabalhista (CLT) e o entendimento da Justiça do Trabalho tendem a proteger o empregado em situações de irregularidade.",
        "impactos": "Podem existir reflexos em FGTS, férias, 13º salário, DSR e demais verbas.",
        "impacto_financeiro": 0,
        "recomendacao": "Revisar o caso com atenção e adotar medidas preventivas para reduzir o risco."
    }