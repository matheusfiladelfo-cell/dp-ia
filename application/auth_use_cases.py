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
    del st.session_state["user_id"]
    st.rerun()
