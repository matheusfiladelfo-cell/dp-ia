from datetime import timedelta


# =====================================================
# MATRIZ DE RISCO PONDERADA – RESCISÃO PROFISSIONAL
# =====================================================

# =====================================================
# BLOCO 1 – ESTABILIDADES
# =====================================================

def verificar_estabilidades(dados):

    alertas = []

    if dados.get("gestante"):
        alertas.append({
            "nivel": "ALTO",
            "peso": 100,
            "categoria": "Estabilidade",
            "motivo": "Estabilidade gestante ativa.",
            "base_legal": "Art. 10, II, b ADCT",
            "recomendacao": "Demissão pode ser considerada nula."
        })

    if dados.get("cipa"):
        alertas.append({
            "nivel": "ALTO",
            "peso": 95,
            "categoria": "Estabilidade",
            "motivo": "Estabilidade de membro da CIPA.",
            "base_legal": "Art. 10 ADCT",
            "recomendacao": "Vedada dispensa arbitrária."
        })

    if dados.get("dirigente_sindical"):
        alertas.append({
            "nivel": "ALTO",
            "peso": 95,
            "categoria": "Estabilidade",
            "motivo": "Estabilidade de dirigente sindical.",
            "base_legal": "Art. 543 CLT",
            "recomendacao": "Dispensa exige inquérito judicial."
        })

    if dados.get("estabilidade_cct"):
        alertas.append({
            "nivel": "MÉDIO",
            "peso": 70,
            "categoria": "Estabilidade Convencional",
            "motivo": "Possível estabilidade prevista em CCT.",
            "base_legal": "Norma coletiva aplicável",
            "recomendacao": "Verificar cláusula específica."
        })

    return alertas


# =====================================================
# BLOCO 2 – JUSTA CAUSA
# =====================================================

def verificar_justa_causa(dados):

    if dados.get("tipo_rescisao") != "Justa Causa":
        return []

    alertas = []

    advertencias = dados.get("advertencias")
    suspensoes = dados.get("suspensoes")
    prova_documental = dados.get("prova_documental")
    falta_grave = dados.get("falta_grave")

    if not falta_grave:
        alertas.append({
            "nivel": "ALTO",
            "peso": 90,
            "categoria": "Justa Causa",
            "motivo": "Falta grave não claramente caracterizada.",
            "base_legal": "Art. 482 CLT",
            "recomendacao": "Alto risco de reversão judicial."
        })

    if not prova_documental:
        alertas.append({
            "nivel": "ALTO",
            "peso": 85,
            "categoria": "Justa Causa",
            "motivo": "Ausência de prova documental.",
            "base_legal": "Ônus da prova do empregador",
            "recomendacao": "Justa causa pode ser revertida."
        })

    if advertencias == 0 and suspensoes == 0:
        alertas.append({
            "nivel": "MÉDIO",
            "peso": 60,
            "categoria": "Justa Causa",
            "motivo": "Ausência de histórico disciplinar progressivo.",
            "base_legal": "Princípio da proporcionalidade",
            "recomendacao": "Avaliar gradação da penalidade."
        })

    return alertas


# =====================================================
# BLOCO 3 – AFASTAMENTOS
# =====================================================

def verificar_afastamento_recente(dados):

    alertas = []

    if dados.get("beneficio_b91"):
        alertas.append({
            "nivel": "ALTO",
            "peso": 85,
            "categoria": "Afastamento",
            "motivo": "Histórico de benefício acidentário (B91).",
            "base_legal": "Art. 118 Lei 8.213/91",
            "recomendacao": "Verificar estabilidade de 12 meses."
        })

    if dados.get("afastamento_recente"):
        alertas.append({
            "nivel": "MÉDIO",
            "peso": 50,
            "categoria": "Afastamento",
            "motivo": "Afastamento recente pode indicar vulnerabilidade jurídica.",
            "base_legal": "Princípio da proteção",
            "recomendacao": "Avaliar risco de alegação discriminatória."
        })

    if dados.get("cid_sensivel"):
        alertas.append({
            "nivel": "MÉDIO",
            "peso": 65,
            "categoria": "Afastamento",
            "motivo": "CID compatível com possível doença ocupacional.",
            "base_legal": "Art. 20 Lei 8.213/91",
            "recomendacao": "Avaliar nexo técnico."
        })

    return alertas


# =====================================================
# BLOCO 4 – PROCEDIMENTO
# =====================================================

def verificar_procedimento(dados):

    alertas = []

    if not dados.get("aviso_previo_aplicado"):
        alertas.append({
            "nivel": "MÉDIO",
            "peso": 45,
            "categoria": "Procedimento",
            "motivo": "Aviso prévio irregular.",
            "base_legal": "Lei 12.506/2011",
            "recomendacao": "Revisar aplicação do aviso."
        })

    if not dados.get("documentacao_ok"):
        alertas.append({
            "nivel": "MÉDIO",
            "peso": 35,
            "categoria": "Procedimento",
            "motivo": "Documentação rescisória incompleta.",
            "base_legal": "Art. 477 CLT",
            "recomendacao": "Revisar checklist."
        })

    if dados.get("prazo_pagamento_irregular"):
        alertas.append({
            "nivel": "MÉDIO",
            "peso": 40,
            "categoria": "Procedimento",
            "motivo": "Pagamento fora do prazo legal.",
            "base_legal": "Art. 477 §6º CLT",
            "recomendacao": "Pode gerar multa."
        })

    return alertas


# =====================================================
# CONSOLIDADOR PONDERADO
# =====================================================

def consolidar_risco(alertas):

    pontuacao_bruta = sum(alerta["peso"] for alerta in alertas)

    # 🔥 NORMALIZAÇÃO (máximo 100)
    pontuacao_total = min(pontuacao_bruta, 100)

    if pontuacao_total >= 80:
        risco_final = "ALTO"
    elif pontuacao_total >= 40:
        risco_final = "MÉDIO"
    else:
        risco_final = "BAIXO"

    return risco_final, pontuacao_total


# =====================================================
# FUNÇÃO PRINCIPAL
# =====================================================

def analisar_rescisao_profissional(dados):

    alertas = []

    alertas.extend(verificar_estabilidades(dados))
    alertas.extend(verificar_justa_causa(dados))
    alertas.extend(verificar_afastamento_recente(dados))
    alertas.extend(verificar_procedimento(dados))

    risco_final, pontuacao_total = consolidar_risco(alertas)

    return {
        "risco_final": risco_final,
        "pontuacao_total": pontuacao_total,
        "alertas": alertas
    }