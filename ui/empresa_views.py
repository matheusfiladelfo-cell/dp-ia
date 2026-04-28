import streamlit as st
from ui.empty_states import render_empty_state_sem_empresa


def render_empresas_sidebar(empresas):
    st.sidebar.markdown("## 🏢 Empresas")

    if not empresas:
        render_empty_state_sem_empresa()

    empresa_nomes = [e[1] for e in empresas]
    empresa_map = {e[1]: e[0] for e in empresas}

    empresa_selecionada = st.sidebar.selectbox(
        "Selecionar empresa",
        empresa_nomes if empresa_nomes else ["--"],
    )

    empresa_id = empresa_map.get(empresa_selecionada)
    return empresa_selecionada, empresa_id


def render_nova_empresa_sidebar():
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ➕ Nova empresa")

    nome_empresa = st.sidebar.text_input("Nome")
    cnpj_empresa = st.sidebar.text_input("CNPJ")
    cidade_empresa = st.sidebar.text_input("Cidade")
    estado_empresa = st.sidebar.text_input("Estado")
    cadastrar_clicked = st.sidebar.button("Cadastrar empresa")

    return nome_empresa, cnpj_empresa, cidade_empresa, estado_empresa, cadastrar_clicked
