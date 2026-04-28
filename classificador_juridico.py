from ia_client import client
import json
import re
from core.juridico_contracts_v2 import (
    ClassificacaoJuridicaV2,
    EvidenciaJuridica,
    RiscoNivel,
    StatusEvidencia,
    TipoRisco,
)


TIPOS_MAPEADOS = {
    "assedio_moral": TipoRisco.ASSEDIO_MORAL,
    "acidente_trabalho": TipoRisco.ACIDENTE_TRABALHO,
    "conflito_interpessoal": TipoRisco.CONFLITO_INTERPESSOAL,
    "rescisao": TipoRisco.RESCISAO,
    "afastamento": TipoRisco.AFASTAMENTO,
    "hora_extra": TipoRisco.HORA_EXTRA,
    "geral": TipoRisco.GERAL,
    "inconclusivo": TipoRisco.INCONCLUSIVO,
}


def _normalizar_tipo_risco(valor):
    key = str(valor or "").strip().lower()
    return TIPOS_MAPEADOS.get(key, TipoRisco.INCONCLUSIVO)


def _normalizar_gravidade(valor):
    key = str(valor or "").strip().lower()
    if key in {"alto", "alta"}:
        return RiscoNivel.ALTO
    if key in {"medio", "médio", "media", "média"}:
        return RiscoNivel.MEDIO
    if key in {"baixo", "baixa"}:
        return RiscoNivel.BAIXO
    return RiscoNivel.INCONCLUSIVO


def _detectar_lacunas(texto):
    texto_lower = str(texto or "").lower()
    lacunas = []
    if len(texto_lower.split()) < 12:
        lacunas.append("relato_curto")
    if not any(p in texto_lower for p in ["quando", "data", "semana", "mes", "mês"]):
        lacunas.append("sem_referencia_temporal")
    if not any(p in texto_lower for p in ["gestor", "empresa", "lider", "líder", "colega"]):
        lacunas.append("sem_envolvidos_claros")
    return lacunas


def _extrair_tempo_meses(texto):
    texto_lower = str(texto or "").lower()
    match = re.search(r"(\d+)\s*(mes|meses)", texto_lower)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return 0
    return 0


