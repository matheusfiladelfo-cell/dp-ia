"""
Motor de pontuação v2 — usa apenas fatos persistidos e validados pelo usuário.
Opera em paralelo ao fluxo_consulta / score v1; não substitui o motor legado.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from application.calculadora_clt import (
    estimar_passivo_detalhado,
    fatos_dict_para_textos,
    formatar_passivo_markdown,
)
from application.parsing_br import (
    meses_entre_datas,
    parse_data_br,
    parse_moeda_br,
    parse_tempo_meses_fatos,
)
from banco import listar_fatos_validados, obter_mapa_fatos_validados

NAO_ENCONTRADO = frozenset(
    {
        "",
        "não encontrado",
        "nao encontrado",
        "n/a",
        "-",
        "null",
        "none",
    }
)

PONTUACAO_BASE = 10
FATOR_AJUSTE_IMPACTO_FINANCEIRO = 0.35


def _norm_txt(s: str) -> str:
    t = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _eh_vazio_ou_nao_encontrado(val: str) -> bool:
    x = str(val or "").strip().lower()
    return not x or x in NAO_ENCONTRADO


def _parse_data_bruta(val: str | None) -> date | None:
    if val is None or _eh_vazio_ou_nao_encontrado(str(val)):
        return None
    return parse_data_br(str(val))


def modificador_por_tipo_contrato(tipo_contrato: str) -> tuple[int, str | None]:
    if _eh_vazio_ou_nao_encontrado(tipo_contrato):
        return 0, None
    t = _norm_txt(tipo_contrato)
    if "clt" in t and not (
        re.search(r"\bpj\b", t)
        or re.search(r"\bmei\b", t)
        or "autonomo" in t
        or "prestador" in t
        or "pessoa juridica" in t
    ):
        return 0, "+0 pts: Tipo de vínculo declarado como CLT (sem acréscimo por reconhecimento de vínculo)."
    if (
        re.search(r"\bpj\b", t)
        or re.search(r"\bmei\b", t)
        or "autonomo" in t
        or "prestador" in t
        or "pessoa juridica" in t
        or t.strip() == "pj"
    ):
        return 20, "+20 pts: Contrato PJ / autônomo / MEI — maior risco de reconhecimento de vínculo empregatício."
    return 0, None


def modificador_por_tempo_servico(data_admissao: str, data_demissao: str) -> tuple[int, str | None]:
    adm = _parse_data_bruta(data_admissao)
    if adm is None:
        return 0, None
    dem = _parse_data_bruta(data_demissao) or date.today()
    if dem < adm:
        return 0, None
    dias = (dem - adm).days
    anos = int(dias // 365.25)
    pts = anos * 5
    if pts <= 0:
        return 0, None
    return pts, f"+{pts} pts: Tempo de serviço aproximado de {anos} ano(s) ({adm.strftime('%d/%m/%Y')} → {dem.strftime('%d/%m/%Y')})."


def modificador_por_motivo_reclamacao(motivo: str) -> tuple[int, str | None]:
    if _eh_vazio_ou_nao_encontrado(motivo):
        return 0, None
    t = _norm_txt(motivo)
    pts = 0
    trechos = []
    if any(k in t for k in ("assedio", "assédio", "discrimin", "assedi")):
        pts += 30
        trechos.append("indícios de assédio ou discriminação (+30)")
    if any(k in t for k in ("hora extra", "horas extras")):
        pts += 15
        trechos.append("horas extras (+15)")
    if pts == 0:
        return 0, None
    return pts, f"+{pts} pts: Motivo da reclamação ({', '.join(trechos)})."


def modificador_por_evidencias(evidencias_valor: str) -> tuple[int, str | None]:
    """valor_fato costuma ser string com itens separados por ';'."""
    if _eh_vazio_ou_nao_encontrado(evidencias_valor):
        return 0, None
    partes = [x.strip() for x in str(evidencias_valor).split(";") if x.strip()]
    if not partes:
        return 0, None
    return 10, f"+10 pts: Evidências ou provas citadas ({len(partes)} item(ns)) — caso mais formalizado/documentado."


def _nivel_por_score(score: int) -> str:
    if score < 35:
        return "BAIXO"
    if score < 70:
        return "MÉDIO"
    return "ALTO"


def _anos_servico_aprox(data_admissao: str, data_demissao: str) -> int:
    adm = _parse_data_bruta(data_admissao)
    if adm is None:
        return 0
    dem = _parse_data_bruta(data_demissao) or date.today()
    if dem < adm:
        return 0
    return int((dem - adm).days // 365.25)


def _conta_evidencias(evidencias_valor: str) -> int:
    if _eh_vazio_ou_nao_encontrado(evidencias_valor):
        return 0
    return len([x.strip() for x in str(evidencias_valor).split(";") if x.strip()])


def _parse_salario_float(valor: str | None) -> float | None:
    if valor is None or _eh_vazio_ou_nao_encontrado(str(valor)):
        return None
    return parse_moeda_br(valor)


def _obter_salario_de_fatos(fatos: dict) -> float | None:
    for chave in ("valor_salario", "salario", "salario_base", "salario_bruto"):
        v = parse_moeda_br(fatos.get(chave))
        if v is not None:
            return v
    return None


def _meses_servico_aprox(data_admissao: str, data_demissao: str) -> int:
    return meses_entre_datas(data_admissao, data_demissao)


def obter_fator_ajuste_dinamico(motivo_reclamacao: str) -> tuple[float, str]:
    motivo_norm = _norm_txt(str(motivo_reclamacao or ""))
    if ("assedio" in motivo_norm) or ("discriminacao" in motivo_norm):
        return 0.60, "Assédio/Discriminação"
    if ("vinculo" in motivo_norm) or ("pejotizacao" in motivo_norm):
        return 0.45, "Reconhecimento de Vínculo"
    if ("hora extra" in motivo_norm) or ("horas extras" in motivo_norm) or ("jornada" in motivo_norm):
        return 0.25, "Horas Extras/Jornada"
    return FATOR_AJUSTE_IMPACTO_FINANCEIRO, "Risco Geral"


def calcular_impacto_financeiro_v2(
    fatos: dict, score_final: int
) -> tuple[float, float, str, str]:
    """
    Retorna (total_estimado, fator_ajuste, categoria_risco, markdown_detalhado).
    markdown vazio quando não há base para cálculo.
    """
    try:
        salario = _obter_salario_de_fatos(fatos)
        if salario is None:
            return 0.0, 0.0, "Dados insuficientes", ""
        meses_servico = parse_tempo_meses_fatos(fatos)
        if meses_servico <= 0:
            return 0.0, 0.0, "Dados insuficientes", ""

        fator_ajuste, categoria = obter_fator_ajuste_dinamico(fatos.get("motivo_reclamacao", ""))
        textos = fatos_dict_para_textos(fatos)
        detalhe = estimar_passivo_detalhado(textos, float(salario), int(meses_servico))
        total = float(detalhe.get("total") or 0)

        if total <= 0:
            return 0.0, float(fator_ajuste), categoria, ""

        markdown = formatar_passivo_markdown(detalhe)
        return round(total, 2), float(fator_ajuste), categoria, markdown
    except (TypeError, ValueError):
        return 0.0, 0.0, "Dados insuficientes", ""


def _texto_tem_subordinacao(txt: str) -> bool:
    t = _norm_txt(txt)
    chaves = (
        "subordinacao",
        "subordinação",
        "ordens diretas",
        "controle de jornada",
        "hierarquia",
        "superior direto",
    )
    return any(k in t for k in chaves)


def _texto_cargo_gestao(cargo: str) -> bool:
    t = _norm_txt(cargo)
    return ("gerente" in t) or ("coordenador" in t)


def _regra_tipo_contrato(fatos: dict) -> tuple[int, str | None]:
    return modificador_por_tipo_contrato(fatos.get("tipo_contrato", ""))


def _regra_tempo_servico(fatos: dict) -> tuple[int, str | None]:
    return modificador_por_tempo_servico(
        fatos.get("data_admissao", ""),
        fatos.get("data_demissao", ""),
    )


def _regra_motivo_reclamacao(fatos: dict) -> tuple[int, str | None]:
    return modificador_por_motivo_reclamacao(fatos.get("motivo_reclamacao", ""))


def _regra_evidencias(fatos: dict) -> tuple[int, str | None]:
    return modificador_por_evidencias(fatos.get("evidencias_mencionadas", ""))


def ponderador_vinculo_agravado(fatos: dict, _score_atual: float) -> tuple[float, str | None]:
    tipo = _norm_txt(str(fatos.get("tipo_contrato", "")))
    is_pj = (
        (" pj " in f" {tipo} ")
        or ("mei" in tipo)
        or ("autonomo" in tipo)
        or ("prestador" in tipo)
        or ("pessoa juridica" in tipo)
    )
    anos_servico = _anos_servico_aprox(
        fatos.get("data_admissao", ""),
        fatos.get("data_demissao", ""),
    )
    motivo = str(fatos.get("motivo_reclamacao", ""))
    cargo = str(fatos.get("cargo", ""))
    if is_pj and anos_servico > 1 and (_texto_tem_subordinacao(motivo) or _texto_cargo_gestao(cargo)):
        return (
            1.3,
            "* Fator de Risco Agravado (x1.3): Contrato PJ de longa duração com indícios de subordinação.",
        )
    return 1.0, None


def ponderador_assedio_com_provas(fatos: dict, _score_atual: float) -> tuple[float, str | None]:
    motivo = _norm_txt(str(fatos.get("motivo_reclamacao", "")))
    if "assedio" in motivo and _conta_evidencias(fatos.get("evidencias_mencionadas", "")) > 0:
        return (
            1.5,
            "* Fator de Risco Crítico (x1.5): Alegação de assédio com menção a evidências documentais.",
        )
    return 1.0, None


def calcular_score_v2_1(fatos: dict) -> tuple[int, str, list[str], float, float, float, str]:
    racional: list[str] = []
    score_base = float(PONTUACAO_BASE)
    racional.append(f"Pontuação base: {PONTUACAO_BASE} pts.")

    regras_de_risco = [
        _regra_tipo_contrato,
        _regra_tempo_servico,
        _regra_motivo_reclamacao,
        _regra_evidencias,
    ]
    for regra in regras_de_risco:
        delta, msg = regra(fatos)
        score_base += float(delta or 0)
        if msg:
            racional.append(msg)

    score_ponderado = score_base
    modificadores_de_ponderacao = [
        ponderador_vinculo_agravado,
        ponderador_assedio_com_provas,
    ]
    for ponderador in modificadores_de_ponderacao:
        fator, msg = ponderador(fatos, score_ponderado)
        try:
            fator_num = float(fator)
        except (TypeError, ValueError):
            fator_num = 1.0
        if fator_num < 0:
            fator_num = 1.0
        score_ponderado *= fator_num
        if msg:
            racional.append(msg)

    score_final = min(100, max(0, int(round(score_ponderado))))
    racional.append(
        f"Total base: {int(round(score_base))} pts; após ponderações: {round(score_ponderado, 2)} pts → score final: {score_final}/100."
    )
    impacto_estimado, fator_ajuste, categoria_fator, impacto_md = calcular_impacto_financeiro_v2(
        fatos, score_final
    )
    if impacto_estimado > 0 and impacto_md:
        racional.append(impacto_md)
        racional.append(
            f"Categoria de risco considerada no contexto: '{categoria_fator}'."
        )
    elif impacto_estimado > 0:
        racional.append(
            f"Cálculo de Impacto Financeiro: total estimado R$ {impacto_estimado:,.2f}."
        )
    else:
        racional.append(
            "Cálculo de Impacto Financeiro: não foi possível estimar por falta de salário, "
            "período de serviço válidos ou palavras-chave de verbas nos fatos validados."
        )
    return (
        score_final,
        _nivel_por_score(score_final),
        racional,
        score_ponderado,
        impacto_estimado,
        fator_ajuste,
        categoria_fator,
        impacto_md,
    )


def executar_score_engine_v2(analise_id: int) -> dict:
    """
    Calcula score 0–100 com base exclusivamente em analises_fatos_validados.
    """
    try:
        aid = int(analise_id)
    except (TypeError, ValueError):
        return {
            "disponivel": False,
            "score_final": None,
            "nivel": None,
            "racional": ["analise_id inválido."],
            "fatos_utilizados": {},
            "pontuacao_bruta": None,
        }

    if not listar_fatos_validados(aid):
        return {
            "disponivel": False,
            "score_final": None,
            "nivel": None,
            "racional": ["Não há fatos validados gravados para este ID de análise."],
            "fatos_utilizados": {},
            "pontuacao_bruta": None,
        }

    fatos = obter_mapa_fatos_validados(aid)
    (
        score_final,
        nivel,
        racional,
        pontuacao_bruta,
        impacto_estimado,
        fator_ajuste,
        categoria_fator,
        impacto_md,
    ) = calcular_score_v2_1(fatos)

    return {
        "disponivel": True,
        "score_final": score_final,
        "nivel": nivel,
        "racional": racional,
        "fatos_utilizados": dict(fatos),
        "pontuacao_bruta": pontuacao_bruta,
        "impacto_financeiro_estimado": impacto_estimado,
        "fator_ajuste_impacto": fator_ajuste,
        "categoria_fator_impacto": categoria_fator,
        "impacto_financeiro_detalhe_md": impacto_md,
    }
