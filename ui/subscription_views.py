import streamlit as st


def _nome_comercial_plano(plano):
    return {
        "FREE": "Starter",
        "PRO": "Pro",
        "PREMIUM": "Business",
    }.get(str(plano).upper(), str(plano))


def render_status_assinatura_card(status_data):
    plano = status_data.get("plano", "FREE")
    status = status_data.get("status", "pendente")
    vencimento = status_data.get("next_billing_at") or "Não informado"
    beneficios = status_data.get("beneficios", [])

    status_cor = {
        "ativo": "#166534",
        "aguardando pagamento": "#b45309",
        "pendente": "#92400e",
        "expirado": "#b91c1c",
    }.get(status, "#334155")

    beneficios_html = "".join([f"<li style='margin-bottom:4px;'>{b}</li>" for b in beneficios])
    plano_display = _nome_comercial_plano(plano)

    st.markdown(
        f"""
<div style="
padding: 14px 16px;
border-radius: 14px;
background: #ffffff;
border: 1px solid #dbeafe;
box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
margin-bottom: 12px;
">
  <div style="font-size:0.78rem; font-weight:800; color:#1d4ed8; letter-spacing:0.05em;">
    Status da Assinatura
  </div>
  <div style="display:flex; gap:10px; margin-top:6px; align-items:center; flex-wrap:wrap;">
    <span style="font-weight:800; font-size:1.1rem; color:#0f172a;">Plano: {plano_display}</span>
    <span style="
      padding:4px 10px;
      border-radius:999px;
      border:1px solid {status_cor};
      color:{status_cor};
      font-size:0.76rem;
      font-weight:800;
      text-transform:uppercase;
    ">{status}</span>
  </div>
  <div style="margin-top:6px; color:#334155; font-size:0.9rem;">
    Próximo vencimento: <b>{vencimento}</b>
  </div>
  <div style="margin-top:8px;">
    <div style="font-weight:700; color:#0f172a; margin-bottom:4px;">Benefícios desbloqueados</div>
    <ul style="margin:0 0 0 18px; color:#1f2937;">
      {beneficios_html}
    </ul>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_cta_upgrade_free():
    st.markdown(
        """
<div style="
margin-top:4px;
padding:10px 12px;
border-radius:10px;
border:1px solid #bfdbfe;
background:#eff6ff;
color:#1e3a8a;
font-weight:700;
">
Trial disponível: 7 dias grátis ou 3 análises. Faça upgrade e libere recursos premium.
</div>
""",
        unsafe_allow_html=True,
    )
    return st.button("🚀 Upgrade para Pro/Business", width="stretch", key="cta_upgrade_from_status")
