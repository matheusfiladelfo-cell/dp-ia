import streamlit as st


def render_onboarding_header(step_atual, total_steps=3):
    percentual = int((step_atual / total_steps) * 100)

    st.markdown(
        f"""
<div style="
padding: 14px 16px;
border-radius: 12px;
border: 1px solid #dbeafe;
background: linear-gradient(135deg, #eff6ff, #ffffff);
margin-bottom: 12px;
">
  <div style="font-size: 0.8rem; font-weight: 700; color: #1d4ed8; letter-spacing: 0.04em;">
    ONBOARDING INICIAL
  </div>
  <div style="font-size: 1.05rem; font-weight: 700; color: #0f172a; margin-top: 2px;">
    Configure seu ambiente em 3 passos
  </div>
  <div style="font-size: 0.9rem; color: #334155; margin-top: 2px;">
    Etapa {step_atual} de {total_steps} concluída.
  </div>
  <div style="
      margin-top: 8px;
      width: 100%;
      height: 8px;
      border-radius: 999px;
      background: #e2e8f0;
      overflow: hidden;
  ">
      <div style="
          width: {percentual}%;
          height: 100%;
          background: linear-gradient(90deg, #2563eb, #1d4ed8);
      "></div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_onboarding_hint_empresa():
    st.info(
        "Passo 1: Cadastre sua primeira empresa na barra lateral para liberar o fluxo de análise."
    )


def render_onboarding_hint_analise():
    st.info(
        "Passo 2: Escreva um caso trabalhista e clique em 'Analisar Caso' para gerar seu primeiro relatório."
    )


def render_onboarding_conclusao():
    st.success(
        "Passo 3 concluído: seu primeiro ciclo foi finalizado. Você já pode escalar análises com padrão executivo."
    )


def render_jornada_versao_1(total_empresas, uso_analises, status_assinatura):
    status = str((status_assinatura or {}).get("status", "")).lower()
    plano = str((status_assinatura or {}).get("plano", "FREE")).upper()

    etapa_empresa = "✅" if total_empresas > 0 else "⬜"
    etapa_analise = "✅" if uso_analises > 0 else "⬜"
    etapa_upgrade = "✅" if plano in {"PRO", "PREMIUM"} else "⬜"
    etapa_checkout = "✅" if status in {"aguardando pagamento", "ativo"} and plano in {"PRO", "PREMIUM"} else "⬜"
    etapa_assinatura = "✅" if status == "ativo" else "⬜"

    st.markdown(
        f"""
<div style="
padding: 12px 14px;
border-radius: 12px;
border: 1px solid #dbeafe;
background: #ffffff;
margin-top: 8px;
margin-bottom: 8px;
">
  <div style="font-weight:800; color:#0f172a; margin-bottom:6px;">Jornada Comercial 1.0</div>
  <div style="color:#334155; font-size:0.9rem; line-height:1.5;">
    {etapa_empresa} Cadastro de empresa<br/>
    {etapa_analise} Primeira análise<br/>
    {etapa_upgrade} Escolha de plano<br/>
    {etapa_checkout} Checkout iniciado<br/>
    {etapa_assinatura} Assinatura ativa
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
