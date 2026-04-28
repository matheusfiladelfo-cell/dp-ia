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
    st.markdown("### Relatório Executivo")

    veredito = parecer.get("veredito_estrategico") or {}
    decisao = parecer.get("decisao_empresarial") or {}
    proxima = parecer.get("proxima_acao") or {}

    st.markdown(
        f"""
<div class="dpia-report-card">
  <strong>Resumo Executivo</strong><br>
  {limpar_texto_fn(veredito.get("resumo_executivo_1_linha") or parecer.get("diagnostico") or "Cenário consolidado para decisão estratégica.")}
</div>
<div class="dpia-report-card">
  <strong>Recomendação Imediata</strong><br>
  {limpar_texto_fn(veredito.get("principal_proximo_passo") or proxima.get("hoje") or parecer.get("recomendacao") or "Definir ação prioritária com base no risco atual.")}
</div>
<div class="dpia-report-card">
  <strong>Risco se Nada Fazer</strong><br>
  {limpar_texto_fn(decisao.get("risco_real") or parecer.get("risco") or "MÉDIO")} •
  {limpar_texto_fn(decisao.get("impacto_financeiro_provavel") or "Exposição financeira dependente do cenário probatório.")}
</div>
<div class="dpia-report-card">
  <strong>Próximo Movimento Ideal</strong><br>
  {limpar_texto_fn(proxima.get("dias_7") or veredito.get("aceitar_acordo_agora") or "Conduzir estratégia com governança e monitoramento semanal.")}
</div>
""",
        unsafe_allow_html=True,
    )

    assistente = parecer.get("assistente_juridico") or {}
    auditoria = parecer.get("auditoria_interna") or {}

    if decisao or assistente or proxima:
        st.markdown("#### 1) Decisão Empresarial")
        st.markdown(
            f"""
<div class="dpia-report-card">
<strong>Risco real:</strong> {limpar_texto_fn(decisao.get("risco_real", parecer.get("risco", "N/A")))}<br>
<strong>Impacto financeiro provável:</strong> {limpar_texto_fn(decisao.get("impacto_financeiro_provavel", parecer.get("impacto_financeiro", "N/A")))}<br>
<strong>Decisão recomendada:</strong> {limpar_texto_fn(decisao.get("decisao_recomendada", parecer.get("recomendacao", "N/A")))}
</div>
""",
            unsafe_allow_html=True,
        )

        st.markdown("#### 2) Assistente Jurídico")
        pontos_prova = assistente.get("pontos_de_prova") or parecer.get("pontos_dependentes_prova") or []
        docs_necessarios = assistente.get("documentos_necessarios") or []
        st.markdown(
            f"""
<div class="dpia-report-card">
<strong>Base legal prática:</strong> {limpar_texto_fn(assistente.get("base_legal_pratica", parecer.get("fundamentacao", "N/A")))}
</div>
""",
            unsafe_allow_html=True,
        )
        if pontos_prova:
            st.markdown("**Pontos de prova**")
            for item in pontos_prova:
                st.markdown(f"- {limpar_texto_fn(item)}")
        if docs_necessarios:
            st.markdown("**Documentos necessários**")
            for item in docs_necessarios:
                st.markdown(f"- {limpar_texto_fn(item)}")

        st.markdown("#### 3) Próxima Ação")
        st.markdown(
            f"""
<div class="dpia-report-card">
<strong>Hoje:</strong> {limpar_texto_fn(proxima.get("hoje", "Consolidar fatos e documentos essenciais."))}<br>
<strong>7 dias:</strong> {limpar_texto_fn(proxima.get("dias_7", "Definir estratégia com base na prova consolidada."))}<br>
<strong>30 dias:</strong> {limpar_texto_fn(proxima.get("dias_30", "Executar plano jurídico e revisar controles internos."))}
</div>
""",
            unsafe_allow_html=True,
        )

        st.markdown("#### Auditoria Interna")
        c1, c2, c3 = st.columns(3)
        audit_dec = auditoria.get("decisao_empresarial") or {}
        audit_ass = auditoria.get("assistente_juridico") or {}
        audit_acao = auditoria.get("proxima_acao") or {}
        with c1:
            st.metric("Decisão Empresarial", (audit_dec.get("confianca") or parecer.get("decisao_empresarial_confianca") or "media").upper())
            st.caption(limpar_texto_fn(audit_dec.get("motivo") or parecer.get("motivo_decisao_empresarial_confianca") or "Sem justificativa detalhada."))
        with c2:
            st.metric("Assistente Jurídico", (audit_ass.get("confianca") or parecer.get("assistente_juridico_confianca") or "media").upper())
            st.caption(limpar_texto_fn(audit_ass.get("motivo") or parecer.get("motivo_assistente_juridico_confianca") or "Sem justificativa detalhada."))
        with c3:
            st.metric("Próxima Ação", (audit_acao.get("confianca") or parecer.get("proxima_acao_confianca") or "media").upper())
            st.caption(limpar_texto_fn(audit_acao.get("motivo") or parecer.get("motivo_proxima_acao_confianca") or "Sem justificativa detalhada."))

        schema_version = parecer.get("parecer_schema_version")
        if schema_version:
            st.caption(f"schema: {schema_version}")

        st.markdown("---")

    if veredito:
        st.markdown("#### VEREDITO ESTRATÉGICO")
        st.markdown(
            f"""
<div class="dpia-report-card">
<strong>Aceitar acordo agora:</strong> {limpar_texto_fn(veredito.get("aceitar_acordo_agora", "depende")).upper()}<br>
<strong>Contestar inicialmente:</strong> {limpar_texto_fn(veredito.get("contestar_inicialmente", "sim")).upper()}<br>
<strong>Faixa de acordo sugerida:</strong> {limpar_texto_fn(veredito.get("faixa_acordo_sugerida", "Depende de cálculos e documentos."))}<br>
<strong>Urgência:</strong> {limpar_texto_fn(veredito.get("urgencia", "media")).upper()}<br>
<strong>Principal próximo passo:</strong> {limpar_texto_fn(veredito.get("principal_proximo_passo", "Consolidar base probatória e definir condução inicial."))}<br>
<strong>Resumo executivo (1 linha):</strong> {limpar_texto_fn(veredito.get("resumo_executivo_1_linha", "Decisão estratégica depende de risco, prova e custo provável."))}
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("#### 🧾 Análise do Caso")
    st.markdown(limpar_texto_fn(parecer.get("diagnostico")))

    st.markdown("#### ⚖️ Fundamentação Jurídica")
    st.markdown(limpar_texto_fn(parecer.get("fundamentacao")))

    st.markdown("#### 📉 Impactos Trabalhistas")
    st.markdown(parecer.get("impactos"))

    st.markdown("#### 💰 Impacto Financeiro")
    impacto_min = parecer.get("impacto_financeiro_provavel_min")
    impacto_max = parecer.get("impacto_financeiro_provavel_max")
    litigioso = bool(
        parecer.get("strategy_band")
        or parecer.get("faixa_provavel_acordo")
        or (impacto_min is not None and impacto_max is not None)
    )

    if impacto_min not in [None, ""] and impacto_max not in [None, ""]:
        try:
            impacto_min = float(impacto_min)
            impacto_max = float(impacto_max)
            if impacto_min > 0 and impacto_max > 0:
                st.markdown(f"### R$ {impacto_min:,.2f} a R$ {impacto_max:,.2f}")
                obs_faixa = parecer.get("observacao_faixa_financeira")
                if obs_faixa:
                    st.caption(limpar_texto_fn(obs_faixa))
            else:
                st.markdown("### Faixa inicial em revisão (dependente de cálculos).")
        except Exception:
            st.markdown("### Faixa inicial em revisão (dependente de cálculos).")
    else:
        impacto = parecer.get("impacto_financeiro", 0)

        try:
            impacto = float(impacto)
        except Exception:
            impacto = 0

        if litigioso and impacto <= 0:
            st.markdown("### Faixa estimada inicial disponível mediante memória de cálculos.")
            st.caption("Caso litigioso sem base numérica completa. O valor depende de cálculos detalhados.")
        else:
            st.markdown(f"### R$ {impacto:,.2f}")

    st.markdown("#### 📌 Orientação Estratégica")
    st.markdown(limpar_texto_fn(parecer.get("recomendacao")))
