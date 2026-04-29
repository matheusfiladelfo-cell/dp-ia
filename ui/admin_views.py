"""
Painel administrativo (master único). Não altera fluxo de login nem motor jurídico.
"""
from __future__ import annotations

import csv
import html
import io
import os
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from banco import (
    LEAD_CRM_STATUSES,
    admin_alertas_automaticos,
    admin_count_analises,
    admin_count_leads,
    admin_count_usuarios,
    admin_count_usuarios_ativos_7d,
    admin_crm_atualizar_lead,
    admin_crm_kpis,
    admin_crm_listar_leads,
    admin_definir_bloqueio_usuario,
    admin_definir_plano_e_status,
    admin_export_analises_rows,
    admin_export_leads_rows,
    admin_export_usuarios_rows,
    admin_fin_base_por_plano,
    admin_fin_checkout_volume_mensal_6m,
    admin_fin_kpis_executivo,
    admin_fin_receita_por_plano,
    admin_fin_ultimos_checkouts_pagos,
    admin_fin_ultimos_suspensos,
    admin_listar_usuarios_gestao,
    admin_receita_estimada_mensal_brl,
    admin_series_cadastros_30_dias,
    admin_series_leads_30_dias,
    admin_ultimos_leads,
    admin_ultimos_usuarios,
)

# Normalizado em minúsculas para comparação segura.
ADMIN_MASTER_EMAIL = os.environ.get(
    "ADMIN_MASTER_EMAIL", "matheus.filadelfo@gmail.com"
).strip().lower()


def is_admin_master(email: str | None) -> bool:
    if not email or not str(email).strip():
        return False
    return str(email).strip().lower() == ADMIN_MASTER_EMAIL