def _detectar_hard_rule_juridica(texto):
    # Estado local por execução, sem retenção entre casos.
    texto_lower = str(texto or "").lower()
    termos_gestante = ["gestante", "grávida", "gravida", "gestação", "gestacao"]
    termos_desligamento = ["demissão", "demissao", "desligamento", "mandei embora", "dispensa", "dispensada", "dispensado", "dispensei"]
    termos_verbas_nao_pagas = [
        "não paguei rescisão",
        "nao paguei rescisao",
        "sem pagar nada",
        "sem acerto",
        "verbas não pagas",
        "verbas nao pagas",
        "verbas rescisórias não pagas",
        "verbas rescisorias nao pagas",
    ]
    termos_sem_prova = ["sem prova", "sem documento", "sem testemunha", "nao tenho prova", "não tenho prova"]
    termos_sem_registro = ["sem carteira", "sem registro", "trabalhou sem registrar"]
    termos_acidente = ["acidente", "acidente de trabalho", "machucou", "queda"]
    termos_sem_cat = ["não abriu cat", "nao abriu cat", "sem cat", "nao fiz cat", "não fiz cat"]
    termos_assedio = ["assédio", "assedio"]
    termos_provas_assedio = ["prints", "print", "áudio", "audio", "testemunha"]
    termos_horas_extras = ["hora extra todo dia", "horas extras", "jornada excessiva", "sem ponto"]
    termos_pedido_demissao = ["pedido de demissão", "pedido de demissao", "pediu a conta", "pediu demissao"]
    termos_quitacao = ["paguei tudo", "recibos", "documentos", "quitação total", "quitacao total"]
    termos_fgts_atraso = ["sem fgts", "fgts atrasado", "fgts em atraso", "fgts não recolhido", "fgts nao recolhido"]
    termos_pj_subordinado = ["contrato pj", "pj", "pessoa jurídica", "pessoa juridica"]
    termos_subordinacao = ["batia ponto", "subordinação", "subordinacao", "chefe direto", "ordens diretas"]
    termos_terceirizado = ["terceirizado", "terceirizada"]
    termos_ferias_vencidas = ["férias vencidas", "ferias vencidas", "férias não pagas", "ferias nao pagas"]
    termos_acao_judicial = ["ação judicial", "acao judicial", "entrou na justiça", "entrou na justica", "processo trabalhista"]
    termos_peticao = ["petição inicial", "peticao inicial", "inicial", "documento da ação", "documento da acao"]
    termos_banco_horas_sem_assinatura = ["banco de horas sem assinatura", "banco de horas sem assinar", "banco de horas não assinado", "banco de horas nao assinado"]
    termos_salario_picado = ["salário picado", "salario picado", "pagamento picado", "pago picado", "salario pago picado"]
    termos_recorrencia = ["vários meses", "varios meses", "recorrente", "todo mês", "todo mes", "sempre"]
    termos_pagamento_por_fora = ["paguei por fora", "pagamento por fora", "por fora varios meses", "por fora vários meses"]
    termos_jornada_sem_folga = ["domingo sem folga", "trabalhava domingo sem folga", "sem folga semanal"]
    termos_assedio_indicios = ["humilhava", "humilha", "constrangimento", "assédio", "assedio", "gerente humilhava"]

    gestante_dispensada = any(t in texto_lower for t in termos_gestante) and any(t in texto_lower for t in termos_desligamento)
    verbas_nao_pagas = any(t in texto_lower for t in termos_verbas_nao_pagas)
    justa_causa_sem_prova = "justa causa" in texto_lower and any(t in texto_lower for t in termos_sem_prova)
    tempo_meses = _extrair_tempo_meses(texto_lower)
    funcionario_sem_registro = any(t in texto_lower for t in termos_sem_registro) and tempo_meses >= 3
    acidente_sem_cat = any(t in texto_lower for t in termos_acidente) and any(t in texto_lower for t in termos_sem_cat)
    assedio_com_provas = any(t in texto_lower for t in termos_assedio) and any(t in texto_lower for t in termos_provas_assedio)
    horas_extras_habituais = any(t in texto_lower for t in termos_horas_extras)
    pedido_demissao_quitado = any(t in texto_lower for t in termos_pedido_demissao) and any(t in texto_lower for t in termos_quitacao)
    fgts_em_atraso = any(t in texto_lower for t in termos_fgts_atraso) and ("6 meses" in texto_lower or "7 meses" in texto_lower or "8 meses" in texto_lower or "9 meses" in texto_lower or "1 ano" in texto_lower or "12 meses" in texto_lower)
    pj_com_subordinacao = any(t in texto_lower for t in termos_pj_subordinado) and any(t in texto_lower for t in termos_subordinacao)
    terceirizado_subordinado = any(t in texto_lower for t in termos_terceirizado) and any(t in texto_lower for t in termos_subordinacao)
    ferias_vencidas_nao_pagas = any(t in texto_lower for t in termos_ferias_vencidas)
    rescisao_atrasada_10d = ("rescisao atrasou" in texto_lower or "rescisão atrasou" in texto_lower or "atraso rescisao" in texto_lower or "atraso rescisão" in texto_lower) and any(
        token in texto_lower for token in ["11 dias", "12 dias", "13 dias", "14 dias", "15 dias", "20 dias", "30 dias"]
    )
    acao_judicial_sem_peticao = any(t in texto_lower for t in termos_acao_judicial) and not any(t in texto_lower for t in termos_peticao)
    banco_horas_sem_assinatura = any(t in texto_lower for t in termos_banco_horas_sem_assinatura)
    salario_picado_recorrente = any(t in texto_lower for t in termos_salario_picado) and (
        any(t in texto_lower for t in termos_recorrencia) or "salario pago picado" in texto_lower
    )
    pagamento_por_fora_recorrente = any(t in texto_lower for t in termos_pagamento_por_fora)
    jornada_sem_folga = any(t in texto_lower for t in termos_jornada_sem_folga)
    assedio_indicios = any(t in texto_lower for t in termos_assedio_indicios)

    return {
        "gestante_dispensada": gestante_dispensada,
        "verbas_nao_pagas": verbas_nao_pagas,
        "justa_causa_sem_prova": justa_causa_sem_prova,
        "funcionario_sem_registro": funcionario_sem_registro,
        "acidente_sem_cat": acidente_sem_cat,
        "assedio_com_provas": assedio_com_provas,
        "horas_extras_habituais": horas_extras_habituais,
        "pedido_demissao_quitado": pedido_demissao_quitado,
        "fgts_em_atraso": fgts_em_atraso,
        "pj_com_subordinacao": pj_com_subordinacao,
        "terceirizado_subordinado": terceirizado_subordinado,
        "ferias_vencidas_nao_pagas": ferias_vencidas_nao_pagas,
        "rescisao_atrasada_10d": rescisao_atrasada_10d,
        "acao_judicial_sem_peticao": acao_judicial_sem_peticao,
        "banco_horas_sem_assinatura": banco_horas_sem_assinatura,
        "salario_picado_recorrente": salario_picado_recorrente,
        "pagamento_por_fora_recorrente": pagamento_por_fora_recorrente,
        "jornada_sem_folga": jornada_sem_folga,
        "assedio_indicios": assedio_indicios,
    }


