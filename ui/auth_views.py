import streamlit as st


def render_auth_view(default_tab="Entrar", banner_text=None, is_processing=False):
    st.markdown(
        """
<style>
.mp-auth-wrap {
    margin: 1.8rem auto 1rem auto;
}
.mp-auth-brand {
    text-align: center;
    margin-bottom: 1.1rem;
}
.mp-auth-brand h1 {
    margin: 0;
    font-size: 2.05rem;
    color: #e2e8f0;
    letter-spacing: 0.01em;
}
.mp-auth-brand p {
    margin: 0.4rem 0 0 0;
    color: #a5b4fc;
    font-size: 1rem;
}
.mp-auth-card {
    background: linear-gradient(160deg, #0b1220 0%, #111827 55%, #0f172a 100%);
    border: 1px solid rgba(96, 165, 250, 0.35);
    border-radius: 20px;
    padding: 1.2rem 1.2rem 1rem 1.2rem;
    box-shadow:
        0 0 0 1px rgba(59,130,246,0.10),
        0 20px 45px rgba(2,6,23,0.58),
        0 0 40px rgba(59,130,246,0.18);
}
.mp-auth-card .stRadio > div {
    background: rgba(15, 23, 42, 0.62);
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: 12px;
    padding: 0.45rem 0.6rem;
}
.mp-auth-card .stTextInput > div > div > input {
    border-radius: 12px !important;
    min-height: 46px;
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(148, 163, 184, 0.25);
    color: #e2e8f0;
}
.mp-auth-card .stButton > button {
    min-height: 52px;
    border-radius: 12px;
    font-weight: 700;
    font-size: 1rem;
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    border: 1px solid rgba(147, 197, 253, 0.45);
}
.mp-auth-footer {
    text-align: center;
    margin-top: 1rem;
    color: #94a3b8;
    font-size: 0.86rem;
}
@media (max-width: 768px) {
    .mp-auth-wrap { margin-top: 1rem; }
    .mp-auth-brand h1 { font-size: 1.6rem; }
    .mp-auth-brand p { font-size: 0.92rem; }
}
</style>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="mp-auth-wrap">', unsafe_allow_html=True)
    st.markdown(
        """
<div class="mp-auth-brand">
  <h1>⚖️ M&P Consultoria Trabalhista</h1>
  <p>Decisão estratégica trabalhista para empresários.</p>
</div>
""",
        unsafe_allow_html=True,
    )

    col_l, col_c, col_r = st.columns([1, 1.25, 1])
    with col_c:
        st.markdown('<div class="mp-auth-card">', unsafe_allow_html=True)
        if banner_text:
            st.info(banner_text)

        opcoes = ["Entrar", "Criar conta"]
        indice = 0 if default_tab == "Entrar" else 1
        aba = st.radio(
            "Acesso",
            opcoes,
            index=indice,
            key="auth_tab",
            horizontal=True,
            label_visibility="collapsed",
        )
        email = st.text_input("Email corporativo", key="auth_email", placeholder="voce@empresa.com")
        senha = st.text_input("Senha", type="password", key="auth_password", placeholder="Digite sua senha")

        if aba == "Entrar":
            acao_clicada = st.button(
                "Entrar na Plataforma →",
                disabled=is_processing,
                key="auth_btn_login",
                width="stretch",
                type="primary",
            )
        else:
            acao_clicada = st.button(
                "Criar conta",
                disabled=is_processing,
                key="auth_btn_signup",
                width="stretch",
                type="primary",
            )

        if is_processing:
            st.caption("Processando...")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
<div class="mp-auth-footer">
Mais segurança jurídica. Menos decisões erradas.
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    return aba, email, senha, acao_clicada
