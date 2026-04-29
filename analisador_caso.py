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

    # 🔥 NORMALIZAÇÃO DE ACENTOS (CORREÇÃO)
    texto_lower = (
        texto_lower
        .replace("á", "a")
        .replace("ã", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )

    # 🔥 PEDIDO DE DEMISSÃO (PRIORIDADE MÁXIMA)
    if any(p in texto_lower for p in [
        "pediu demissao",
        "pedido de demissao",
        "pediu a conta",
        "pedido demissao",
        "quis sair",
        "decidiu sair",
        "saiu da empresa"
    ]):
        return "pedido_demissao"

    # RESCISÃO (evita rotear só por "dispensa" genérica → litígio sem fatos de dispensa ia parar na matriz errada)
    if any(p in texto_lower for p in [
        "demitir",
        "demissao",
        "dispensou",
        "dispensado",
        "dispensada",
        "foi demitido",
        "empresa demitiu",
    ]):
        return "rescisao"

    # AFASTAMENTO
    if any(p in texto_lower for p in [
        "afastado",
        "atestado",
        "inss",
        "licenca"
    ]):
        return "afastamento"

    return None


# 🔒 FALLBACK (SEGURANÇA TOTAL)
def classificar_risco_juridico(texto):

    texto_lower = texto.lower()

    # Relatos especulativos ("talvez assédio") não devem herdar peso de assédio confirmado.
    _hedge_assedio = (
        "talvez",
        "sera que",
        "será que",
        "so estresse",
        "só estresse",
        "so stress",
        "só stress",
        "nao sei",
        "não sei",
    )
    _fortes_assedio = [
        "ofensa",
        "humilha",
        "xing",
        "gritou",
        "constrangimento",
        "exposição",
        "exposicao",
        "dano moral",
        "ridicularizado",
        "vergonha",
    ]
    _tem_hedge = any(h in texto_lower for h in _hedge_assedio)
    _forte_sem_só_bare = any(p in texto_lower for p in _fortes_assedio)
    _bare_assedio = "assedio" in texto_lower or "assédio" in texto_lower
    _indicio_assedio = _forte_sem_só_bare or (_bare_assedio and not _tem_hedge)

    if _indicio_assedio:
        return {
            "tipo_risco": "assedio_moral",
            "gravidade": "alta",
        }

    # Nexo ocupacional incerto: não rotear como acidente de trabalho só por queda/lesão genérica.
    _nexo_acidente_incerto = any(
        p in texto_lower
        for p in (
            "trabalho ou casa",
            "nao fala se",
            "não fala se",
            "duvidoso",
            "duvida se",
            "duvida se foi",
            "sem nexo",
            "nexo duvidoso",
            "nao sei se foi",
            "não sei se foi",
            "pode ter sido em casa",
        )
    )
    _sinais_acidente = any(
        p in texto_lower for p in ("acidente", "queda", "machucou", "lesão", "lesao")
    )

    if _sinais_acidente and not _nexo_acidente_incerto:
        return {
            "tipo_risco": "acidente_trabalho",
            "gravidade": "alta",
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

    # Narrativa completa para o motor (evita _normalizar_texto sem o relato do usuário).
    resultado["descricao_caso"] = texto

    return resultado