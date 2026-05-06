import streamlit as st


def carregar_css_customizado(css_path: str = "style.css"):
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except OSError:
        # Fail-soft: não interrompe a aplicação se o CSS não estiver disponível.
        pass
