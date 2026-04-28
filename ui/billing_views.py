import streamlit as st


def traduzir_erro_checkout(error_text):
    texto = str(error_text or "").lower()

    if any(k in texto for k in ["timeout", "connection", "conex", "network"]):
        return "Não conseguimos conectar ao provedor agora. Verifique sua internet e tente novamente."

    if any(k in texto for k in ["503", "502", "unavailable", "indispon", "service"]):
        return "O provedor de pagamento está indisponível no momento. Tente novamente em instantes."

    if any(k in texto for k in ["400", "invalid", "inválid", "inval", "dados", "email"]):
        return "Alguns dados de cobrança parecem inválidos. Revise os dados da conta e tente novamente."

    return "Não foi possível gerar o checkout neste momento. Tente novamente."


def render_checkout_success(plano_destino, checkout_url, sandbox=False):
    st.success("Checkout criado com sucesso. Continue o pagamento.")

    if sandbox:
        st.markdown(
            """
<div style="
display:inline-block;
padding:6px 10px;
border-radius:999px;
background:#fef3c7;
border:1px solid #f59e0b;
color:#92400e;
font-size:0.78rem;
font-weight:800;
letter-spacing:0.04em;
margin-top:6px;
margin-bottom:10px;
">
AMBIENTE DE TESTE
</div>
""",
            unsafe_allow_html=True,
        )

    st.link_button(
        f"🔗 Abrir checkout {plano_destino}",
        checkout_url,
        width="stretch",
    )

    st.markdown(
        """
<div style="
margin-top:10px;
padding:12px 14px;
border-radius:12px;
border:1px solid #dbeafe;
background:#f8fbff;
">
<strong>Próximos passos</strong><br/>
1) Abra o checkout no botão acima.<br/>
2) Conclua o pagamento no provedor.<br/>
3) Volte ao DP-IA: seu plano será atualizado após confirmação.
</div>
""",
        unsafe_allow_html=True,
    )
