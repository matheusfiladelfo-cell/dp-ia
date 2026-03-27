# score_engine.py

def normalizar_risco(risco):
    if isinstance(risco, (int, float)):
        return min(max(risco, 0), 1)

    risco = str(risco).lower()

    mapa = {
        "baixo": 0.3,
        "medio": 0.6,
        "médio": 0.6,
        "medio-alto": 0.75,
        "médio-alto": 0.75,
        "alto": 0.9
    }

    return mapa.get(risco, 0.5)


def normalizar_impacto(valor):
    if not valor:
        return 0

    if valor < 5000:
        return 0.2
    elif valor < 20000:
        return 0.5
    elif valor < 50000:
        return 0.7
    else:
        return 1.0


# 🔥 NOVO — TRAVA JURÍDICA
def aplicar_trava_risco(score, risco):

    risco = str(risco).upper()

    if risco == "ALTO":
        return max(score, 70)

    if risco in ["MÉDIO", "MEDIO"]:
        return max(score, 40)

    if risco in ["MÉDIO-ALTO", "MEDIO-ALTO"]:
        return max(score, 60)

    return max(score, 10)


def calcular_score(case_data):

    motivos = []

    risco = case_data.get("risco", "BAIXO")
    impacto_valor = case_data.get("impacto", 0)
    tipo = case_data.get("tipo", "geral")

    risco_base = normalizar_risco(risco)
    impacto = normalizar_impacto(impacto_valor)

    # =========================
    # BASE
    # =========================

    score = risco_base * 100

    motivos.append({
        "fator": "Risco base do caso",
        "impacto": int(score)
    })

    # =========================
    # PESO POR TIPO
    # =========================

    peso_tipo = {
        "rescisao": 1.2,
        "afastamento": 1.1,
        "hora_extra": 1.0,
        "assedio_moral": 1.3,
        "acidente_trabalho": 1.3,
        "geral": 1.0
    }

    fator_tipo = peso_tipo.get(tipo, 1.0)

    incremento_tipo = (fator_tipo - 1) * 30
    score += incremento_tipo

    if incremento_tipo > 0:
        motivos.append({
            "fator": f"Tipo de caso com maior risco ({tipo})",
            "impacto": int(incremento_tipo)
        })

    # =========================
    # IMPACTO FINANCEIRO
    # =========================

    impacto_score = impacto * 15
    score += impacto_score

    if impacto_score > 0:
        motivos.append({
            "fator": "Impacto financeiro relevante",
            "impacto": int(impacto_score)
        })

    # =========================
    # AJUSTES CONTEXTUAIS
    # =========================

    if case_data.get("reincidente"):
        score += 10
        motivos.append({
            "fator": "Reincidência do problema",
            "impacto": 10
        })

    if case_data.get("tem_prova"):
        score += 5
        motivos.append({
            "fator": "Existência de prova",
            "impacto": 5
        })

    if case_data.get("testemunha"):
        score += 5
        motivos.append({
            "fator": "Possível testemunha",
            "impacto": 5
        })

    # =========================
    # LIMITES
    # =========================

    score = max(0, min(int(score), 100))

    # =========================
    # 🔥 TRAVA FINAL (CRÍTICO)
    # =========================

    score = aplicar_trava_risco(score, risco)

    # =========================
    # CLASSIFICAÇÃO FINAL
    # =========================

    if score >= 80:
        prob = 75
        nivel = "ALTO"
    elif score >= 60:
        prob = 55
        nivel = "MÉDIO-ALTO"
    elif score >= 40:
        prob = 35
        nivel = "MÉDIO"
    else:
        prob = 20
        nivel = "BAIXO"

    return {
        "score": score,
        "probabilidade_condenacao": prob,
        "nivel": nivel,
        "motivos": motivos
    }