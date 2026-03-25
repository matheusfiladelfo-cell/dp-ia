import streamlit as st
import sqlite3
import pandas as pd

from banco import criar_tabelas

# ===============================
# INIT
# ===============================

criar_tabelas()

st.set_page_config(page_title="Dashboard DP-IA", layout="wide")

st.title("📊 Dashboard Inteligente de Risco Trabalhista")

# ===============================
# DADOS
# ===============================

def carregar_dados():
    conn = sqlite3.connect("dpia.db", check_same_thread=False)

    try:
        df = pd.read_sql_query("SELECT * FROM analises", conn)
    except:
        df = pd.DataFrame()

    conn.close()
    return df


df = carregar_dados()

if df.empty:
    st.warning("Nenhuma análise encontrada.")
    st.stop()

# ===============================
# TRATAMENTO CORRETO
# ===============================

# 🔥 converte corretamente a data
df["data"] = pd.to_datetime(df["data_analise"], errors="coerce")

# 🔥 remove dados inválidos
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
# GRÁFICO 1 — DISTRIBUIÇÃO
# ===============================

st.subheader("📌 Distribuição de risco")

distribuicao = df_filtrado["risco"].value_counts()

if distribuicao.empty:
    st.info("Sem dados para exibir distribuição.")
else:
    # 🔥 transforma em DataFrame (evita bug Altair)
    df_dist = distribuicao.reset_index()
    df_dist.columns = ["risco", "quantidade"]

    st.bar_chart(df_dist.set_index("risco"))

# ===============================
# GRÁFICO 2 — EVOLUÇÃO
# ===============================

st.subheader("📈 Evolução no tempo")

df_evolucao = df_filtrado.groupby("data").size()

if df_evolucao.empty:
    st.info("Sem dados suficientes para exibir evolução.")
else:
    # 🔥 garante formato correto
    df_evolucao = df_evolucao.reset_index()
    df_evolucao.columns = ["data", "quantidade"]

    df_evolucao = df_evolucao.set_index("data")

    st.line_chart(df_evolucao)

# ===============================
# HISTÓRICO
# ===============================

st.subheader("📋 Histórico de análises")

st.dataframe(df_filtrado.sort_values("data", ascending=False))