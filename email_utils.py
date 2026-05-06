"""
Envio de e-mail para fluxo de redefinição de senha (SendGrid no Render).
Fora do Render: apenas registra o link no stdout para desenvolvimento local.
"""

from __future__ import annotations

import os
from urllib.parse import quote

import streamlit as st


def _is_render_service() -> bool:
    return str(os.getenv("RENDER", "")).strip().lower() in {"1", "true", "yes"}


def montar_link_reset_senha(token: str) -> str:
    """URL absoluta com query params page=reset_password e token."""
    base = str(os.getenv("APP_URL", "")).strip().rstrip("/")
    tok = quote(str(token or "").strip(), safe="")
    if base:
        return f"{base}/?page=reset_password&token={tok}"
    return f"/?page=reset_password&token={tok}"


def enviar_email_reset_senha(email_destino: str, token: str) -> bool:
    """
    Envia e-mail HTML com link de redefinição.
    Fora do Render: não envia — imprime o link no terminal (stdout).
    """
    destinatario = str(email_destino or "").strip()
    link = montar_link_reset_senha(token)

    if not _is_render_service():
        print(f"[reset_password] destinatario={destinatario} link={link}", flush=True)
        return True

    try:
        api_key = st.secrets["sendgrid"]["api_key"]
    except Exception:
        return False

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        remetente = str(os.getenv("ALERT_FROM_EMAIL", "no-reply@mpconsultoria.com")).strip()
        assunto = "[M&P] Redefinição de senha"
        html = f"""
<h3>Redefinição de senha — M&amp;P Consultoria Trabalhista</h3>
<p>Você solicitou redefinir sua senha. Clique no link abaixo (válido por tempo limitado):</p>
<p><a href="{link}">{link}</a></p>
<p>Se você não fez este pedido, ignore este e-mail.</p>
"""
        mensagem = Mail(
            from_email=remetente,
            to_emails=destinatario,
            subject=assunto,
            html_content=html,
        )
        client = SendGridAPIClient(api_key)
        response = client.send(mensagem)
        return int(getattr(response, "status_code", 500)) < 400
    except Exception:
        return False