def _aplicar_hard_rule_classificacao(tipo, gravidade, confianca, hard_rule):
    if hard_rule["pedido_demissao_quitado"]:
        return TipoRisco.RESCISAO, RiscoNivel.BAIXO, max(confianca, 0.70)
    if hard_rule["gestante_dispensada"]:
        return TipoRisco.RESCISAO, RiscoNivel.ALTO, max(confianca, 0.85)
    if hard_rule["verbas_nao_pagas"]:
        return TipoRisco.RESCISAO, RiscoNivel.ALTO, max(confianca, 0.82)
    if hard_rule["justa_causa_sem_prova"]:
        return TipoRisco.RESCISAO, RiscoNivel.ALTO, max(confianca, 0.80)
    if hard_rule["funcionario_sem_registro"]:
        return TipoRisco.RESCISAO, RiscoNivel.ALTO, max(confianca, 0.78)
    if hard_rule["acidente_sem_cat"]:
        return TipoRisco.ACIDENTE_TRABALHO, RiscoNivel.ALTO, max(confianca, 0.84)
    if hard_rule["assedio_com_provas"]:
        return TipoRisco.ASSEDIO_MORAL, RiscoNivel.ALTO, max(confianca, 0.83)
    if hard_rule["horas_extras_habituais"]:
        return TipoRisco.HORA_EXTRA, RiscoNivel.MEDIO, max(confianca, 0.72)
    if hard_rule["pj_com_subordinacao"] or hard_rule["terceirizado_subordinado"]:
        return TipoRisco.GERAL, RiscoNivel.ALTO, max(confianca, 0.80)
    if (
        hard_rule["fgts_em_atraso"]
        or hard_rule["ferias_vencidas_nao_pagas"]
        or hard_rule["rescisao_atrasada_10d"]
        or hard_rule["acao_judicial_sem_peticao"]
        or hard_rule["banco_horas_sem_assinatura"]
        or hard_rule["salario_picado_recorrente"]
        or hard_rule["pagamento_por_fora_recorrente"]
        or hard_rule["jornada_sem_folga"]
        or hard_rule["assedio_indicios"]
    ):
        return TipoRisco.GERAL, RiscoNivel.MEDIO, max(confianca, 0.65)
    return tipo, gravidade, confianca


