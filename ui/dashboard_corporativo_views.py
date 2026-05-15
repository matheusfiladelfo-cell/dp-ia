from datetime import date, timedelta

import pandas as pd
import streamlit as st

from application.auditoria_risco_massa import executar_auditoria_risco_massa
from application.dashboard_corporativo_use_cases import agregar_dados_dashboard
from banco import obter_ultima_auditoria_risco_massa, salvar_auditoria_risco_massa


_PERIODO_OPCOES = ("Últimos 7 dias", "Últimos 30 dias", "Este Mês", "Desde o início")


def _periodo_para_intervalo(preset: str) -> tuple[date | None, date | None]:
    hoje = date.today()
    if preset == "Desde o início":
        return None, None
    if preset == "Este Mês":
        return hoje.replace(day=1), hoje
    dias = 7 if preset == "Últimos 7 dias" else 30
    return hoje - timedelta(days=dias), hoje


def _processar_clique_tabela_casos(
    edited: pd.DataFrame,
    case_ids: list[str],
    sig: tuple,
) -> None:
    """Detecta checkbox 'Ver detalhes' marcado e redireciona ao Painel de Controle."""
    col = "Ver detalhes"
    if col not in edited.columns or len(edited) != len(case_ids):
        return

    checks_now = edited[col].tolist()
    prev_key = "_dash_prev_checks"
    sig_key = "_dash_table_sig"

    if st.session_state.get(sig_key) != sig:
        st.session_state[sig_key] = sig
        st.session_state[prev_key] = [False] * len(checks_now)

    checks_prev = st.session_state.get(prev_key) or [False] * len(checks_now)
    if len(checks_prev) != len(checks_now):
        checks_prev = [False] * len(checks_now)

    for i, (now, antes) in enumerate(zip(checks_now, checks_prev)):
        if now and not antes and case_ids[i]:
            st.session_state["caso_selecionado_para_exibicao"] = case_ids[i]
            st.session_state["controlador_abas_relatorio"] = "Painel de Controle"
            st.session_state["pagina_ativa"] = "Nova Análise"
            st.session_state.pop(prev_key, None)
            st.session_state.pop(sig_key, None)
            st.rerun()

    st.session_state[prev_key] = checks_now


