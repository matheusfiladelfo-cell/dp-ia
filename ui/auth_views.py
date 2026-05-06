import re

import streamlit as st

_MP_AUTH_CSS = """
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
"""


def _inject_auth_styles():
    st.markdown(_MP_AUTH_CSS, unsafe_allow_html=True)


def _email_ok(s: str | None) -> bool:
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", str(s or "").strip()))


def render_auth_view(default_tab="Entrar", banner_text=None, is_processing=False):
    _inject_auth_styles()

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
            _, col_f = st.columns([2, 1])
            with col_f:
                if st.button("Esqueceu sua senha?", key="auth_forgot_pw"):
                    st.session_state["auth_view_mode"] = "forgot_password"
                    st.rerun()

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


def render_esqueci_senha_view():
    """Tela de solicitação de link de redefinição de senha."""
    from banco import gerar_token_reset_senha
    from email_utils import enviar_email_reset_senha

    _inject_auth_styles()

    st.markdown('<div class="mp-auth-wrap">', unsafe_allow_html=True)
    st.markdown(
        """
<div class="mp-auth-brand">
  <h1>⚖️ M&P Consultoria Trabalhista</h1>
  <p>Redefinição de senha</p>
</div>
""",
        unsafe_allow_html=True,
    )

    col_l, col_c, col_r = st.columns([1, 1.25, 1])
    with col_c:
        st.markdown('<div class="mp-auth-card">', unsafe_allow_html=True)
        st.markdown("#### Esqueci minha senha")
        st.caption("Informe o e-mail da sua conta. Se ele estiver cadastrado, você receberá um link para criar uma nova senha.")

        email_reset = st.text_input(
            "E-mail",
            key="forgot_password_email",
            placeholder="voce@empresa.com",
        )
        enviar = st.button("Enviar link de redefinição", key="forgot_password_submit", type="primary", width="stretch")

        if enviar:
            if not _email_ok(email_reset):
                st.warning("Digite um e-mail válido.")
            else:
                em = str(email_reset).strip()
                token = gerar_token_reset_senha(em)
                if token:
                    enviar_email_reset_senha(em, token)
                st.success(
                    "Se um usuário com este e-mail existir, um link de redefinição foi enviado."
                )

        if st.button("← Voltar ao login", key="forgot_password_back"):
            st.session_state.pop("auth_view_mode", None)
            st.rerun()

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


def render_reset_password_view(token: str):
    """Tela de nova senha a partir do token na URL."""
    from banco import validar_token_e_resetar_senha

    _inject_auth_styles()

    st.markdown('<div class="mp-auth-wrap">', unsafe_allow_html=True)
    st.markdown(
        """
<div class="mp-auth-brand">
  <h1>⚖️ M&P Consultoria Trabalhista</h1>
  <p>Nova senha</p>
</div>
""",
        unsafe_allow_html=True,
    )

    col_l, col_c, col_r = st.columns([1, 1.25, 1])
    with col_c:
        st.markdown('<div class="mp-auth-card">', unsafe_allow_html=True)
        st.markdown("#### Redefinir senha")

        nova = st.text_input("Nova senha", type="password", key="reset_pw_new", placeholder="Mínimo de 8 caracteres")
        conf = st.text_input(
            "Confirmar nova senha",
            type="password",
            key="reset_pw_confirm",
            placeholder="Repita a nova senha",
        )
        salvar = st.button("Salvar nova senha", key="reset_pw_submit", type="primary", width="stretch")

        if salvar:
            if len(str(nova or "")) < 8:
                st.error("A senha deve ter pelo menos 8 caracteres.")
            elif nova != conf:
                st.error("As senhas não conferem.")
            else:
                ok, msg = validar_token_e_resetar_senha(str(token or "").strip(), nova)
                if ok:
                    st.query_params.clear()
                    st.success(msg)
                    st.info("Agora faça login com seu e-mail e a nova senha.")
                else:
                    st.error(msg)

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


def render_primeiro_acesso_view(email_convite: str):
    st.markdown("### Primeiro acesso")
    st.caption(f"Convite para: **{email_convite}**")
    with st.form("primeiro_acesso_form", clear_on_submit=False):
        nova_senha = st.text_input(
            "Defina sua senha",
            type="password",
            placeholder="Mínimo de 8 caracteres",
        )
        confirmar = st.text_input(
            "Confirme sua senha",
            type="password",
            placeholder="Repita a senha",
        )
        enviar = st.form_submit_button("Salvar senha e continuar", type="primary")
    return nova_senha, confirmar, enviar