def apply_sidebar_admin_visibility(email: str | None) -> None:
    """
    Oculta o item da página admin no menu lateral para quem não é master.
    Depende da estrutura do Streamlit multipage (href contém 'admin').
    """
    if is_admin_master(email):
        return
    st.markdown(
        """
<style>
section[data-testid="stSidebar"] nav[data-testid="stSidebarNav"] a[href*="admin"],
section[data-testid="stSidebar"] nav[data-testid="stSidebarNav"] a[href*="Admin"] {
    display: none !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_admin_access_denied() -> None:
    st.markdown(
        """
<div style="padding:1.5rem;border-radius:16px;border:1px solid rgba(248,113,113,0.45);
background:rgba(30,41,59,0.85);max-width:560px;">
  <div style="font-size:1.1rem;font-weight:800;color:#fecaca;">Acesso negado</div>
  <div style="margin-top:0.5rem;color:#cbd5e1;">Esta área é exclusiva do administrador master.</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _series_to_df_last_30(series_rows):
    start = date.today() - timedelta(days=29)
    counts = {str(d): int(c) for d, c in series_rows}
    rows = []
    for i in range(30):
        day = start + timedelta(days=i)
        key = day.isoformat()
        rows.append({"dia": pd.Timestamp(day), "qtd": counts.get(key, 0)})
    return pd.DataFrame(rows)


def _chart_line(df: pd.DataFrame, title: str, color: str):
    return (
        alt.Chart(df)
        .mark_area(line={"color": color}, color=color, opacity=0.28)
        .encode(
            x=alt.X("dia:T", title="Dia"),
            y=alt.Y("qtd:Q", title="Quantidade"),
            tooltip=[
                alt.Tooltip("dia:T", title="Data"),
                alt.Tooltip("qtd:Q", title="Qtd"),
            ],
        )
        .properties(height=240, title=title)
        .configure_axis(labelColor="#94a3b8", titleColor="#cbd5e1")
        .configure_title(color="#f1f5f9", fontSize=16)
        .configure_view(strokeWidth=0)
    )


_CRM_STATUS_LABELS = {
    "novo": "Novo",
    "contato_feito": "Contato feito",
    "demo_agendada": "Demo agendada",
    "proposta_enviada": "Proposta enviada",
    "cliente_fechado": "Cliente fechado",
    "perdido": "Perdido",
    "pausado": "Pausado",
}


def _crm_label_status(st_key: str) -> str:
    return _CRM_STATUS_LABELS.get(st_key, st_key)


def _csv_bytes(rows: list, header: list[str]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


_PLANO_FIN_LABEL = {"FREE": "Trial / Free", "PRO": "Pro", "PREMIUM": "Business"}


def _render_financeiro_executivo() -> None:
    st.markdown(
        """
<div class="mp-fin-wrap">
  <div class="mp-fin-title">Financeiro Executivo</div>
  <div class="mp-fin-sub">MRR em catálogo (PRO R$197 · PREMIUM R$397) · checkout como proxy de fluxo</div>
</div>
""",
        unsafe_allow_html=True,
    )

    fin = admin_fin_kpis_executivo()
    fk = st.columns(5)
    with fk[0]:
        st.markdown(
            f'<div class="mp-fin-kpi"><div class="lab">MRR estimado</div>'
            f'<div class="val">R$ {fin["mrr_estimado"]:,.0f}</div></div>',
            unsafe_allow_html=True,
        )
    with fk[1]:
        st.markdown(
            f'<div class="mp-fin-kpi"><div class="lab">Pagantes ativos</div>'
            f'<div class="val">{fin["pagantes_ativos"]:,}</div></div>',
            unsafe_allow_html=True,
        )
    with fk[2]:
        st.markdown(
            f'<div class="mp-fin-kpi"><div class="lab">Ticket médio</div>'
            f'<div class="val">R$ {fin["ticket_medio"]:,.2f}</div></div>',
            unsafe_allow_html=True,
        )
    with fk[3]:
        st.markdown(
            f'<div class="mp-fin-kpi"><div class="lab">Suspensos</div>'
            f'<div class="val">{fin["suspensos_total"]:,}</div></div>',
            unsafe_allow_html=True,
        )
    with fk[4]:
        st.markdown(
            f'<div class="mp-fin-kpi"><div class="lab">Trials ativos</div>'
            f'<div class="val">{fin["trials_ativos"]:,}</div></div>',
            unsafe_allow_html=True,
        )

    ir = st.columns(3)
    with ir[0]:
        st.markdown(
            f'<div class="mp-fin-ind"><div class="lv">Upgrades (mês)</div>'
            f'<div class="vv">{fin["upgrades_mes"]:,}</div></div>',
            unsafe_allow_html=True,
        )
    with ir[1]:
        st.markdown(
            f'<div class="mp-fin-ind"><div class="lv">Downgrades / volta Free (mês)</div>'
            f'<div class="vv">{fin["downgrades_mes"]:,}</div></div>',
            unsafe_allow_html=True,
        )
    with ir[2]:
        st.markdown(
            f'<div class="mp-fin-ind"><div class="lv">Churn estimado</div>'
            f'<div class="vv">{fin["churn_estimado_pct"]:.1f}%</div></div>',
            unsafe_allow_html=True,
        )

    st.caption(
        "Upgrades = usuários distintos com checkout pago no mês. Downgrades = contas ativas Free "
        "atualizadas no mês com histórico de checkout pago. Churn = suspensões no mês ÷ pagantes ativos."
    )

    rows_rec = admin_fin_receita_por_plano()
    rows_base = admin_fin_base_por_plano()
    vol_raw = admin_fin_checkout_volume_mensal_6m()
    df_vol = pd.DataFrame(vol_raw, columns=["mes", "valor"])
    if len(df_vol) > 6:
        df_vol = df_vol.tail(6)

    g1, g2, g3 = st.columns(3)
    with g1:
        if rows_rec:
            df_r = pd.DataFrame(rows_rec, columns=["plano", "mrr"])
            df_r["rotulo"] = df_r["plano"].map(lambda p: _PLANO_FIN_LABEL.get(p, p))
            ch1 = (
                alt.Chart(df_r)
                .mark_bar(color="#38bdf8")
                .encode(
                    x=alt.X("mrr:Q", title="R$"),
                    y=alt.Y("rotulo:N", title="", sort="-x"),
                    tooltip=[
                        alt.Tooltip("rotulo:N", title="Plano"),
                        alt.Tooltip("mrr:Q", title="MRR", format=",.2f"),
                    ],
                )
                .properties(height=240, title="MRR estimado por plano")
                .configure_axis(labelColor="#94a3b8", titleColor="#cbd5e1")
                .configure_title(color="#fefce8", fontSize=15)
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(ch1, use_container_width=True)
        else:
            st.caption("Sem receita recorrente por plano.")

    with g2:
        if rows_base:
            df_b = pd.DataFrame(rows_base, columns=["plano", "base"])
            df_b["rotulo"] = df_b["plano"].map(lambda p: _PLANO_FIN_LABEL.get(p, p))
            ch2 = (
                alt.Chart(df_b)
                .mark_arc(innerRadius=50, stroke="#1e293b")
                .encode(
                    theta=alt.Theta("base:Q", title="contas"),
                    color=alt.Color(
                        "rotulo:N",
                        legend=alt.Legend(title=None),
                        scale=alt.Scale(scheme="darkmulti"),
                    ),
                    tooltip=[
                        alt.Tooltip("rotulo:N", title="Plano"),
                        alt.Tooltip("base:Q", title="Contas"),
                    ],
                )
                .properties(height=260, title="Base ativa por plano")
                .configure_title(color="#fefce8", fontSize=15)
            )
            st.altair_chart(ch2, use_container_width=True)
        else:
            st.caption("Sem dados de base.")

    with g3:
        if len(df_vol) > 0:
            base_v = alt.Chart(df_vol)
            area_v = base_v.mark_area(
                line={"color": "#fbbf24"},
                color="#f59e0b",
                opacity=0.35,
            ).encode(
                x=alt.X("mes:T", title="Mês"),
                y=alt.Y("valor:Q", title="R$ checkout"),
                tooltip=[
                    alt.Tooltip("mes:T", title="Mês"),
                    alt.Tooltip("valor:Q", title="Total", format=",.2f"),
                ],
            )
            line_v = base_v.mark_line(color="#fde68a", point=True).encode(
                x="mes:T",
                y="valor:Q",
            )
            ch3 = (
                (area_v + line_v)
                .properties(height=260, title="Volume checkout pago (proxy evolução)")
                .configure_axis(labelColor="#94a3b8", titleColor="#cbd5e1")
                .configure_title(color="#fefce8", fontSize=15)
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(ch3, use_container_width=True)
        else:
            st.caption("Sem checkout pago no período.")

    st.markdown("##### Movimentações recentes")
    t1, t2 = st.columns(2)
    with t1:
        st.markdown("<strong>Últimos upgrades (checkout pago)</strong>", unsafe_allow_html=True)
        up = admin_fin_ultimos_checkouts_pagos(12)
        if up:
            df_u = pd.DataFrame(
                up,
                columns=[
                    "usuario_id",
                    "email",
                    "plano_destino",
                    "valor",
                    "data",
                    "status_pg",
                ],
            )
            st.dataframe(df_u, use_container_width=True, hide_index=True)
        else:
            st.caption("Nenhum checkout pago registrado.")
    with t2:
        st.markdown("<strong>Últimos suspensos</strong>", unsafe_allow_html=True)
        sp = admin_fin_ultimos_suspensos(12)
        if sp:
            df_s = pd.DataFrame(
                sp,
                columns=["usuario_id", "email", "plano", "data"],
            )
            st.dataframe(df_s, use_container_width=True, hide_index=True)
        else:
            st.caption("Nenhuma assinatura suspensa.")


def _render_alertas_automaticos() -> None:
    rows = admin_alertas_automaticos()
    nivel_cls = {
        "warning": "mp-alert-warning",
        "danger": "mp-alert-danger",
        "success": "mp-alert-success",
        "info": "mp-alert-info",
    }
    if not rows:
        st.markdown(
            '<div class="mp-alert-neutral">Sem alertas automáticos no momento — métricas dentro dos limiares configurados.</div>',
            unsafe_allow_html=True,
        )
        return
    parts = ['<div class="mp-alert-stack">']
    for a in rows:
        nc = nivel_cls.get(str(a.get("nivel", "info")), "mp-alert-info")
        titulo = html.escape(str(a.get("titulo", "")))
        texto = html.escape(str(a.get("texto", "")))
        parts.append(
            f'<div class="mp-alert-item {nc}">'
            f'<div class="mp-alert-item-title">{titulo}</div>'
            f'<div class="mp-alert-item-text">{texto}</div></div>'
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_admin_dashboard() -> None:
    st.markdown(
        """
<style>
    .mp-admin-header {
        padding: 1.35rem 1.45rem;
        border-radius: 18px;
        background: linear-gradient(138deg, rgba(15,23,42,0.96), rgba(30,58,138,0.42));
        border: 1px solid rgba(212,175,55,0.38);
        box-shadow: 0 18px 46px rgba(2,6,23,0.48), 0 0 36px rgba(59,130,246,0.14);
        margin-bottom: 1rem;
    }
    .mp-admin-title { margin: 0; font-size: 1.55rem; font-weight: 900; color: #f8fafc; letter-spacing: 0.02em; }
    .mp-admin-sub { margin: 0.45rem 0 0 0; color: #cbd5e1; font-size: 0.95rem; }
    .mp-admin-kpi {
        border: 1px solid rgba(148,163,184,0.28);
        border-radius: 14px;
        background: rgba(15,23,42,0.82);
        padding: 0.85rem 1rem;
        box-shadow: 0 10px 26px rgba(2,6,23,0.32);
    }
    .mp-admin-kpi .lab { font-size: 0.72rem; font-weight: 800; letter-spacing: 0.08em;
      text-transform: uppercase; color: #93c5fd; }
    .mp-admin-kpi .val { font-size: 1.55rem; font-weight: 900; color: #f8fafc; margin-top: 0.25rem; }
    .mp-admin-block {
        border: 1px solid rgba(148,163,184,0.22);
        border-radius: 14px;
        background: rgba(15,23,42,0.76);
        padding: 0.9rem 1rem;
        margin-top: 0.65rem;
    }
    .mp-crm-wrap {
        margin: 1.15rem 0 0.85rem 0;
        padding: 1.15rem 1.25rem;
        border-radius: 18px;
        border: 1px solid rgba(96,165,250,0.32);
        background: linear-gradient(168deg, rgba(15,23,42,0.94), rgba(30,27,75,0.35));
        box-shadow: 0 16px 44px rgba(2,6,23,0.45), 0 0 28px rgba(59,130,246,0.1);
    }
    .mp-crm-title {
        margin: 0 0 0.35rem 0;
        font-size: 1.22rem;
        font-weight: 900;
        color: #f8fafc;
        letter-spacing: 0.02em;
    }
    .mp-crm-sub {
        margin: 0 0 1rem 0;
        color: #94a3b8;
        font-size: 0.9rem;
    }
    .mp-crm-kpi {
        border: 1px solid rgba(167,139,250,0.28);
        border-radius: 14px;
        background: rgba(15,23,42,0.78);
        padding: 0.75rem 0.85rem;
    }
    .mp-crm-kpi .lab {
        font-size: 0.68rem;
        font-weight: 800;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        color: #c4b5fd;
    }
    .mp-crm-kpi .val {
        font-size: 1.35rem;
        font-weight: 900;
        color: #faf5ff;
        margin-top: 0.2rem;
    }
    .mp-fin-wrap {
        margin: 1.2rem 0 0.9rem 0;
        padding: 1.2rem 1.3rem;
        border-radius: 18px;
        border: 1px solid rgba(212,175,55,0.35);
        background: linear-gradient(165deg, rgba(15,23,42,0.97), rgba(30,64,175,0.2));
        box-shadow: 0 16px 40px rgba(2,6,23,0.48);
    }
    .mp-fin-title {
        margin: 0 0 0.3rem 0;
        font-size: 1.22rem;
        font-weight: 900;
        color: #fefce8;
        letter-spacing: 0.02em;
    }
    .mp-fin-sub { margin: 0 0 1rem 0; color: #a8a29e; font-size: 0.88rem; }
    .mp-fin-kpi {
        border: 1px solid rgba(212,175,55,0.28);
        border-radius: 14px;
        background: rgba(15,23,42,0.82);
        padding: 0.72rem 0.85rem;
    }
    .mp-fin-kpi .lab {
        font-size: 0.66rem;
        font-weight: 800;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        color: #fcd34d;
    }
    .mp-fin-kpi .val {
        font-size: 1.28rem;
        font-weight: 900;
        color: #fffbeb;
        margin-top: 0.18rem;
    }
    .mp-fin-ind {
        border: 1px solid rgba(148,163,184,0.22);
        border-radius: 12px;
        background: rgba(30,41,59,0.65);
        padding: 0.65rem 0.8rem;
        text-align: center;
    }
    .mp-fin-ind .lv { font-size: 0.72rem; color: #94a3b8; font-weight: 700; }
    .mp-fin-ind .vv { font-size: 1.15rem; font-weight: 900; color: #e2e8f0; margin-top: 0.2rem; }
    .mp-alert-stack { display: flex; flex-direction: column; gap: 0.55rem; margin-bottom: 1rem; }
    .mp-alert-item {
        border-radius: 12px; padding: 0.75rem 1rem;
        border: 1px solid rgba(148,163,184,0.22);
        background: rgba(15,23,42,0.72);
    }
    .mp-alert-item-title { font-size: 0.82rem; font-weight: 800; letter-spacing: 0.04em; margin-bottom: 0.25rem; }
    .mp-alert-item-text { font-size: 0.88rem; color: #cbd5e1; line-height: 1.45; }
    .mp-alert-warning { border-left: 4px solid #f59e0b; }
    .mp-alert-warning .mp-alert-item-title { color: #fcd34d; }
    .mp-alert-danger { border-left: 4px solid #ef4444; }
    .mp-alert-danger .mp-alert-item-title { color: #fca5a5; }
    .mp-alert-success { border-left: 4px solid #22c55e; }
    .mp-alert-success .mp-alert-item-title { color: #86efac; }
    .mp-alert-info { border-left: 4px solid #3b82f6; }
    .mp-alert-info .mp-alert-item-title { color: #93c5fd; }
    .mp-alert-neutral {
        border-radius: 12px; padding: 0.65rem 1rem; margin-bottom: 1rem;
        border: 1px dashed rgba(148,163,184,0.35);
        background: rgba(15,23,42,0.5);
        font-size: 0.88rem; color: #94a3b8;
    }
</style>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="mp-admin-header">
  <div class="mp-admin-title">⚖️ Painel Administrativo Estratégico</div>
  <div class="mp-admin-sub">Visão consolidada do SaaS · CRM · financeiro executivo · gestão de acessos</div>
</div>
""",
        unsafe_allow_html=True,
    )

    _render_alertas_automaticos()

    k1, k2, k3, k4, k5 = st.columns(5)
    total_u = admin_count_usuarios()
    total_l = admin_count_leads()
    total_a = admin_count_analises()
    ativos = admin_count_usuarios_ativos_7d()
    receita = admin_receita_estimada_mensal_brl()

    with k1:
        st.markdown(
            f'<div class="mp-admin-kpi"><div class="lab">Usuários</div>'
            f'<div class="val">{total_u:,}</div></div>',
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f'<div class="mp-admin-kpi"><div class="lab">Leads</div>'
            f'<div class="val">{total_l:,}</div></div>',
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f'<div class="mp-admin-kpi"><div class="lab">Análises</div>'
            f'<div class="val">{total_a:,}</div></div>',
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f'<div class="mp-admin-kpi"><div class="lab">Ativos 7 dias</div>'
            f'<div class="val">{ativos:,}</div></div>',
            unsafe_allow_html=True,
        )
    with k5:
        st.markdown(
            f'<div class="mp-admin-kpi"><div class="lab">Receita estimada</div>'
            f'<div class="val">R$ {receita:,.0f}</div></div>',
            unsafe_allow_html=True,
        )

    st.caption(
        "Receita estimada = assinaturas ativas × tabela (FREE R$0 · PRO R$197 · PREMIUM R$397). "
        "Não substitui financeiro."
    )

    g1, g2 = st.columns(2)
    df_sig = _series_to_df_last_30(admin_series_cadastros_30_dias())
    df_lead = _series_to_df_last_30(admin_series_leads_30_dias())
    with g1:
        st.altair_chart(
            _chart_line(df_sig, "Cadastros (30 dias)", "#60a5fa"),
            use_container_width=True,
        )
    with g2:
        st.altair_chart(
            _chart_line(df_lead, "Leads (30 dias)", "#34d399"),
            use_container_width=True,
        )

    _render_funil_comercial()

    _render_financeiro_executivo()

    st.markdown("#### Últimos registros")
    t1, t2 = st.columns(2)
    with t1:
        st.markdown('<div class="mp-admin-block"><strong>Últimos usuários</strong></div>', unsafe_allow_html=True)
        rows_u = admin_ultimos_usuarios(15)
        df_u = pd.DataFrame(rows_u, columns=["id", "email", "cadastro_ref"])
        st.dataframe(df_u, use_container_width=True, hide_index=True)
    with t2:
        st.markdown('<div class="mp-admin-block"><strong>Últimos leads</strong></div>', unsafe_allow_html=True)
        rows_l = admin_ultimos_leads(15)
        df_l = pd.DataFrame(
            rows_l,
            columns=[
                "id",
                "nome",
                "empresa",
                "email",
                "whatsapp",
                "plano_interesse",
                "criado_em",
                "status",
            ],
        )
        st.dataframe(df_l, use_container_width=True, hide_index=True)

    st.markdown("#### Exportações CSV")
    e1, e2, e3 = st.columns(3)
    exp_u = admin_export_usuarios_rows()
    exp_l = admin_export_leads_rows()
    exp_a = admin_export_analises_rows()
    with e1:
        st.download_button(
            "Baixar usuários (CSV)",
            data=_csv_bytes(
                exp_u,
                ["id", "email", "bloqueado", "plano", "status_assinatura"],
            ),
            file_name="dpia_usuarios.csv",
            mime="text/csv",
            use_container_width=True,
            key="admin_dl_users",
        )
    with e2:
        st.download_button(
            "Baixar leads (CSV)",
            data=_csv_bytes(
                exp_l,
                [
                    "id",
                    "nome",
                    "empresa",
                    "whatsapp",
                    "email",
                    "plano_interesse",
                    "criado_em",
                    "origem",
                    "status",
                    "observacoes",
                    "atualizado_em",
                ],
            ),
            file_name="dpia_leads.csv",
            mime="text/csv",
            use_container_width=True,
            key="admin_dl_leads",
        )
    with e3:
        st.download_button(
            "Baixar análises (CSV)",
            data=_csv_bytes(
                exp_a,
                [
                    "id",
                    "empresa_id",
                    "empresa_nome",
                    "usuario_id",
                    "data_analise",
                    "tipo_caso",
                    "risco",
                    "pontuacao",
                    "versao_ia",
                ],
            ),
            file_name="dpia_analises.csv",
            mime="text/csv",
            use_container_width=True,
            key="admin_dl_analises",
        )

    _render_admin_gestao_acessos()


def _render_funil_comercial() -> None:
    st.markdown(
        """
<div class="mp-crm-wrap">
  <div class="mp-crm-title">Funil Comercial</div>
  <div class="mp-crm-sub">CRM interno · pipeline de leads da landing e demais origens</div>
</div>
""",
        unsafe_allow_html=True,
    )

    kp = admin_crm_kpis()
    z1, z2, z3, z4, z5 = st.columns(5)
    with z1:
        st.markdown(
            f'<div class="mp-crm-kpi"><div class="lab">Novos hoje</div>'
            f'<div class="val">{kp["novos_hoje"]:,}</div></div>',
            unsafe_allow_html=True,
        )
    with z2:
        st.markdown(
            f'<div class="mp-crm-kpi"><div class="lab">Em aberto</div>'
            f'<div class="val">{kp["em_aberto"]:,}</div></div>',
            unsafe_allow_html=True,
        )
    with z3:
        st.markdown(
            f'<div class="mp-crm-kpi"><div class="lab">Demos marcadas</div>'
            f'<div class="val">{kp["demos_marcadas"]:,}</div></div>',
            unsafe_allow_html=True,
        )
    with z4:
        st.markdown(
            f'<div class="mp-crm-kpi"><div class="lab">Fechados (mês)</div>'
            f'<div class="val">{kp["fechados_mes"]:,}</div></div>',
            unsafe_allow_html=True,
        )
    with z5:
        st.markdown(
            f'<div class="mp-crm-kpi"><div class="lab">Taxa conversão</div>'
            f'<div class="val">{kp["taxa_conversao"]:.1f}%</div></div>',
            unsafe_allow_html=True,
        )

    st.caption(
        "Taxa = fechados ÷ (fechados + perdidos) no mês atual, por data de atualização do status."
    )

    filtros_opt = ["(todos)"] + [f"{s} · {_crm_label_status(s)}" for s in LEAD_CRM_STATUSES]
    escolha = st.selectbox(
        "Filtrar por status",
        filtros_opt,
        key="crm_filtro_status_select",
    )
    filtro_sql = None
    if escolha != "(todos)":
        filtro_sql = escolha.split(" · ", 1)[0].strip()

    rows = admin_crm_listar_leads(filtro_sql)
    if not rows:
        st.info("Nenhum lead neste filtro.")
        return

    df = pd.DataFrame(
        rows,
        columns=[
            "id",
            "nome",
            "empresa",
            "whatsapp",
            "email",
            "plano_interesse",
            "criado_em",
            "origem",
            "status",
            "observacoes",
        ],
    )
    df["status_fmt"] = df["status"].map(_crm_label_status)
    show = df[
        [
            "id",
            "nome",
            "empresa",
            "whatsapp",
            "email",
            "plano_interesse",
            "criado_em",
            "origem",
            "status_fmt",
            "observacoes",
        ]
    ].rename(columns={"status_fmt": "status"})
    st.dataframe(show, use_container_width=True, hide_index=True)

    by_id = {r[0]: r for r in rows}
    ids_ord = list(by_id.keys())

    with st.form("crm_edit_form"):
        lid = st.selectbox(
            "Lead para atualizar",
            options=ids_ord,
            format_func=lambda i: (
                f"{i} · {by_id[i][1]} "
                f"({_crm_label_status(str(by_id[i][7] or 'novo'))})"
            ),
        )
        row = by_id[lid]
        st_cur = str(row[7] or "novo")
        idx_st = (
            list(LEAD_CRM_STATUSES).index(st_cur)
            if st_cur in LEAD_CRM_STATUSES
            else 0
        )
        novo_status = st.selectbox(
            "Status",
            options=list(LEAD_CRM_STATUSES),
            format_func=_crm_label_status,
            index=idx_st,
        )
        obs_txt = st.text_area(
            "Observações",
            value=str(row[8] or ""),
            height=120,
            placeholder="Notas internas da negociação…",
        )
        salvar = st.form_submit_button("Salvar alterações")

    if salvar:
        admin_crm_atualizar_lead(lid, status=novo_status, observacoes=obs_txt)
        st.success("Lead atualizado.")
        st.rerun()


def _render_admin_gestao_acessos() -> None:
    st.divider()
    st.markdown("#### Gestão de acessos")
    st.caption(
        "Bloqueio impede login. Assinatura **suspensa** também bloqueia o acesso à plataforma "
        "(dados preservados). O administrador master não pode ser bloqueado nem suspenso."
    )

    rows_all = admin_listar_usuarios_gestao()
    if not rows_all:
        st.info("Nenhum usuário cadastrado.")
        return

    overview = pd.DataFrame(
        rows_all,
        columns=["id", "email", "bloqueado", "plano", "status_assinatura"],
    )
    st.dataframe(overview, use_container_width=True, hide_index=True)

    by_id = {r[0]: r for r in rows_all}
    opts = list(by_id.keys())

    with st.form("admin_form_gestao"):
        sel_uid = st.selectbox(
            "Selecionar usuário",
            options=opts,
            format_func=lambda u: f"{u} · {by_id[u][1]}",
        )
        row = by_id[sel_uid]
        master_alvo = is_admin_master(row[1])

        c1, c2 = st.columns(2)
        with c1:
            bloquear = st.checkbox(
                "Bloquear usuário",
                value=bool(row[2]),
                disabled=master_alvo,
                help="Impede login enquanto ativo.",
            )
        with c2:
            idx_plano = (
                ["FREE", "PRO", "PREMIUM"].index(row[3])
                if row[3] in ("FREE", "PRO", "PREMIUM")
                else 0
            )
            plano = st.selectbox(
                "Plano",
                ["FREE", "PRO", "PREMIUM"],
                index=idx_plano,
            )
        idx_st = 1 if str(row[4] or "").lower() == "suspended" else 0
        status_a = st.selectbox(
            "Status da assinatura",
            ["active", "suspended"],
            index=idx_st,
            disabled=master_alvo,
            help="Suspenso: bloqueia uso da plataforma sem apagar conta.",
        )

        submitted = st.form_submit_button("Aplicar alterações")

    if submitted:
        if master_alvo and bloquear:
            st.error("Não é permitido bloquear o administrador master.")
            return
        if master_alvo and status_a == "suspended":
            st.error("Não é permitido suspender o administrador master.")
            return

        ok_b = admin_definir_bloqueio_usuario(sel_uid, 1 if bloquear else 0)
        if not ok_b:
            st.error("Não foi possível alterar o bloqueio (usuário protegido).")
            return

        ok_p = admin_definir_plano_e_status(sel_uid, plano, status_a)
        if not ok_p:
            st.error("Não foi possível aplicar plano/status (usuário protegido).")
            return

        st.success("Alterações aplicadas.")
        st.rerun()
