import streamlit as st
from memoria_sessao import MemoriaSessao


def get_sessao():

    if "sessao_dp_ia" not in st.session_state:
        st.session_state.sessao_dp_ia = MemoriaSessao()

    return st.session_state.sessao_dp_ia


def resetar_sessao():
    st.session_state.sessao_dp_ia = MemoriaSessao()