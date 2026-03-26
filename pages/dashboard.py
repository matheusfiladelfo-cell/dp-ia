import streamlit as st
import sqlite3
import pandas as pd

from banco import criar_tabelas, listar_empresas

# ===============================
# INIT
# ===============================

criar_tabelas()

st.set_page_config(page_title="Dashboard DP-IA", layout="wide")

st.title("📊 Dashboard Inteligente de Risco Trabalhista")

# ===============================
# USUÁRIO
# ===============================

usuario_id = st.session_state.get("user_id")

if not usuario_id:
    st.warning("Faça login primeiro")
    st.stop()

# ===============================
# EMPRESA (🔥 AGORA FUNCIONA SEM APP)
# ===============================

st.sidebar.header("🏢 Empresa")

empresas = listar_empresas(usuario_id)

if not empresas:
    st.warning("Nenhuma empresa cadastrada")
    st.stop()

empresa_nomes = [e[1] for e in empresas]
empresa_map = {e[1]: e[0] for e in empresas}

empresa_selecionada = st.sidebar.selectbox(
    "Selecionar empresa",
    empresa_nomes
)

empresa_id = empresa_map.get(empresa_selecionada)

# ===============================
# DADOS
# ===============================

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
    st.warning("Nenhuma análise encontrada para esta empresa.")
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

# ===============================
# KPIs
# ===============================

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total análises", len(df_filtrado))
col2.metric("🔴 Alto risco", (df_filtrado["risco"] == "ALTO").sum())
col3.metric("🟠 Médio risco", (df_filtrado["risco"] == "MÉDIO").sum())
col4.metric("🟢 Baixo risco", (df_filtrado["risco"] == "BAIXO").sum())

st.markdown("---")

# ===============================
# DISTRIBUIÇÃO
# ===============================

st.subheader("📌 Distribuição de risco")

distribuicao = df_filtrado["risco"].value_counts()

if distribuicao.empty:
    st.info("Sem dados para exibir distribuição.")
else:
    df_dist = distribuicao.reset_index()
    df_dist.columns = ["risco", "quantidade"]

    st.bar_chart(df_dist.set_index("risco"))

# ===============================
# EVOLUÇÃO
# ===============================

st.subheader("📈 Evolução no tempo")

df_evolucao = df_filtrado.groupby("data").size()

if df_evolucao.empty:
    st.info("Sem dados suficientes para exibir evolução.")
else:
    df_evolucao = df_evolucao.reset_index()
    df_evolucao.columns = ["data", "quantidade"]
    df_evolucao = df_evolucao.set_index("data")

    st.line_chart(df_evolucao)

# ===============================
# HISTÓRICO
# ===============================

st.subheader("📋 Histórico de análises")

st.dataframe(df_filtrado.sort_values("data", ascending=False))