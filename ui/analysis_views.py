import streamlit as st


def render_analysis_input():
    st.markdown(
        """
<div class="dpia-report-card">
<strong>Entrada do Caso</strong><br>
Descreva o cenário trabalhista para gerar um parecer estratégico.
</div>
""",
        unsafe_allow_html=True,
    )
    if "analysis_input_prefill" in st.session_state:
        st.session_state["analysis_texto_usuario"] = st.session_state.pop("analysis_input_prefill")
    texto_usuario = st.text_area(
        "Descreva o problema trabalhista da empresa",
        placeholder="Descreva o problema trabalhista da empresa...",
        height=210,
        key="analysis_texto_usuario",
    )
    analisar_clicked = st.button("⚖️ Gerar Parecer Estratégico", width="stretch", type="primary")
    return texto_usuario, analisar_clicked


def render_score(score, probabilidade, nivel, cor_score_fn):
    st.markdown("### Indicadores de Risco")
    score_color = "#f87171" if score >= 75 else "#fbbf24" if score >= 55 else "#34d399"
    nivel_color = "#f87171" if "ALTO" in str(nivel).upper() else "#fbbf24" if "MÉDIO" in str(nivel).upper() or "MEDIO" in str(nivel).upper() else "#34d399"
    st.markdown(
        f"""
<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0.75rem;margin:0.4rem 0 0.8rem 0;">
  <div class="dpia-report-card" style="margin:0;">
    <div style="color:#cbd5e1;font-size:0.82rem;font-weight:700;">SCORE</div>
    <div style="color:#f8fafc;font-size:1.72rem;font-weight:900;line-height:1.1;">
      <span style="color:{score_color};">{cor_score_fn(score)}</span> {score}/100
    </div>
  </div>
  <div class="dpia-report-card" style="margin:0;">
    <div style="color:#cbd5e1;font-size:0.82rem;font-weight:700;">PROBABILIDADE</div>
    <div style="color:#f8fafc;font-size:1.72rem;font-weight:900;line-height:1.1;">{probabilidade}%</div>
  </div>
  <div class="dpia-report-card" style="margin:0;">
    <div style="color:#cbd5e1;font-size:0.82rem;font-weight:700;">NÍVEL DE RISCO</div>
    <div style="color:{nivel_color};font-size:1.72rem;font-weight:900;line-height:1.1;">{nivel}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_decisao_executiva(score):
    if score >= 80:
        titulo = "Não prosseguir"
        subtitulo = "Exposição jurídica muito elevada para a decisão atual."
        cor = "#b91c1c"
        fundo = "linear-gradient(135deg, #7f1d1d, #b91c1c)"
        emoji = "🛑"
    elif score >= 60:
        titulo = "Prosseguir com cautela"
        subtitulo = "Prosseguir apenas com controles e mitigação imediata."
        cor = "#b45309"
        fundo = "linear-gradient(135deg, #92400e, #d97706)"
        emoji = "⚠️"
    else:
        titulo = "Seguro para prosseguir"
        subtitulo = "Cenário com risco controlado para continuidade."
        cor = "#166534"
        fundo = "linear-gradient(135deg, #14532d, #16a34a)"
        emoji = "✅"

    st.markdown(
        f"""
<div style="
padding: 18px 20px;
border-radius: 14px;
background: {fundo};
color: #ffffff;
box-shadow: 0 8px 20px rgba(15, 23, 42, 0.18);
margin: 10px 0 18px 0;
border: 1px solid rgba(255,255,255,0.18);
">
  <div style="font-size: 0.82rem; letter-spacing: 0.08em; opacity: 0.92; font-weight: 700;">
    DECISÃO EXECUTIVA
  </div>
  <div style="font-size: 1.38rem; font-weight: 800; margin-top: 4px;">
    {emoji} {titulo}
  </div>
  <div style="font-size: 0.95rem; margin-top: 6px; opacity: 0.95;">
    {subtitulo}
  </div>
  <div style="
      margin-top: 10px;
      display: inline-block;
      padding: 5px 10px;
      border-radius: 999px;
      background: rgba(255,255,255,0.16);
      font-size: 0.8rem;
      font-weight: 700;
      border: 1px solid rgba(255,255,255,0.25);
      color: #ffffff;
  ">
    Score atual: {score}/100
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_parecer_sections(parecer, limpar_texto_fn):
    st.markdown("### Parecer Profissional")

    decisao = parecer.get("decisao_empresarial") or {}
    proxima = parecer.get("proxima_acao") or {}
    estrategia = (
        parecer.get("estrategia_recomendada")
        or parecer.get("recomendacao")
        or decisao.get("decisao_recomendada")
    )

    st.markdown("#### 1) Diagnóstico Inicial")
    st.markdown(
        f"""
<div class="dpia-report-card">
{limpar_texto_fn(parecer.get("diagnostico") or parecer.get("tese_risco") or "Diagnóstico inicial em elaboração com base nos fatos informados.")}
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("#### 2) Risco Jurídico")
    st.markdown(
        f"""
<div class="dpia-report-card">
<strong>Nível:</strong> {limpar_texto_fn(decisao.get("risco_real") or parecer.get("risco") or "INCONCLUSIVO")}<br>
{limpar_texto_fn(parecer.get("fundamentacao") or parecer.get("tese_defesa") or "Risco depende da robustez documental e da coerência dos fatos.")}
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("#### 3) Impacto Financeiro")
    impacto_min = parecer.get("impacto_financeiro_provavel_min")
    impacto_max = parecer.get("impacto_financeiro_provavel_max")
    msg_sem_base = "Impacto financeiro depende de salário, tempo de vínculo e verbas discutidas."
    impacto_renderizado = msg_sem_base
    if impacto_min not in [None, ""] and impacto_max not in [None, ""]:
        try:
            impacto_min = float(impacto_min)
            impacto_max = float(impacto_max)
            if impacto_min > 0 and impacto_max > 0:
                impacto_renderizado = f"R$ {impacto_min:,.2f} a R$ {impacto_max:,.2f}"
        except Exception:
            impacto_renderizado = msg_sem_base
    st.markdown(
        f"""
<div class="dpia-report-card">
{limpar_texto_fn(decisao.get("impacto_financeiro_provavel") or impacto_renderizado)}
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("#### 4) Próxima Ação Recomendada")
    st.markdown(
        f"""
<div class="dpia-report-card">
{limpar_texto_fn(proxima.get("hoje") or parecer.get("pedido_complemento") or "Validar documentos críticos antes de consolidar posição final.")}
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("#### 5) Estratégia Empresarial")
    st.markdown(
        f"""
<div class="dpia-report-card">
{limpar_texto_fn(estrategia or "Conduzir estratégia com base em prova, prazo e impacto potencial.")}
</div>
""",
        unsafe_allow_html=True,
    )
