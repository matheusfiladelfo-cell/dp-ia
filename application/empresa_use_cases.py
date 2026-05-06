import streamlit as st

from banco import adicionar_ou_atualizar_membro_empresa, cadastrar_empresa, listar_empresas


def listar_empresas_usuario(usuario_id):
    return listar_empresas(usuario_id)


def selecionar_empresa(empresa_id):
    st.session_state.empresa_id = empresa_id
    return empresa_id


def cadastrar_empresa_usuario(usuario_id, nome, cnpj, cidade, estado):
    empresa_id = cadastrar_empresa(
        usuario_id,
        nome,
        cnpj,
        cidade,
        estado,
    )
    adicionar_ou_atualizar_membro_empresa(int(empresa_id), int(usuario_id), "admin")
