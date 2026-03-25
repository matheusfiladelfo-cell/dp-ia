from datetime import timedelta


# ---------------- CLASSIFICAÇÃO BENEFÍCIO ----------------

def classificar_beneficio(tipo_evento):
    if tipo_evento in ["trajeto", "a_servico"]:
        return "B91"
    return "B31"


# ---------------- RESPONSABILIDADE PAGAMENTO ----------------

def calcular_responsabilidade_pagamento(dias_afastamento):

    if dias_afastamento <= 15:
        return {
            "empresa_paga": dias_afastamento,
            "inss_paga": 0
        }

    return {
        "empresa_paga": 15,
        "inss_paga": dias_afastamento - 15
    }


# ---------------- REGRA 60 DIAS ----------------

def verificar_regra_60_dias(cid_atual, cid_anterior, dias_entre_afastamentos):

    if cid_atual and cid_anterior:
        if cid_atual == cid_anterior and dias_entre_afastamentos <= 60:
            return {
                "empresa_paga_novamente_15": False,
                "alerta": "Mesmo CID dentro de 60 dias. INSS assume desde o primeiro dia.",
                "base_legal": "Art. 75 §5º Decreto 3.048/99"
            }

    return {
        "empresa_paga_novamente_15": True,
        "alerta": "Novo CID ou prazo superior a 60 dias. Empresa paga 15 dias novamente.",
        "base_legal": "Art. 60 Lei 8.213/91"
    }


# ---------------- ESTABILIDADE ACIDENTÁRIA ----------------

def verificar_estabilidade_acidentaria(tipo_beneficio, data_alta, data_demissao):

    if tipo_beneficio == "B91" and data_alta and data_demissao:

        fim_estabilidade = data_alta + timedelta(days=365)

        if data_demissao <= fim_estabilidade:
            return {
                "nivel": "ALTO",
                "motivo": "Estabilidade acidentária ativa (12 meses após alta).",
                "base_legal": "Art. 118 Lei 8.213/91",
                "recomendacao": "Demissão pode gerar reintegração ou indenização substitutiva."
            }

    return None


# ---------------- DEMISSÃO DURANTE AFASTAMENTO ----------------

def verificar_demissao_durante_afastamento(dias_afastamento, data_demissao):

    if dias_afastamento > 0 and not data_demissao:
        return None

    # Se a pessoa ainda está afastada
    if dias_afastamento > 0 and data_demissao:
        return {
            "nivel": "ALTO",
            "motivo": "Demissão durante período de afastamento.",
            "base_legal": "Entendimento jurisprudencial consolidado",
            "recomendacao": "Demissão pode ser considerada nula."
        }

    return None


# ---------------- RISCO DE DOENÇA OCUPACIONAL ----------------

def verificar_risco_doenca_ocupacional(cid_atual, tipo_evento):

    # Exemplo simples de CID de lesão por esforço
    cids_sensiveis = ["M54", "M51", "G56"]

    if cid_atual:
        for cid in cids_sensiveis:
            if cid in cid_atual and tipo_evento == "comum":
                return {
                    "nivel": "MÉDIO",
                    "motivo": "CID compatível com possível doença ocupacional.",
                    "base_legal": "Art. 20 Lei 8.213/91",
                    "recomendacao": "Avaliar nexo técnico epidemiológico."
                }

    return None


# ---------------- PRAZO CAT ----------------

def verificar_prazo_cat(data_acidente, data_emissao_cat, tipo_evento):

    if tipo_evento == "comum":
        return None

    if not data_emissao_cat:
        return {
            "nivel": "MÉDIO",
            "motivo": "Possível ausência de emissão de CAT.",
            "base_legal": "Art. 22 Lei 8.213/91",
            "recomendacao": "Verificar obrigação de comunicação."
        }

    prazo = data_acidente + timedelta(days=1)

    if data_emissao_cat > prazo:
        return {
            "nivel": "MÉDIO",
            "motivo": "CAT emitida fora do prazo legal.",
            "base_legal": "Art. 22 Lei 8.213/91",
            "recomendacao": "Pode gerar multa administrativa."
        }

    return None