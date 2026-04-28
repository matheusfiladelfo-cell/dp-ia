import streamlit as st
import sqlite3
import pandas as pd
import altair as alt
import json

from banco import criar_tabelas, listar_empresas
from plano_service import get_plano_usuario
from ui.theme import apply_global_theme
from ui.empty_states import (
    render_empty_state_sem_empresa,
    render_empty_state_sem_analises,
    render_empty_state_sem_historico,
)

# ===============================
# INIT
# ===============================

criar_tabelas()

st.set_page_config(page_title="Dashboard DP-IA", layout="wide")
apply_global_theme()

st.markdown(
    """
<style>
    .mp-header {
        padding: 1.2rem 1.35rem;
        border-radius: 16px;
        background: linear-gradient(140deg, rgba(15,23,42,0.94), rgba(30,64,175,0.34));
        border: 1px solid rgba(212,175,55,0.26);
        box-shadow: 0 0 0 1px rgba(59,130,246,0.10), 0 18px 42px rgba(2,6,23,0.50), 0 0 40px rgba(59,130,246,0.16);
        color: #f8fafc;
        margin-bottom: 0.85rem;
    }
    .mp-title { margin: 0; font-size: 1.4rem; font-weight: 800; }
    .mp-sub { margin-top: 0.3rem; color: #cbd5e1; }
    .mp-kpi {
        border: 1px solid rgba(148,163,184,0.24);
        border-radius: 14px;
        background: rgba(15,23,42,0.78);
        padding: 0.75rem 0.8rem;
        transition: transform 0.18s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }
    .mp-kpi:hover {
        transform: translateY(-2px);
        border-color: rgba(96,165,250,0.40);
        box-shadow: 0 12px 26px rgba(2,6,23,0.34), 0 0 18px rgba(59,130,246,0.14);
    }
    .mp-right {
        border: 1px solid rgba(96,165,250,0.34);
        border-radius: 14px;
        background: linear-gradient(145deg, rgba(15,23,42,0.88), rgba(30,64,175,0.22));
        padding: 0.9rem;
        color: #e2e8f0;
    }
    .mp-summary {
        border: 1px solid rgba(148,163,184,0.24);
        border-radius: 14px;
        background: rgba(15,23,42,0.78);
        padding: 0.9rem 1rem;
        color: #e2e8f0;
        margin-top: 0.6rem;
    }
    .mp-summary ul {
        margin: 0.45rem 0 0 1rem;
        color: #cbd5e1;
    }
    .mp-section-title {
        margin-top: 0.55rem;
        margin-bottom: 0.3rem;
        color: #e2e8f0;
        font-weight: 700;
        letter-spacing: 0.01em;
    }
</style>
""",
    unsafe_allow_html=True,
)

top_cta_1, top_cta_2, _ = st.columns([1, 1, 3])
with top_cta_1:
    if st.button("🧾 Nova análise", width="stretch"):
        st.switch_page("app.py")
with top_cta_2:
    if st.button("🚀 Ver upgrade", width="stretch"):
        st.switch_page("app.py")

st.markdown(
    """
<div class="mp-header">
  <div style="font-size:0.85rem; color:#93c5fd; font-weight:700;">⚖️ M&P Consultoria Trabalhista</div>
  <h2 class="mp-title">Painel Estratégico Empresarial</h2>
  <div class="mp-sub">Risco trabalhista em tempo real para tomada de decisão.</div>
</div>
""",
    unsafe_allow_html=True,
)

# ===============================
# USUÁRIO
# ===============================

usuario_id = st.session_state.get("user_id")

if not usuario_id:
    st.warning("Faça login para acessar o Dashboard Executivo.")
    st.stop()

# ===============================
# EMPRESA (🔥 AGORA FUNCIONA SEM APP)
# ===============================

st.sidebar.header("🏢 Empresa")

empresas = listar_empresas(usuario_id)

if not empresas:
    render_empty_state_sem_empresa()
    st.stop()

empresa_nomes = [e[1] for e in empresas]
empresa_map = {e[1]: e[0] for e in empresas}

empresa_selecionada = st.sidebar.selectbox(
    "Selecionar empresa",
    empresa_nomes
)

empresa_id = empresa_map.get(empresa_selecionada)
plano_atual = get_plano_usuario(usuario_id)
plano_display = {"FREE": "Starter", "PRO": "Pro", "PREMIUM": "Business"}.get(str(plano_atual).upper(), str(plano_atual))

# ===============================
# DADOS
# ===============================

with st.spinner("Carregando dados..."):
    conn = sqlite3.connect("dpia.db", check_same_thread=False)
    df = pd.read_sql_query(
        """
        SELECT * FROM analises
        WHERE empresa_id = ?
        """,
        conn,
        params=(empresa_id,)
    )
    conn.close()

