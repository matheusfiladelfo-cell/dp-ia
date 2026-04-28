import streamlit as st


def _nome_comercial_plano(plano):
    return {
        "FREE": "Starter",
        "PRO": "Pro",
        "PREMIUM": "Business",
    }.get(str(plano).upper(), str(plano))


def render_usage(plano, uso, limite):
    col1, col2 = st.columns([1, 1.4])
    with col1:
        st.metric("Plano Atual", _nome_comercial_plano(plano))
    with col2:
        st.metric("Uso do Período", f"{uso} / {limite}")
