"""
Agregação leve para o Dashboard Corporativo (fonte: session_state).
Não altera score_engine nem fluxos jurídicos.
"""

from collections import Counter
from datetime import date, datetime

import streamlit as st

from application.permissoes_use_cases import filtrar_casos_por_perfil


def _parse_gerado_para_data(valor) -> date | None:
    raw = str(valor or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.date()
    except ValueError:
        return None


def caso_dentro_do_periodo(caso: dict, data_inicio: date | None, data_fim: date | None) -> bool:
    """Filtra por gerado_em (parte da data). None em início/fim = sem limite naquele lado."""
    d = _parse_gerado_para_data(caso.get("gerado_em"))
    if d is None:
        return False
    if data_inicio is not None and d < data_inicio:
        return False
    if data_fim is not None and d > data_fim:
        return False
    return True


def _score_fluxo(rel: dict) -> int:
    try:
        return int((rel or {}).get("fluxo_consulta", {}).get("pontuacao") or 0)
    except (TypeError, ValueError):
        return 0


def _impacto_estimado_relatorio(rel: dict) -> float:
    se2 = (rel or {}).get("score_engine_v2") or {}
    valor = se2.get("impacto_financeiro_estimado")
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, v)


def _norm_empresa_id(empresa_id):
    if empresa_id is None:
        return None
    try:
        return int(empresa_id)
    except (TypeError, ValueError):
        return empresa_id


def _nivel_risco_display(rel: dict) -> str:
    nivel = str((rel or {}).get("nivel_risco_visual") or "").upper().replace("MEDIO", "MÉDIO")
    if nivel in {"ALTO", "MÉDIO", "BAIXO"}:
        return nivel
    risco = str((rel or {}).get("fluxo_consulta", {}).get("risco") or "INCONCLUSIVO").upper().replace(
        "MEDIO", "MÉDIO"
    )
    return risco if risco else "INCONCLUSIVO"


def _risco_metric_format(label: str) -> str:
    x = str(label or "").upper().replace("MEDIO", "MÉDIO")
    if x == "ALTO":
        return "🔴 ALTO"
    if x == "MÉDIO":
        return "🟡 MÉDIO"
    if x == "BAIXO":
        return "🟢 BAIXO"
    return "⚪ " + x


def _tema_caso(rel: dict) -> str:
    fluxo = (rel or {}).get("fluxo_consulta") or {}
    tema = fluxo.get("tipo_risco") or fluxo.get("tipo_caso") or "não_classificado"
    return str(tema).replace("_", " ").strip() or "não_classificado"


def _contar_acoes_pendentes(case_id: str, rel: dict, checklist_por_caso: dict) -> int:
    chk = rel.get("plano_acao_checklist") or []
    prox = rel.get("proximos_passos_recomendados") or []
    plano = list(chk) + list(prox)
    if not plano:
        plano = [
            "Validar documentos críticos em até 48h",
            "Evitar decisão irreversível sem validação",
        ]
    total = len(plano)
    if total == 0:
        return 0
    estado = checklist_por_caso.get(case_id) or {}
    return sum(1 for i in range(total) if not estado.get(f"acao_{i}"))


def agregar_dados_dashboard(
    empresa_id,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    usuario_visualizador_id=None,
    perfil_visualizador: str | None = None,
) -> dict:
    """
    Agrega casos ativos da empresa a partir de st.session_state['casos_ativos_notificacao'].
    Filtra primeiro por gerado_em ∈ [data_inicio, data_fim] (limites inclusivos; None = aberto).
    """
    eid = _norm_empresa_id(empresa_id)
    casos = list(st.session_state.get("casos_ativos_notificacao") or [])
    checklist_por_caso = st.session_state.get("checklist_estado_por_caso") or {}

    empty = {
        "casos_ativos": 0,
        "risco_moda": "INCONCLUSIVO",
        "risco_moda_ui": _risco_metric_format("INCONCLUSIVO"),
        "acoes_pendentes_total": 0,
        "impacto_potencial_agregado": 0.0,
        "impacto_potencial_agregado_fmt": "R$ 0",
        "distribuicao_risco": {},
        "distribuicao_tema": {},
        "tabela_casos": [],
    }

    if eid is None:
        return empty.copy()

    por_empresa = [c for c in casos if _norm_empresa_id(c.get("empresa_id")) == eid]
    por_empresa = filtrar_casos_por_perfil(por_empresa, usuario_visualizador_id, perfil_visualizador)
    filtrados = [c for c in por_empresa if caso_dentro_do_periodo(c, data_inicio, data_fim)]

    niveis = []
    temas = []
    total_pendentes = 0
    impacto_agregado = 0.0
    tabela = []

    for caso in filtrados:
        case_id = str(caso.get("case_id") or "")
        rel = caso.get("relatorio_payload") or {}
        impacto_agregado += _impacto_estimado_relatorio(rel)
        nivel = _nivel_risco_display(rel)
        niveis.append(nivel)
        tema = _tema_caso(rel)
        temas.append(tema)

        pendentes = _contar_acoes_pendentes(case_id, rel, checklist_por_caso)
        total_pendentes += pendentes

        diag = str(rel.get("diagnostico") or "").strip()
        if len(diag) > 120:
            diag = diag[:117] + "..."

        gerado_raw = str(caso.get("gerado_em") or "")
        try:
            dt = datetime.fromisoformat(gerado_raw.replace("Z", "+00:00"))
            data_fmt = dt.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            data_fmt = gerado_raw or "—"

        tabela.append(
            {
                "Diagnóstico Resumido": diag or "—",
                "Nível de Risco": nivel,
                "Data de Criação": data_fmt,
                "Ações Pendentes": pendentes,
                "case_id": case_id,
            }
        )

    contagem_risco = Counter(niveis)
    contagem_tema = Counter(temas)

    moda = "INCONCLUSIVO"
    if contagem_risco:
        moda = contagem_risco.most_common(1)[0][0]

    impacto_fmt = _format_reais_br(impacto_agregado)

    return {
        "casos_ativos": len(filtrados),
        "risco_moda": moda,
        "risco_moda_ui": _risco_metric_format(moda),
        "acoes_pendentes_total": total_pendentes,
        "impacto_potencial_agregado": impacto_agregado,
        "impacto_potencial_agregado_fmt": impacto_fmt,
        "distribuicao_risco": dict(contagem_risco),
        "distribuicao_tema": dict(contagem_tema),
        "tabela_casos": tabela,
    }


def _format_reais_br(valor: float) -> str:
    v = int(round(abs(valor)))
    texto = f"{v:,}".replace(",", ".")
    prefix = "R$ "
    if valor < 0:
        prefix += "-"
    return prefix + texto