# ===============================
# SEM DADOS
# ===============================

if df.empty:
    render_empty_state_sem_analises()
    st.stop()

# ===============================
# NORMALIZAÇÃO
# ===============================

df["risco"] = df["risco"].astype(str).str.upper()

df["data"] = pd.to_datetime(df["data_analise"], errors="coerce")
df = df.dropna(subset=["data"])

# ===============================
# FILTROS
# ===============================

st.sidebar.header("🔎 Filtros")

risco_filtro = st.sidebar.multiselect(
    "Risco",
    df["risco"].dropna().unique(),
    default=df["risco"].dropna().unique()
)

data_inicio = st.sidebar.date_input("Data início", df["data"].min())
data_fim = st.sidebar.date_input("Data fim", df["data"].max())

df_filtrado = df[
    (df["risco"].isin(risco_filtro)) &
    (df["data"] >= pd.to_datetime(data_inicio)) &
    (df["data"] <= pd.to_datetime(data_fim))
]

total_analises = len(df_filtrado)
total_alto = (df_filtrado["risco"] == "ALTO").sum()
total_medio = (df_filtrado["risco"] == "MÉDIO").sum()
total_baixo = (df_filtrado["risco"] == "BAIXO").sum()
percentual_alto = round((total_alto / total_analises) * 100, 1) if total_analises else 0.0
criticidade = (
    "ALTA" if percentual_alto >= 40 else "MODERADA" if percentual_alto >= 20 else "CONTROLADA"
)
risk_score_map = {"ALTO": 3, "MÉDIO": 2, "MEDIO": 2, "BAIXO": 1}
risco_medio_num = (
    df_filtrado["risco"].map(risk_score_map).dropna().mean() if not df_filtrado.empty else 0
)
if risco_medio_num >= 2.5:
    risco_medio_txt = "ALTO"
elif risco_medio_num >= 1.7:
    risco_medio_txt = "MÉDIO"
else:
    risco_medio_txt = "BAIXO"

hoje = pd.Timestamp.now().normalize()
inicio_30 = hoje - pd.Timedelta(days=30)
inicio_60 = hoje - pd.Timedelta(days=60)
casos_30 = len(df_filtrado[df_filtrado["data"] >= inicio_30])
casos_30_prev = len(df_filtrado[(df_filtrado["data"] >= inicio_60) & (df_filtrado["data"] < inicio_30)])
delta_30 = casos_30 - casos_30_prev
tendencia_30 = f"{'+' if delta_30 > 0 else ''}{delta_30} casos"

exposicao_financeira = 0.0
if "parecer_json" in df_filtrado.columns:
    for raw in df_filtrado["parecer_json"].dropna():
        try:
            payload = raw if isinstance(raw, dict) else json.loads(str(raw))
            exposicao_financeira += float(payload.get("impacto_financeiro", 0) or 0)
        except Exception:
            pass

# ===============================
# KPIs + LADO DIREITO
# ===============================

with st.spinner("Preparando dashboard..."):
    col_main, col_right = st.columns([2.2, 1])
with col_main:
    st.markdown('<div class="mp-section-title">Indicadores Estratégicos</div>', unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown('<div class="mp-kpi">', unsafe_allow_html=True)
        st.metric("⚖️ Risco Médio Atual", risco_medio_txt)
        st.caption("Tendência: " + ("↗ atenção" if risco_medio_txt == "ALTO" else "→ estável" if risco_medio_txt == "MÉDIO" else "↘ controlado"))
        st.markdown("</div>", unsafe_allow_html=True)
    with k2:
        st.markdown('<div class="mp-kpi">', unsafe_allow_html=True)
        st.metric("📁 Casos Analisados", total_analises)
        st.caption("Janela filtrada")
        st.markdown("</div>", unsafe_allow_html=True)
    with k3:
        st.markdown('<div class="mp-kpi">', unsafe_allow_html=True)
        st.metric("💰 Exposição Financeira", f"R$ {exposicao_financeira:,.0f}")
        st.caption("Soma dos pareceres")
        st.markdown("</div>", unsafe_allow_html=True)
    with k4:
        st.markdown('<div class="mp-kpi">', unsafe_allow_html=True)
        st.metric("📈 Tendência 30 dias", tendencia_30, f"{casos_30} no período")
        st.caption("Comparativo com 30 dias anteriores")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        f"""
<div class="mp-summary">
  <strong>Resumo Estratégico da IA</strong>
  <ul>
    <li>Criticidade atual: <b>{criticidade}</b>, com {percentual_alto}% dos casos em risco alto.</li>
    <li>Exposição financeira consolidada estimada em <b>R$ {exposicao_financeira:,.0f}</b>.</li>
    <li>Tendência de 30 dias: <b>{tendencia_30}</b>, sugerindo {'aceleração' if delta_30 > 0 else 'estabilidade/redução'} de demanda trabalhista.</li>
  </ul>
</div>
""",
        unsafe_allow_html=True,
    )
