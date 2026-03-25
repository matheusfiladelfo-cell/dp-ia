from ia_pipeline import analisar_texto_ia
from extrator_dados import (
    extrair_dias_afastamento,
    identificar_tipo_rescisao,
    identificar_experiencia,
    extrair_tempo_empresa,
    detectar_estabilidades
)
from perguntas_consultor import gerar_perguntas


def classificar_por_regra(texto):

    texto_lower = texto.lower()

    if any(p in texto_lower for p in ["demitir", "demissao", "dispensa"]):
        return "rescisao"

    if any(p in texto_lower for p in ["afastado", "atestado", "inss"]):
        return "afastamento"

    return None


def analisar_texto_usuario(texto):

    resultado = {}

    # =========================
    # 1. REGRAS (PRIORIDADE)
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

    # =========================
    # 3. 🔥 MERGE INTELIGENTE
    # =========================

    if isinstance(dados_ia, dict) and not dados_ia.get("erro"):

        for chave, valor in dados_ia.items():

            if valor in [None, ""]:
                continue

            # 🔥 REGRA SEMPRE GANHA
            if resultado.get(chave) not in [None]:
                continue

            resultado[chave] = valor

    else:
        resultado["erro_ia"] = dados_ia

    # =========================
    # 4. CONSISTÊNCIA
    # =========================

    if resultado.get("tipo_rescisao") == "demissao_sem_justa_causa":
        resultado["justa_causa"] = False

    if resultado.get("tipo_rescisao") == "justa_causa":
        resultado["justa_causa"] = True

    # =========================
    # 5. PERGUNTAS
    # =========================

    resultado["perguntas"] = gerar_perguntas(resultado)

    return resultado