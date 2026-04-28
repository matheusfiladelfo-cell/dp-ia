import streamlit as st


def _nome_comercial_plano(plano):
    return {
        "FREE": "Starter",
        "PRO": "Pro",
        "PREMIUM": "Business",
    }.get(str(plano).upper(), str(plano))


def render_planos_comparativo(plano_atual):
    st.markdown(
        """
<style>
    .pricing-wrap {
        margin-top: 4px;
        margin-bottom: 10px;
    }
    .pricing-card {
        border: 1px solid #dbeafe;
        border-radius: 14px;
        background: #ffffff;
        padding: 12px 14px;
        min-height: 220px;
        box-shadow: 0 3px 12px rgba(15, 23, 42, 0.06);
    }
    .pricing-card.recommended {
        border: 2px solid #2563eb;
        box-shadow: 0 9px 24px rgba(37, 99, 235, 0.15);
        transform: translateY(-2px);
    }
    .pricing-badge {
        display: inline-block;
        background: #eff6ff;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 0.2rem 0.48rem;
        border-radius: 999px;
        margin-bottom: 0.48rem;
    }
</style>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="pricing-wrap"></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)

    free_current = " (atual)" if plano_atual == "FREE" else ""
    pro_current = " (atual)" if plano_atual == "PRO" else ""
    premium_current = " (atual)" if plano_atual == "PREMIUM" else ""

    with c1:
        st.markdown(
            f"""
<div class="pricing-card">
  <div class="pricing-badge">START</div>
  <h4 style="margin:0;">Starter{free_current}</h4>
  <p style="margin:4px 0 10px 0;"><b>R$ 97/mês</b></p>
  <p style="margin:0 0 6px 0; color:#475569; font-size:0.85rem;">Trial: 7 dias grátis ou 3 análises grátis</p>
  <p style="margin:0;">• Até 10 análises/mês</p>
  <p style="margin:0;">• 1 empresa</p>
  <p style="margin:0;">• Sem PDF premium</p>
  <p style="margin:0;">• Prioridade padrão</p>
</div>
""",
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
<div class="pricing-card recommended">
  <div class="pricing-badge">MAIS ESCOLHIDO</div>
  <h4 style="margin:0;">Pro{pro_current}</h4>
  <p style="margin:4px 0 10px 0;"><b>R$ 197/mês</b></p>
  <p style="margin:0;">• Até 200 análises/mês</p>
  <p style="margin:0;">• Até 5 empresas</p>
  <p style="margin:0;">• PDF premium liberado</p>
  <p style="margin:0;">• Prioridade futura</p>
</div>
""",
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
<div class="pricing-card">
  <div class="pricing-badge">ESCALA</div>
  <h4 style="margin:0;">Business{premium_current}</h4>
  <p style="margin:4px 0 10px 0;"><b>R$ 397/mês</b></p>
  <p style="margin:0;">• Análises ilimitadas</p>
  <p style="margin:0;">• Empresas ilimitadas</p>
  <p style="margin:0;">• PDF premium liberado</p>
  <p style="margin:0;">• Prioridade futura</p>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown(
        """
<div style="
margin-top: 10px;
padding: 10px 12px;
border-radius: 10px;
border: 1px solid #dbeafe;
background: #f8fbff;
color: #0f172a;
font-weight: 600;
">
💡 Trial disponível: 7 dias grátis ou 3 análises grátis. Evolua para Pro/Business e escale com padrão executivo.
</div>
""",
        unsafe_allow_html=True,
    )
