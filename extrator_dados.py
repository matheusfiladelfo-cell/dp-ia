import re


# =====================================================
# EXTRAIR DIAS DE AFASTAMENTO
# =====================================================

def extrair_dias_afastamento(texto):

    texto = texto.lower()

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

    texto = texto.lower()

    if "justa causa" in texto:
        return "justa_causa"

    if "pedido de demissão" in texto:
        return "pedido_demissao"

    if "pediu demissão" in texto:
        return "pedido_demissao"

    if "sem justa causa" in texto:
        return "demissao_sem_justa_causa"

    if "demitir" in texto or "demissão" in texto:
        return "demissao_sem_justa_causa"

    return None


# =====================================================
# IDENTIFICAR CONTRATO DE EXPERIÊNCIA
# =====================================================

def identificar_experiencia(texto):

    texto = texto.lower()

    if "experiência" in texto or "experiencia" in texto:
        return True

    return False


# =====================================================
# EXTRAIR TEMPO DE EMPRESA
# =====================================================

def extrair_tempo_empresa(texto):

    texto = texto.lower()

    padrao_anos = r"(\d+)\s*anos?"
    match = re.search(padrao_anos, texto)

    if match:
        return int(match.group(1)) * 12

    padrao_meses = r"(\d+)\s*meses?"
    match = re.search(padrao_meses, texto)

    if match:
        return int(match.group(1))

    return None


# =====================================================
# DETECTAR ESTABILIDADES
# =====================================================

def detectar_estabilidades(texto):

    texto = texto.lower()

    estabilidade = {
        "gestante": False,
        "acidente_trabalho": False,
        "cipa": False,
        "dirigente_sindical": False,
        "retorno_inss": False
    }

    if "gestante" in texto or "grávida" in texto or "gravida" in texto:
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