import streamlit as st
import base64
import hashlib
import hmac
import os
import struct
import time

from banco import criar_tabelas, obter_email_usuario, registrar_admin_audit
from ui.admin_views import is_admin_master, render_admin_access_denied, render_admin_dashboard
from ui.theme import apply_global_theme

criar_tabelas()

st.set_page_config(
    page_title="M&P | Painel Administrativo",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_theme()


def _totp_valid(code: str, secret_b32: str, step_seconds: int = 30, drift_steps: int = 1) -> bool:
    c = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(c) != 6:
        return False
    try:
        key = base64.b32decode(secret_b32.strip().upper(), casefold=True)
    except Exception:
        return False
    now_counter = int(time.time() // step_seconds)
    for delta in range(-drift_steps, drift_steps + 1):
        counter = now_counter + delta
        msg = struct.pack(">Q", counter)
        digest = hmac.new(key, msg, hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        binary = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
        expected = str(binary % 1000000).zfill(6)
        if hmac.compare_digest(expected, c):
            return True
    return False


def _admin_mfa_enabled() -> bool:
    return bool(str(os.getenv("ADMIN_MFA_TOTP_SECRET", "")).strip() or str(os.getenv("ADMIN_MFA_CODE", "")).strip())

if "user_id" not in st.session_state:
    st.warning("Faça login no aplicativo principal para acessar esta página.")
    st.stop()

user_id = int(st.session_state["user_id"])
email = obter_email_usuario(user_id)

if not is_admin_master(email, user_id):
    registrar_admin_audit(
        admin_user_id=user_id,
        action="admin_access_denied",
        target_type="admin_page",
        target_id="pages/admin.py",
        details=f"email={email or '-'}",
    )
    render_admin_access_denied()
    st.stop()

if _admin_mfa_enabled():
    mfa_ok = st.session_state.get("admin_mfa_ok_user_id") == user_id
    if not mfa_ok:
        st.markdown("### Verificação adicional de segurança")
        with st.form("admin_mfa_form"):
            mfa_code = st.text_input(
                "Código MFA (6 dígitos)",
                max_chars=6,
                placeholder="000000",
            )
            mfa_submit = st.form_submit_button("Validar acesso admin")
        if mfa_submit:
            totp_secret = str(os.getenv("ADMIN_MFA_TOTP_SECRET", "")).strip()
            static_code = str(os.getenv("ADMIN_MFA_CODE", "")).strip()
            ok = False
            if totp_secret:
                ok = _totp_valid(mfa_code, totp_secret)
            elif static_code:
                ok = hmac.compare_digest(str(mfa_code or "").strip(), static_code)
            if ok:
                st.session_state["admin_mfa_ok_user_id"] = user_id
                registrar_admin_audit(
                    admin_user_id=user_id,
                    action="admin_mfa_success",
                    target_type="admin_page",
                    target_id="pages/admin.py",
                )
                st.rerun()
            else:
                registrar_admin_audit(
                    admin_user_id=user_id,
                    action="admin_mfa_failure",
                    target_type="admin_page",
                    target_id="pages/admin.py",
                )
                st.error("Código de verificação inválido.")
        st.stop()

render_admin_dashboard()