with col_right:
    st.markdown('<div class="mp-right">', unsafe_allow_html=True)
    st.markdown("**Plano atual**")
    st.markdown(f"### {plano_display}")
    st.caption("Trial: 7 dias grátis ou 3 análises grátis.")
    st.caption(f"Empresa selecionada: {empresa_selecionada}")
    if st.button("🚀 Upgrade Pro/Business", width="stretch"):
        st.switch_page("app.py")
    st.markdown("</div>", unsafe_allow_html=True)

# ===============================
# GRÁFICOS
# ===============================

st.markdown('<div class="mp-section-title">Distribuição de casos</div>', unsafe_allow_html=True)

distribuicao = df_filtrado["risco"].value_counts()

if distribuicao.empty:
    render_empty_state_sem_historico()
else:
    df_dist = distribuicao.reset_index()
    df_dist.columns = ["risco", "quantidade"]
    ordem_risco = ["ALTO", "MÉDIO", "BAIXO"]
    df_dist["risco"] = pd.Categorical(df_dist["risco"], categories=ordem_risco, ordered=True)
    df_dist = df_dist.sort_values("risco")

    cores_risco = alt.Scale(
        domain=["ALTO", "MÉDIO", "BAIXO"],
        range=["#dc2626", "#f59e0b", "#16a34a"],
    )

    grafico_dist = (
        alt.Chart(df_dist)
        .mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8)
        .encode(
            x=alt.X("risco:N", title="Nível de risco"),
            y=alt.Y("quantidade:Q", title="Quantidade"),
            color=alt.Color("risco:N", scale=cores_risco, legend=None),
            tooltip=["risco:N", "quantidade:Q"],
        )
        .properties(height=270)
    )
    st.altair_chart(grafico_dist, width="stretch")

# ===============================
# EVOLUÇÃO
# ===============================

st.markdown('<div class="mp-section-title">Evolução de risco</div>', unsafe_allow_html=True)

df_risco = df_filtrado.copy()
df_risco["score_risco"] = df_risco["risco"].map({"ALTO": 3, "MÉDIO": 2, "MEDIO": 2, "BAIXO": 1}).fillna(1)
df_evolucao = df_risco.groupby("data", as_index=False)["score_risco"].mean()

if df_evolucao.empty:
    render_empty_state_sem_historico()
else:
    grafico_linha = (
        alt.Chart(df_evolucao)
        .mark_line(point=alt.OverlayMarkDef(size=65, color="#60a5fa"), strokeWidth=3, color="#60a5fa")
        .encode(
            x=alt.X("data:T", title="Data"),
            y=alt.Y("score_risco:Q", title="Índice de risco (1-3)"),
            tooltip=["data:T", "score_risco:Q"],
        )
        .properties(height=270)
    )
    st.altair_chart(grafico_linha, width="stretch")

st.markdown('<div class="mp-section-title">Tendência mensal</div>', unsafe_allow_html=True)
df_tend = df_filtrado.copy()
df_tend["mes"] = df_tend["data"].dt.to_period("M").astype(str)
df_tend = df_tend.groupby("mes", as_index=False).size().rename(columns={"size": "casos"})
if df_tend.empty:
    render_empty_state_sem_historico()
else:
    grafico_tend = (
        alt.Chart(df_tend)
        .mark_area(line={"color": "#3b82f6"}, color=alt.Gradient(
            gradient="linear",
            stops=[alt.GradientStop(color="#1d4ed8", offset=0), alt.GradientStop(color="#1d4ed8", offset=1)],
            x1=1, x2=1, y1=1, y2=0
        ), opacity=0.30)
        .encode(
            x=alt.X("mes:N", title="Mês"),
            y=alt.Y("casos:Q", title="Casos"),
            tooltip=["mes:N", "casos:Q"],
        )
        .properties(height=250)
    )
    st.altair_chart(grafico_tend, width="stretch")

# ===============================
# HISTÓRICO
# ===============================

st.markdown('<div class="mp-section-title">Últimos casos analisados</div>', unsafe_allow_html=True)
df_historico = df_filtrado.sort_values("data", ascending=False).copy()
colunas_visao = [
    c for c in ["data_analise", "tipo_caso", "risco", "pontuacao", "versao_ia"] if c in df_historico.columns
]
if colunas_visao:
    st.dataframe(
        df_historico[colunas_visao],
        width="stretch",
        hide_index=True,
    )
else:
    if df_historico.empty:
        render_empty_state_sem_historico()
    else:
        st.dataframe(df_historico, width="stretch", hide_index=True)