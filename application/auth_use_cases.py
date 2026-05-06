import streamlit as st

from banco import criar_usuario, login_usuario


def processar_login(email, senha):
    user_id = login_usuario(email, senha)
    if user_id:
        st.session_state.user_id = user_id
        st.rerun()
    return False


def processar_cadastro(email, senha):
    try:
        criar_usuario(email, senha)
        return True
    except Exception:
        return False


def processar_logout():
    st.session_state.pop("user_id", None)
    st.session_state.pop("perfil_usuario", None)
    st.session_state.pop("empresa_id", None)
    st.session_state.pop("area_principal_mp", None)
    st.rerun()
