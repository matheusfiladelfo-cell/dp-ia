import streamlit as st

from banco import cadastrar_empresa, listar_empresas


def listar_empresas_usuario(usuario_id):
    return listar_empresas(usuario_id)


def selecionar_empresa(empresa_id):
    st.session_state.empresa_id = empresa_id
    return empresa_id


def cadastrar_empresa_usuario(usuario_id, nome, cnpj, cidade, estado):
    cadastrar_empresa(
        usuario_id,
        nome,
        cnpj,
        cidade,
        estado,
    )
