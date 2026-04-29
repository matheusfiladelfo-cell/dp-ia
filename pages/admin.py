import streamlit as st

from banco import criar_tabelas, obter_email_usuario
from ui.admin_views import is_admin_master, render_admin_access_denied, render_admin_dashboard
from ui.theme import apply_global_theme

criar_tabelas()

st.set_page_config(
    page_title="M&P | Painel Administrativo",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_theme()

if "user_id" not in st.session_state:
    st.warning("Faça login no aplicativo principal para acessar esta página.")
    st.stop()

email = obter_email_usuario(st.session_state["user_id"])

if not is_admin_master(email):
    render_admin_access_denied()
    st.stop()

render_admin_dashboard()
