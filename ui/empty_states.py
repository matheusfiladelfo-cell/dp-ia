import streamlit as st


def render_empty_state_sem_empresa():
    st.markdown(
        """
<div class="mp-empty-state">
  <div style="font-weight:800; color:#93c5fd; margin-bottom:2px;">Nenhuma empresa cadastrada</div>
  <div style="color:#cbd5e1; font-size:0.92rem;">
    Cadastre sua primeira empresa na barra lateral para iniciar análises e liberar o painel executivo.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_empty_state_sem_analises():
    st.markdown(
        """
<div class="mp-empty-state">
  <div style="font-weight:800; color:#e2e8f0; margin-bottom:2px;">Sem análises para esta empresa</div>
  <div style="color:#cbd5e1; font-size:0.92rem;">
    Realize a primeira análise no módulo principal para visualizar indicadores e tendências.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_empty_state_sem_historico():
    st.markdown(
        """
<div class="mp-empty-state">
  <div style="font-weight:700; color:#e2e8f0;">Sem histórico no período filtrado</div>
  <div style="color:#94a3b8; font-size:0.9rem;">
    Ajuste filtros de data e risco para ampliar a visão histórica.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_empty_state_plano_free_limitado():
    st.markdown(
        """
<div class="mp-empty-state">
  <div style="font-weight:700; color:#93c5fd;">
    Limite do plano Starter atingido.
  </div>
  <div style="color:#cbd5e1; font-size:0.88rem;">
    Upgrade elegante para Pro/Business: libere mais análises, PDF premium e operação escalável.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
