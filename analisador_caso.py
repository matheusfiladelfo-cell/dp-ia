from ia_pipeline import analisar_texto_ia
from extrator_dados import (
    extrair_dias_afastamento,
    identificar_tipo_rescisao,
    identificar_experiencia,
    extrair_tempo_empresa,
    detectar_estabilidades
)
from perguntas_consultor import gerar_perguntas

# 🔥 IA CLASSIFICADOR
from classificador_juridico import classificar_risco_ia


def classificar_por_regra(texto):

    texto_lower = texto.lower()

    if any(p in texto_lower for p in ["demitir", "demissao", "dispensa"]):
        return "rescisao"

    if any(p in texto_lower for p in ["afastado", "atestado", "inss"]):
        return "afastamento"

    return None


# 🔒 FALLBACK (SEGURANÇA TOTAL)
def classificar_risco_juridico(texto):

    texto_lower = texto.lower()

    if any(p in texto_lower for p in [
        "ofensa", "humilha", "xing", "assédio", "assedio",
        "gritou", "constrangimento", "exposição", "exposicao",
        "dano moral", "ridicularizado", "vergonha"
    ]):
        return {
            "tipo_risco": "assedio_moral",
            "gravidade": "alta"
        }

    if any(p in texto_lower for p in [
        "acidente", "queda", "machucou", "lesão", "lesao"
    ]):
        return {
            "tipo_risco": "acidente_trabalho",
            "gravidade": "alta"
        }

    if any(p in texto_lower for p in [
        "discussão", "discussao", "conflito", "problema com gestor"
    ]):
        return {
            "tipo_risco": "conflito_interpessoal",
            "gravidade": "media"
        }

    return {
        "tipo_risco": "geral",
        "gravidade": "baixa"
    }


def analisar_texto_usuario(texto):

    resultado = {}

    # =========================
    # 1. REGRAS
    # =========================

    resultado["dias_afastamento"] = extrair_dias_afastamento(texto)
    resultado["tipo_rescisao"] = identificar_tipo_rescisao(texto)
    resultado["experiencia"] = identificar_experiencia(texto)
    resultado["tempo_empresa_meses"] = extrair_tempo_empresa(texto)

    estabilidade = detectar_estabilidades(texto)
    resultado.update(estabilidade)

    resultado["tipo_caso"] = classificar_por_regra(texto)

    # =========================
    # 2. IA (COMPLEMENTO)
    # =========================

    dados_ia = analisar_texto_ia(texto)

    if isinstance(dados_ia, dict) and not dados_ia.get("erro"):

        for chave, valor in dados_ia.items():

            if valor in [None, ""]:
                continue

            if resultado.get(chave) not in [None]:
                continue

            resultado[chave] = valor

    else:
        resultado["erro_ia"] = dados_ia

    # =========================
    # 3. CONSISTÊNCIA
    # =========================

    if resultado.get("tipo_rescisao") == "demissao_sem_justa_causa":
        resultado["justa_causa"] = False

    if resultado.get("tipo_rescisao") == "justa_causa":
        resultado["justa_causa"] = True

    # =========================
    # 🔥 4. CLASSIFICAÇÃO PROFISSIONAL (IA + FALLBACK)
    # =========================

    try:
        classificacao_ia = classificar_risco_ia(texto)

        if not isinstance(classificacao_ia, dict):
            classificacao_ia = {}

    except:
        classificacao_ia = {}

    tipo_risco = str(classificacao_ia.get("tipo_risco", "")).lower()
    gravidade = str(classificacao_ia.get("gravidade", "")).lower()

    # 🔒 fallback se IA falhar ou vier genérico
    if not tipo_risco or tipo_risco == "geral":

        fallback = classificar_risco_juridico(texto)

        tipo_risco = fallback["tipo_risco"]
        gravidade = fallback["gravidade"]

    # 🔒 proteção extra (nunca deixar vazio)
    if not tipo_risco:
        tipo_risco = "geral"

    if not gravidade:
        gravidade = "baixa"

    resultado["tipo_risco"] = tipo_risco
    resultado["gravidade"] = gravidade

    # =========================
    # 5. PERGUNTAS
    # =========================

    resultado["perguntas"] = gerar_perguntas(resultado)

    return resultado