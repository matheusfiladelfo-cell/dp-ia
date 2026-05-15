import streamlit as st

from banco import EMAIL_JA_CADASTRADO_MSG, criar_usuario, login_usuario


def processar_login(email, senha):
    user_id = login_usuario(email, senha)
    if user_id:
        st.session_state.user_id = user_id
        st.rerun()
    return False


def processar_cadastro(email, senha):
    """
    Retorna True se a conta foi criada.
    Retorna "duplicate" se o e-mail já existe.
    Retorna False em outros erros.
    """
    try:
        criar_usuario(email, senha)
        return True
    except ValueError as exc:
        if str(exc).strip() == EMAIL_JA_CADASTRADO_MSG:
            return "duplicate"
        return False
    except Exception:
        return False


def processar_logout():
    st.session_state.pop("user_id", None)
    st.session_state.pop("perfil_usuario", None)
    st.session_state.pop("empresa_id", None)
    st.session_state.pop("area_principal_mp", None)
    st.rerun()
