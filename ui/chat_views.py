import streamlit as st


def render_chat_title():
    st.subheader("💬 Consultor Trabalhista")


def render_chat_input():
    return st.chat_input("Digite sua dúvida...")


def render_chat_historico(historico):
    for msg in historico:
        with st.chat_message(msg["role"]):
            st.write(msg["texto"])
