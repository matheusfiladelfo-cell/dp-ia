import re


# =====================================================
# NORMALIZAR TEXTO
# =====================================================

def normalizar_texto(texto):
    texto = texto.lower()
    texto = texto.replace(",", ".")
    return texto


# =====================================================
# EXTRAIR DIAS DE AFASTAMENTO
# =====================================================

def extrair_dias_afastamento(texto):

    texto = normalizar_texto(texto)

    padrao_dias = r"(\d+)\s*dias?"
    match = re.search(padrao_dias, texto)
    if match:
        return int(match.group(1))

    padrao_semanas = r"(\d+)\s*semanas?"
    match = re.search(padrao_semanas, texto)
    if match:
        return int(match.group(1)) * 7

    padrao_meses = r"(\d+)\s*meses?"
    match = re.search(padrao_meses, texto)
    if match:
        return int(match.group(1)) * 30

    return None


# =====================================================
# IDENTIFICAR TIPO DE RESCISÃO
# =====================================================

def identificar_tipo_rescisao(texto):

    texto = normalizar_texto(texto)

    if "sem justa causa" in texto:
        return "demissao_sem_justa_causa"

    if "justa causa" in texto:
        return "justa_causa"

    if "pedido de demissão" in texto or "pediu demissão" in texto:
        return "pedido_demissao"

    return None


# =====================================================
# IDENTIFICAR EXPERIÊNCIA
# =====================================================

def identificar_experiencia(texto):

    texto = normalizar_texto(texto)

    return "experiencia" in texto or "experiência" in texto


# =====================================================
# 🔥 EXTRAIR TEMPO DE EMPRESA (CORRIGIDO)
# =====================================================

def extrair_tempo_empresa(texto):

    texto = normalizar_texto(texto)

    # 🔥 1. FORMATO COMPLETO (PRIORIDADE MÁXIMA)
    match_completo = re.search(r"(\d+)\s*ano[s]?\s*e\s*(\d+)\s*meses?", texto)
    if match_completo:
        anos = int(match_completo.group(1))
        meses = int(match_completo.group(2))
        return (anos * 12) + meses

    # 2. 1 ano e meio
    match_meio = re.search(r"(\d+)\s*ano[s]?\s*e\s*meio", texto)
    if match_meio:
        anos = int(match_meio.group(1))
        return (anos * 12) + 6

    # 3. decimal (1.5 ano)
    match_decimal = re.search(r"(\d+(\.\d+)?)\s*anos?", texto)
    if match_decimal:
        valor = float(match_decimal.group(1))
        return int(valor * 12)

    # 4. só anos
    match_anos = re.search(r"(\d+)\s*anos?", texto)
    if match_anos:
        return int(match_anos.group(1)) * 12

    # 5. só meses
    match_meses = re.search(r"(\d+)\s*meses?", texto)
    if match_meses:
        return int(match_meses.group(1))

    # 6. aproximações
    if "quase 2 anos" in texto:
        return 22

    if "cerca de 1 ano" in texto or "aproximadamente 1 ano" in texto:
        return 12

    if "mais de 1 ano" in texto:
        return 13

    return None


# =====================================================
# DETECTAR ESTABILIDADES
# =====================================================

def detectar_estabilidades(texto):

    texto = normalizar_texto(texto)

    estabilidade = {
        "gestante": False,
        "acidente_trabalho": False,
        "cipa": False,
        "dirigente_sindical": False,
        "retorno_inss": False
    }

    if any(p in texto for p in ["gestante", "gravida", "grávida"]):
        estabilidade["gestante"] = True

    if "acidente de trabalho" in texto:
        estabilidade["acidente_trabalho"] = True

    if "cipa" in texto or "cipeiro" in texto:
        estabilidade["cipa"] = True

    if "dirigente sindical" in texto or "sindicato" in texto:
        estabilidade["dirigente_sindical"] = True

    if "retorno do inss" in texto or "voltou do inss" in texto:
        estabilidade["retorno_inss"] = True

    return estabilidade