def _render_dashboard_visao_geral(
    empresa_id,
    usuario_visualizador_id=None,
    perfil_visualizador: str | None = None,
):
    st.markdown("##### Período")
    preset = st.selectbox(
        "Filtrar por data de criação do caso",
        _PERIODO_OPCOES,
        key="dashboard_periodo_preset",
        label_visibility="collapsed",
    )
    di, df = _periodo_para_intervalo(preset)
    if preset != "Desde o início":
        st.caption(
            f"Mostrando casos com **gerado_em** entre **{di.strftime('%d/%m/%Y')}** e **{df.strftime('%d/%m/%Y')}** (limites inclusivos)."
        )
    else:
        st.caption("Mostrando **todos** os casos da empresa nesta sessão (sem limite de datas).")

    dados = agregar_dados_dashboard(
        empresa_id,
        di,
        df,
        usuario_visualizador_id=usuario_visualizador_id,
        perfil_visualizador=perfil_visualizador,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Casos Ativos", value=str(dados["casos_ativos"]))
    with c2:
        st.metric("Nível de Risco Médio (moda)", value=dados["risco_moda_ui"])
    with c3:
        st.metric(
            "Ações Pendentes",
            value=str(dados["acoes_pendentes_total"]),
        )
    with c4:
        st.metric(
            "Impacto Potencial Agregado",
            value=dados["impacto_potencial_agregado_fmt"],
        )
        st.caption(
            "Estimativa potencial agregada com base em salário, tempo de serviço e nível de risco (score v2 quando disponível). "
            "Não corresponde a cálculo exato de verbas nem a passivo contábil final."
        )

    st.markdown("---")
    g1, g2 = st.columns(2)

    dist_risco = dados["distribuicao_risco"]
    dist_tema = dados["distribuicao_tema"]

    with g1:
        st.markdown("#### Distribuição de Risco")
        if dist_risco:
            df_r = pd.DataFrame(
                {"nível": list(dist_risco.keys()), "casos": list(dist_risco.values())}
            )
            st.bar_chart(df_r, x="nível", y="casos", horizontal=True)
        else:
            st.caption("Sem casos no período selecionado.")

    with g2:
        st.markdown("#### Principais Tipos de Risco")
        if dist_tema:
            df_t = pd.DataFrame(
                {"tema": list(dist_tema.keys()), "casos": list(dist_tema.values())}
            )
            df_t = df_t.sort_values("casos", ascending=False)
            st.bar_chart(df_t, x="tema", y="casos", horizontal=True)
        else:
            st.caption("Sem temas para exibir no período.")

    st.markdown("#### Casos Ativos")
    rows = dados["tabela_casos"]
    if rows:
        case_ids = [str(r.get("case_id") or "") for r in rows]
        df_body = pd.DataFrame([{k: v for k, v in r.items() if k != "case_id"} for r in rows])
        df_show = df_body.copy()
        df_show.insert(0, "Ver detalhes", False)

        cols_desabilitadas = [
            c for c in df_show.columns if c != "Ver detalhes"
        ]

        editor_key = f"dash_casos_editor_{empresa_id}_{preset}_{di}_{df}"
        edited = st.data_editor(
            df_show,
            disabled=cols_desabilitadas,
            hide_index=True,
            width="stretch",
            key=editor_key,
            column_config={
                "Ver detalhes": st.column_config.CheckboxColumn(
                    "Ver detalhes",
                    help="Marque para abrir o Painel de Controle deste caso.",
                    default=False,
                ),
            },
        )

        sig_tabela = (empresa_id, preset, di, df)
        _processar_clique_tabela_casos(edited, case_ids, sig_tabela)

        st.caption(
            "Marque **Ver detalhes** na linha do caso para ir ao Painel de Controle (você será levado à Nova Análise)."
        )
    else:
        st.info(
            "Nenhum caso no período para esta empresa. "
            "Ajuste o filtro ou gere relatórios de consultoria para alimentar o dashboard."
        )


def _render_auditoria_folha(empresa_id: int, usuario_visualizador_id=None):
    st.markdown("#### Auditoria de Folha")
    st.caption(
        "Heurísticas rápidas sobre colaboradores na base de integração (payroll). "
        "A execução é manual para controlar carga no servidor."
    )

    registro = obter_ultima_auditoria_risco_massa(empresa_id)
    col_btn, col_when = st.columns([1, 2])
    with col_btn:
        executar = st.button(
            "Executar Auditoria de Risco em Massa",
            key=f"dash_auditoria_massa_{empresa_id}",
            type="primary",
        )
    with col_when:
        if registro:
            st.caption(f"Última auditoria gravada: **{registro.get('executada_em') or '—'}**")
        else:
            st.caption("Nenhuma auditoria gravada ainda para esta empresa.")

    if executar:
        with st.spinner("Executando auditoria de risco em massa..."):
            resultado = executar_auditoria_risco_massa(int(empresa_id))
            salvar_auditoria_risco_massa(
                int(empresa_id),
                int(usuario_visualizador_id or 0),
                resultado,
            )
        st.success("Auditoria concluída e resultados salvos.")
        st.rerun()

    ultimo = obter_ultima_auditoria_risco_massa(empresa_id)
    res = (ultimo or {}).get("resultado") if ultimo else None
    if not res:
        st.info(
            "Quando houver funcionários sincronizados em **Integrações**, execute a auditoria para ver KPIs e detalhes."
        )
        return

    ri = res.get("riscos_identificados") or {}
    m0, m1, m2, m3, m4 = st.columns(5)
    with m0:
        st.metric("Funcionários auditados", str(res.get("total_funcionarios_auditados", 0)))
    with m1:
        st.metric(
            "Com risco identificado",
            str(res.get("total_funcionarios_com_risco", 0)),
        )
    with m2:
        st.metric("Vínculo PJ", str(ri.get("risco_vinculo_pj", 0)))
    with m3:
        st.metric(
            "Equiparação salarial",
            str(ri.get("risco_equiparacao_salarial", 0)),
        )
    with m4:
        st.metric("Longo tempo de casa", str(ri.get("risco_longo_servico", 0)))

    st.markdown("##### Colaboradores sinalizados")
    lista = res.get("lista_funcionarios_risco") or []
    if not lista:
        st.caption("Nenhum colaborador correspondeu às regras na última auditoria.")
        return

    df_alvos = pd.DataFrame(lista)
    renomear = {
        "id": "ID interno",
        "employee_id_externo": "ID externo",
        "nome": "Nome",
        "risco": "Motivo",
    }
    df_alvos = df_alvos.rename(columns={k: v for k, v in renomear.items() if k in df_alvos.columns})
    st.dataframe(df_alvos, hide_index=True, width="stretch")


def render_dashboard_corporativo(
    empresa_id,
    empresa_nome: str | None,
    usuario_visualizador_id=None,
    perfil_visualizador: str | None = None,
):
    st.markdown("### Dashboard Corporativo")
    if empresa_nome:
        st.caption(f"Empresa selecionada: **{empresa_nome}**")

    if not empresa_id:
        st.warning("Selecione uma empresa na barra lateral para visualizar o dashboard.")
        return

    tab_visao, tab_auditoria = st.tabs(["Visão geral", "Auditoria de Folha"])
    with tab_visao:
        _render_dashboard_visao_geral(
            empresa_id,
            usuario_visualizador_id=usuario_visualizador_id,
            perfil_visualizador=perfil_visualizador,
        )
    with tab_auditoria:
        _render_auditoria_folha(empresa_id, usuario_visualizador_id=usuario_visualizador_id)