def classificar_risco_ia_v2(texto):
    prompt = f"""
Você é um especialista em direito do trabalho brasileiro.

Classifique o risco jurídico trabalhista com prudência técnica.
NÃO force ALTO quando faltarem evidências.
Quando houver informação insuficiente, use "inconclusivo".

CASO:
{texto}

Regras:
- Use ALTO apenas com sinais claros e robustos.
- Se faltar contexto factual, use "inconclusivo".
- Retorne confiança entre 0 e 1.
- Liste lacunas de informação relevantes.

{{
  "tipo_risco": "assedio_moral | acidente_trabalho | conflito_interpessoal | rescisao | afastamento | hora_extra | geral | inconclusivo",
  "gravidade": "alto | medio | baixo | inconclusivo",
  "confianca": 0.0,
  "evidencias_textuais": ["..."],
  "faltam_dados": ["..."]
}}
"""

    try:
        resposta = client.responses.create(
            model="gpt-4.1",
            input=prompt,
            timeout=20
        )

        data = json.loads(resposta.output_text.strip())
    except Exception:
        data = {}

    tipo = _normalizar_tipo_risco(data.get("tipo_risco"))
    gravidade = _normalizar_gravidade(data.get("gravidade"))

    try:
        confianca = float(data.get("confianca", 0.45))
    except (TypeError, ValueError):
        confianca = 0.45
    confianca = max(0.0, min(1.0, confianca))

    evidencias_raw = data.get("evidencias_textuais")
    if not isinstance(evidencias_raw, list):
        evidencias_raw = []

    faltam_dados = data.get("faltam_dados")
    if not isinstance(faltam_dados, list):
        faltam_dados = []

    faltam_dados.extend(_detectar_lacunas(texto))
    faltam_dados = sorted({str(x).strip() for x in faltam_dados if str(x).strip()})
    hard_rule = _detectar_hard_rule_juridica(texto)

    # Segurança jurídica: nunca subir para ALTO por default/baixa confiança.
    if gravidade == RiscoNivel.ALTO and (confianca < 0.70 or len(evidencias_raw) == 0):
        gravidade = RiscoNivel.MEDIO if confianca >= 0.45 else RiscoNivel.INCONCLUSIVO

    tipo, gravidade, confianca = _aplicar_hard_rule_classificacao(tipo, gravidade, confianca, hard_rule)

    if tipo == TipoRisco.INCONCLUSIVO:
        gravidade = RiscoNivel.INCONCLUSIVO

    evidencias = [
        EvidenciaJuridica(
            descricao=str(item),
            fonte="llm_texto",
            status=StatusEvidencia.MODERADA,
            peso=1.0,
        )
        for item in evidencias_raw
        if str(item).strip()
    ]

    return ClassificacaoJuridicaV2(
        tipo_risco=tipo,
        gravidade=gravidade,
        confianca_classificacao=confianca,
        evidencias_detectadas=evidencias,
        lacunas_informacao=faltam_dados,
        flags_criticas=[],
    )


def classificar_risco_ia(texto):
    """
    Compatibilidade com integração atual do app.
    Retorna o formato legado esperado por `analisador_caso.py`.
    """
    v2 = classificar_risco_ia_v2(texto)
    gravidade_legacy = {
        RiscoNivel.ALTO: "alta",
        RiscoNivel.MEDIO: "media",
        RiscoNivel.BAIXO: "baixa",
        RiscoNivel.INCONCLUSIVO: "baixa",
    }[v2.gravidade]

    tipo_legacy = (
        v2.tipo_risco.value
        if v2.tipo_risco != TipoRisco.INCONCLUSIVO
        else "geral"
    )

    return {
        "tipo_risco": tipo_legacy,
        "gravidade": gravidade_legacy,
        "confianca": round(v2.confianca_classificacao, 3),
        "faltam_dados": v2.lacunas_informacao,
    }