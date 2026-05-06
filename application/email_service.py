import os

import streamlit as st


def _enviar_email_html(destinatario: str, assunto: str, html_content: str) -> bool:
    app_env = str(os.getenv("APP_ENV", "")).strip().lower()
    if app_env == "development":
        st.info(f"MODO DEV: E-mail para {destinatario} com assunto '{assunto}'")
        with st.expander("Preview do e-mail (modo desenvolvimento)", expanded=False):
            st.markdown(html_content, unsafe_allow_html=True)
        return True

    try:
        api_key = st.secrets["sendgrid"]["api_key"]
    except Exception:
        return False

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        remetente = str(os.getenv("ALERT_FROM_EMAIL", "no-reply@mpconsultoria.com")).strip()
        mensagem = Mail(
            from_email=remetente,
            to_emails=str(destinatario).strip(),
            subject=str(assunto).strip(),
            html_content=html_content,
        )
        client = SendGridAPIClient(api_key)
        response = client.send(mensagem)
        return int(getattr(response, "status_code", 500)) < 400
    except Exception:
        return False


def montar_link_primeiro_acesso(token: str) -> str:
    base = str(os.getenv("APP_URL", "")).strip().rstrip("/")
    if not base:
        return f"?convite={token}"
    return f"{base}/?convite={token}"


def enviar_email_convite_primeiro_acesso(
    destinatario: str,
    nome_destinatario: str,
    empresa_nome: str,
    perfil: str,
    token: str,
) -> bool:
    nome = str(nome_destinatario or "").strip() or "Olá"
    link = montar_link_primeiro_acesso(token)
    assunto = f"[M&P] Convite para acessar {empresa_nome}"
    html = f"""
<h3>Convite para acesso à M&P Consultoria Trabalhista</h3>
<p>{nome}, você foi convidado(a) para a empresa <strong>{empresa_nome}</strong>.</p>
<p>Perfil de acesso: <strong>{perfil}</strong>.</p>
<p>Para definir sua senha no primeiro acesso, clique no link abaixo (válido por tempo limitado):</p>
<p><a href="{link}">{link}</a></p>
<p>Se você não esperava este convite, desconsidere este e-mail.</p>
"""
    return _enviar_email_html(destinatario, assunto, html)
