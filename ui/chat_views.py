import json

import streamlit as st
from datetime import datetime
from banco import obter_email_usuario, registrar_evento_produto

from application.document_fatos_llm import (
    CHAVES_JSON,
    LABELS_PT,
    analisar_fatos_documento,
    aplicar_fatos_documento_na_sessao,
)
from application.document_parser import MAX_UPLOAD_BYTES_DEFAULT, parse_documento
from application.pdf_generator import gerar_pdf_relatorio


def render_chat_title():
    st.subheader("💬 Consultor Trabalhista")


def render_chat_document_upload(sessao, usuario_id=None, empresa_id=None):
    """
    Upload opcional acima do chat_input; incorpora texto ao histórico para o LLM.
    """
    limite_mb = max(1, MAX_UPLOAD_BYTES_DEFAULT // (1024 * 1024))
    uploaded = st.file_uploader(
        "Anexar documentos (opcional)",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key="chat_documentacao_upload",
        help=f"PDF, DOCX ou TXT. Até {limite_mb} MiB por arquivo.",
    )
    if not uploaded:
        return

    processados = st.session_state.setdefault("chat_documentos_processados_sig", [])
    novos = False
    nomes_incorporados = []

    for f in uploaded:
        sig = (getattr(f, "name", "") or "", int(getattr(f, "size", 0) or 0))
        if sig in processados:
            continue
        try:
            texto = parse_documento(f)
        except ValueError as err:
            st.error(str(err))
            continue
        nome = getattr(f, "name", None) or "documento"
        with st.spinner("Analisando fatos do documento…"):
            fatos = analisar_fatos_documento(texto)
        aplicar_fatos_documento_na_sessao(sessao, fatos)
        orig_ia = json.loads(json.dumps(fatos)) if fatos else {}
        sessao.adicionar(
            "document",
            texto,
            arquivo=nome,
            fatos_extraidos=fatos,
            fatos_ia_originais=orig_ia,
        )
        processados.append(sig)
        novos = True
        nomes_incorporados.append(nome)
        try:
            registrar_evento_produto(
                nome_evento="documento_anexado",
                usuario_id=usuario_id,
                empresa_id=empresa_id,
                metadados={
                    "arquivo": nome,
                    "tamanho_bytes": int(getattr(f, "size", 0) or 0),
                },
            )
        except Exception:
            pass

    if novos:
        st.toast("Documento(s) incorporados ao contexto: " + ", ".join(nomes_incorporados))
        st.rerun()


def render_chat_input():
    return st.chat_input("Digite sua dúvida...")


def render_chat_historico(sessao, empresa_id=None, usuario_id=None):
    from ui.document_fatos_validacao import (
        documento_tem_fatos_validados_persistidos,
        render_validacao_fatos_documento,
    )

    for msg in sessao.historico:
        role = msg.get("role")
        if role == "document":
            nome = msg.get("arquivo") or "documento"
            with st.chat_message("assistant", avatar="📎"):
                with st.expander(f"Conteúdo do documento: {nome}"):
                    st.text(msg.get("texto") or "")
                if "fatos_extraidos" in msg:
                    if not documento_tem_fatos_validados_persistidos(msg):
                        fatos = msg.get("fatos_extraidos") or {}
                        st.markdown(
                            "**Fatos extraídos pela IA** *(assistência automatizada — conferir no documento original)*:"
                        )
                        if fatos:
                            for chave in CHAVES_JSON:
                                rotulo = LABELS_PT.get(chave, chave)
                                val = fatos.get(chave)
                                if chave == "evidencias_mencionadas":
                                    if isinstance(val, list) and val:
                                        itens = "\n".join(f"- {e}" for e in val)
                                        st.markdown(f"**{rotulo}:**\n{itens}")
                                    else:
                                        st.markdown(f"**{rotulo}:** Não encontrado")
                                else:
                                    st.markdown(f"**{rotulo}:** {val}")
                        else:
                            st.caption(
                                "A extração estruturada não pôde ser concluída para este arquivo. "
                                "O texto integral permanece disponível no expansor acima."
                            )
                    render_validacao_fatos_documento(
                        sessao,
                        msg,
                        empresa_id=empresa_id,
                        usuario_id=usuario_id,
                    )
            continue
        with st.chat_message(role):
            st.write(msg["texto"])


def determinar_risco_cenario(nome_cenario: str, risco_original: str) -> str:
    """
    Classificação determinística por tipo de cenário, alinhada ao risco principal do caso.
    Não altera score_engine; apenas explicita mitigação esperada por ação.
    """
    nome = (nome_cenario or "").lower()
    orig = str(risco_original or "").strip().upper().replace("MEDIO", "MÉDIO")
    if orig not in {"ALTO", "MÉDIO", "BAIXO"}:
        orig = "MÉDIO"

    if "negociar" in nome or "acordo" in nome:
        return "BAIXO"
    if "regularizar" in nome or "pagar" in nome:
        return "MÉDIO" if orig == "ALTO" else "BAIXO"
    # Manutenção do status quo ou confronto (ex.: demitir agora)
    return orig


def _cor_texto_por_risco(nivel: str) -> str:
    n = str(nivel or "").upper().replace("MEDIO", "MÉDIO")
    if n == "ALTO":
        return "#ef4444"
    if n == "MÉDIO":
        return "#eab308"
    if n == "BAIXO":
        return "#22c55e"
    return "#94a3b8"


def _emoji_risco_associado(nivel: str) -> str:
    n = str(nivel or "").upper().replace("MEDIO", "MÉDIO")
    if n == "ALTO":
        return "🔴"
    if n == "MÉDIO":
        return "🟡"
    if n == "BAIXO":
        return "🟢"
    return "⚪"


def _html_bloco_simulacao_decisao(simulacao: dict, risco_original: str) -> str:
    cenarios = [
        ("Se você demitir agora", "demitir agora", "se_demitir_agora"),
        ("Se regularizar antes", "regularizar antes", "se_regularizar_antes"),
        ("Se negociar acordo", "negociar acordo", "se_negociar_acordo"),
    ]
    blocos = []
    for titulo, nome_logico, chave in cenarios:
        ref_triagem = simulacao.get(chave, "INCONCLUSIVO")
        assoc = determinar_risco_cenario(nome_logico, risco_original)
        emoji = _emoji_risco_associado(assoc)
        cor = _cor_texto_por_risco(assoc)
        blocos.append(
            f"""
<div style="margin-bottom:12px; padding:12px 14px; border-radius:10px; border:1px solid #334155; background:rgba(15,23,42,0.55);">
  <div style="font-weight:700; color:#f8fafc;">{titulo}</div>
  <div style="margin-top:8px; font-size:1.05rem; font-weight:800; color:{cor}; letter-spacing:0.02em;">
    Risco associado: {emoji} {assoc}
  </div>
  <div style="margin-top:6px; font-size:0.82rem; color:#94a3b8;">
    Triagem do relatório para este cenário: → risco {ref_triagem}
  </div>
</div>
"""
        )
    return (
        '<div class="dpia-report-card" style="border: 1px solid #334155;">'
        '<strong>Simulação de decisão</strong>'
        + "".join(blocos)
        + "</div>"
    )


def render_barra_impacto_financeiro(score_risco: int):
    try:
        score = int(score_risco or 0)
    except Exception:
        score = 0
    score = max(0, min(score, 100))

    if score < 30:
        cor = "#22c55e"
        titulo = "Impacto Potencial: Baixo"
        emoji = "🟩"
        rotulo_executivo = "Baixo"
    elif score < 70:
        cor = "#eab308"
        titulo = "Impacto Potencial: Significativo"
        emoji = "🟡"
        rotulo_executivo = "Significativo"
    else:
        cor = "#ef4444"
        titulo = "Impacto Potencial: Elevado"
        emoji = "🔴"
        rotulo_executivo = "Elevado"

    st.markdown(
        f"""
<div style="margin-top:6px; margin-bottom:8px;">
  <div style="font-size:0.86rem; color:#cbd5e1; font-weight:700;">{emoji} {titulo}</div>
  <div style="
      width:100%;
      height:10px;
      margin-top:6px;
      border-radius:999px;
      background:#1f2937;
      border:1px solid #334155;
      overflow:hidden;
  ">
      <div style="width:{score}%; height:100%; background:{cor};"></div>
  </div>
  <div style="font-size:0.88rem; color:#e2e8f0; margin-top:8px; font-weight:600;">
    Score de Impacto: {score}/100 • {rotulo_executivo}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _format_reais_br(valor: float) -> str:
    try:
        v = float(valor)
    except (TypeError, ValueError):
        v = 0.0
    sinal = "-" if v < 0 else ""
    abs_v = abs(v)
    inteiro, frac = f"{abs_v:.2f}".split(".")
    inteiro_fmt = f"{int(inteiro):,}".replace(",", ".")
    return f"R$ {sinal}{inteiro_fmt},{frac}"


def calcular_reducao_risco(risco_original: str, acoes_concluidas: int, total_acoes: int) -> str:
    """
    Projeção visual representativa do efeito do plano de ação (somente UI).
    """
    orig = str(risco_original or "").strip().upper().replace("MEDIO", "MÉDIO")
    if orig not in {"ALTO", "MÉDIO", "BAIXO"}:
        orig = "MÉDIO"

    try:
        concl = int(acoes_concluidas or 0)
        total = int(total_acoes or 0)
    except Exception:
        return orig

    if total <= 0:
        return orig
    if concl <= 0:
        return orig
    if concl >= total:
        return "BAIXO"
    if concl > total / 2:
        if orig == "ALTO":
            return "MÉDIO"
        if orig == "MÉDIO":
            return "BAIXO"
        return "BAIXO"
    return orig


def _html_reducao_risco_plano(risco_atual: str, risco_projetado: str, concluidas: int, total: int) -> str:
    def _norm(r):
        x = str(r or "").strip().upper().replace("MEDIO", "MÉDIO")
        return x if x in {"ALTO", "MÉDIO", "BAIXO"} else "MÉDIO"

    atual = _norm(risco_atual)
    proj = _norm(risco_projetado)
    em_atual = _emoji_risco_associado(atual)
    em_proj = _emoji_risco_associado(proj)
    cor_atual = _cor_texto_por_risco(atual)
    cor_proj = _cor_texto_por_risco(proj)
    return f"""
<div style="margin-bottom:14px; padding:14px 16px; border-radius:10px; border:1px solid #334155; background:rgba(15,23,42,0.6);">
  <div style="font-size:0.82rem; color:#94a3b8; font-weight:700;">Redução de risco (simulação pelo progresso do plano)</div>
  <div style="margin-top:10px; display:flex; flex-wrap:wrap; align-items:center; gap:10px; font-size:1rem; font-weight:800;">
    <span style="color:{cor_atual};">{em_atual} Risco atual: {atual}</span>
    <span style="color:#64748b;">→</span>
    <span style="color:{cor_proj};">{em_proj} Risco projetado: {proj}</span>
  </div>
  <div style="margin-top:8px; font-size:0.8rem; color:#94a3b8;">
    Ações concluídas: {concluidas}/{total} • atualiza ao marcar o checklist
  </div>
</div>
"""


def _build_relatorio_view_model(relatorio):
    nivel = str(relatorio.get("nivel_risco_visual") or "INCONCLUSIVO").upper()
    if nivel == "ALTO":
        risco_visual = "🔴 RISCO: ALTO"
        risco_cor = "#ef4444"
    elif nivel == "MÉDIO":
        risco_visual = "🟡 RISCO: MÉDIO"
        risco_cor = "#eab308"
    elif nivel == "BAIXO":
        risco_visual = "🟢 RISCO: BAIXO"
        risco_cor = "#22c55e"
    else:
        risco_visual = "⚪ RISCO: INCONCLUSIVO"
        risco_cor = "#94a3b8"

    checklist = relatorio.get("plano_acao_checklist") or []
    checklist_html = "".join(f"<li>✔ {item}</li>" for item in checklist)

    base_legal = relatorio.get("base_legal_simplificada") or []
    base_legal_html = "".join(f"<li>{item}</li>" for item in base_legal)
    simulacao = relatorio.get("simulacao_decisao") or {}
    proximos_passos = relatorio.get("proximos_passos_recomendados") or []
    proximos_passos_html = "".join(f"<li>{item}</li>" for item in proximos_passos)
    historico = relatorio.get("historico_empresa") or {}
    frase_historico = str(
        historico.get("resumo")
        or "Com base no histórico da empresa, não há dados suficientes para padrão recorrente."
    )
    recomendacao_final = str(relatorio.get("decisao_recomendada") or "").strip()
    if not recomendacao_final:
        recomendacao_final = "Validar documentos antes de decidir."
    if "." in recomendacao_final:
        recomendacao_final = recomendacao_final.split(".")[0].strip() + "."

    score_v2 = (relatorio.get("score_engine_v2") or {})
    impacto_estimado = score_v2.get("impacto_financeiro_estimado")
    try:
        impacto_estimado_val = float(impacto_estimado)
    except (TypeError, ValueError):
        impacto_estimado_val = 0.0

    impacto_md = str(score_v2.get("impacto_financeiro_detalhe_md") or "").strip()
    if not impacto_md:
        for linha in score_v2.get("racional") or []:
            if "Estimativa de Passivo Trabalhista" in str(linha):
                impacto_md = str(linha)
                break

    return {
        "nivel_risco": nivel,
        "risco_visual": risco_visual,
        "risco_cor": risco_cor,
        "checklist": checklist,
        "checklist_html": checklist_html,
        "base_legal_html": base_legal_html,
        "base_legal": base_legal,
        "simulacao": simulacao,
        "proximos_passos": proximos_passos,
        "proximos_passos_html": proximos_passos_html,
        "frase_historico": frase_historico,
        "recomendacao_final": recomendacao_final,
        "score_risco": int((relatorio.get("fluxo_consulta") or {}).get("pontuacao") or 0),
        "impacto_financeiro_estimado": impacto_estimado_val,
        "impacto_financeiro_detalhe_md": impacto_md,
        "score_engine_v2": score_v2,
    }


def _linhas_racional_score_sem_impacto(racional: list) -> list[str]:
    """Remove o bloco Markdown da calculadora CLT (exibido no expander de impacto)."""
    out: list[str] = []
    omitir = False
    for linha in racional or []:
        texto = str(linha or "").strip()
        if not texto:
            continue
        if "Estimativa de Passivo Trabalhista" in texto:
            omitir = True
            continue
        if omitir:
            if texto.startswith("Categoria de risco"):
                out.append(texto)
                omitir = False
            continue
        out.append(texto)
    return out


def _render_resumo_scores(relatorio):
    fluxo = relatorio.get("fluxo_consulta") or {}
    try:
        p1 = int(fluxo.get("pontuacao") or 0)
    except (TypeError, ValueError):
        p1 = 0
    r1 = str(fluxo.get("risco") or "INCONCLUSIVO").upper().replace("MEDIO", "MÉDIO")
    em1 = _emoji_risco_associado(r1 if r1 in {"ALTO", "MÉDIO", "BAIXO"} else "INCONCLUSIVO")
    st.markdown(f"**Score v1 (conversa):** {em1} **{r1}** ({p1}/100)")

    se2 = relatorio.get("score_engine_v2") or {}
    if se2.get("disponivel") and se2.get("score_final") is not None:
        try:
            p2 = int(se2["score_final"])
        except (TypeError, ValueError):
            p2 = 0
        n2 = str(se2.get("nivel") or "INCONCLUSIVO").upper().replace("MEDIO", "MÉDIO")
        em2 = _emoji_risco_associado(n2 if n2 in {"ALTO", "MÉDIO", "BAIXO"} else "INCONCLUSIVO")
        st.markdown(f"**Score v2 (fatos validados):** {em2} **{n2}** ({p2}/100)")
    else:
        st.caption(
            "Score v2 indisponível: valide e salve fatos no documento anexado para pontuar com base nas evidências aprovadas."
        )


def _render_comparativo_scores_risco(relatorio):
    fluxo = relatorio.get("fluxo_consulta") or {}
    try:
        p1 = int(fluxo.get("pontuacao") or 0)
    except (TypeError, ValueError):
        p1 = 0
    r1 = str(fluxo.get("risco") or "INCONCLUSIVO").upper().replace("MEDIO", "MÉDIO")
    em1 = _emoji_risco_associado(r1 if r1 in {"ALTO", "MÉDIO", "BAIXO"} else "INCONCLUSIVO")
    st.markdown(f"**Score v1 (baseado na conversa):** {em1} **{r1}** ({p1}/100)")

    se2 = relatorio.get("score_engine_v2") or {}
    if se2.get("disponivel") and se2.get("score_final") is not None:
        try:
            p2 = int(se2["score_final"])
        except (TypeError, ValueError):
            p2 = 0
        n2 = str(se2.get("nivel") or "INCONCLUSIVO").upper().replace("MEDIO", "MÉDIO")
        em2 = _emoji_risco_associado(n2 if n2 in {"ALTO", "MÉDIO", "BAIXO"} else "INCONCLUSIVO")
        st.markdown(f"**Score v2 (baseado em fatos validados):** {em2} **{n2}** ({p2}/100)")
        with st.expander("Ver racional do Score v2"):
            for linha in se2.get("racional") or []:
                st.markdown(f"- {linha}")
    else:
        st.caption(
            "Score v2 indisponível: valide e salve fatos no documento anexado para pontuar com base nas evidências aprovadas."
        )


def _formatar_score_para_pdf(relatorio: dict, vm: dict) -> str:
    linhas: list[str] = []
    fluxo = relatorio.get("fluxo_consulta") or {}
    try:
        p1 = int(fluxo.get("pontuacao") or 0)
    except (TypeError, ValueError):
        p1 = 0
    r1 = str(fluxo.get("risco") or "INCONCLUSIVO").upper().replace("MEDIO", "MÉDIO")
    linhas.append(f"Score v1 (conversa): {r1} ({p1}/100)")

    se2 = vm.get("score_engine_v2") or relatorio.get("score_engine_v2") or {}
    if se2.get("disponivel") and se2.get("score_final") is not None:
        try:
            p2 = int(se2["score_final"])
        except (TypeError, ValueError):
            p2 = 0
        n2 = str(se2.get("nivel") or "INCONCLUSIVO").upper().replace("MEDIO", "MÉDIO")
        linhas.append(f"Score v2 (fatos validados): {n2} ({p2}/100)")
        racional = _linhas_racional_score_sem_impacto(se2.get("racional") or [])
        if racional:
            linhas.append("")
            linhas.append("Racional:")
            linhas.extend(f"- {x}" for x in racional)
    else:
        linhas.append("Score v2: indisponível (valide fatos no documento anexado).")
    return "\n".join(linhas)


def _build_dados_pdf_relatorio(relatorio: dict, vm: dict) -> dict:
    diag_partes = [
        str(relatorio.get("diagnostico") or "—"),
        "",
        "Com base no histórico da empresa:",
        str(vm.get("frase_historico") or "—"),
        "",
        "Risco jurídico:",
        str(relatorio.get("risco_juridico") or "—"),
    ]

    acao_linhas: list[str] = []
    for item in vm.get("checklist") or []:
        acao_linhas.append(f"• {item}")
    if vm.get("proximos_passos"):
        if acao_linhas:
            acao_linhas.append("")
        acao_linhas.append("Próximos passos:")
        for item in vm["proximos_passos"]:
            acao_linhas.append(f"• {item}")
    if relatorio.get("decisao_recomendada"):
        if acao_linhas:
            acao_linhas.append("")
        acao_linhas.append("Decisão recomendada:")
        acao_linhas.append(str(relatorio.get("decisao_recomendada")))
    if vm.get("recomendacao_final"):
        if acao_linhas:
            acao_linhas.append("")
        acao_linhas.append(f"Recomendação final: {vm['recomendacao_final']}")

    impacto_md = str(vm.get("impacto_financeiro_detalhe_md") or "").strip()
    impacto_val = float(vm.get("impacto_financeiro_estimado") or 0)
    if not impacto_md and impacto_val > 0:
        impacto_md = f"**Total consolidado:** {_format_reais_br(impacto_val)}"
    impacto_narr = str(relatorio.get("impacto_financeiro") or "").strip()
    if impacto_narr:
        impacto_md = f"{impacto_md}\n\nContexto narrativo:\n{impacto_narr}".strip()

    estrategia_partes = [str(relatorio.get("estrategia") or "—")]
    sim = vm.get("simulacao") or {}
    if sim:
        estrategia_partes.extend(["", "Simulação de decisão:"])
        for titulo, chave in (
            ("Se demitir agora", "se_demitir_agora"),
            ("Se regularizar antes", "se_regularizar_antes"),
            ("Se negociar acordo", "se_negociar_acordo"),
        ):
            ref = sim.get(chave, "INCONCLUSIVO")
            estrategia_partes.append(f"• {titulo}: risco {ref}")

    base_legal = vm.get("base_legal") or relatorio.get("base_legal_simplificada") or []
    base_legal_txt = "\n".join(f"• {item}" for item in base_legal) if base_legal else "—"

    return {
        "risco": vm.get("nivel_risco") or relatorio.get("nivel_risco_visual") or "INCONCLUSIVO",
        "score": _formatar_score_para_pdf(relatorio, vm),
        "diagnostico": "\n".join(diag_partes),
        "impacto_financeiro": impacto_md or "Provisionamento quantitativo não disponível.",
        "acao": "\n".join(acao_linhas) if acao_linhas else "—",
        "estrategia": "\n".join(estrategia_partes),
        "base_legal": base_legal_txt,
    }


def _render_linha_racional_score(linha: str) -> None:
    texto = str(linha or "").strip()
    if not texto:
        return
    if texto.startswith("**") or texto.startswith("* "):
        st.markdown(texto)
    else:
        st.markdown(f"- {texto}")


def _render_relatorio_completo(relatorio, vm):
    st.caption("Relatório baseado na análise completa da conversa")
    st.markdown(
        f"""
<div class="dpia-report-card" style="border: 2px solid {vm["risco_cor"]}; border-left: 8px solid {vm["risco_cor"]}; padding: 18px;">
  <strong style="font-size: 1.35rem; color: {vm["risco_cor"]}; letter-spacing: 0.02em;">{vm["risco_visual"]}</strong>
</div>
""",
        unsafe_allow_html=True,
    )

    dados_pdf = _build_dados_pdf_relatorio(relatorio, vm)
    try:
        pdf_bytes = gerar_pdf_relatorio(dados_pdf)
        st.download_button(
            label="📄 Baixar Relatório em PDF",
            data=pdf_bytes,
            file_name="relatorio_risco_trabalhista.pdf",
            mime="application/pdf",
            type="primary",
            key="download_relatorio_completo_pdf",
        )
    except FileNotFoundError as err:
        st.warning(f"Exportação PDF indisponível: {err}")
    except Exception as err:
        st.error(f"Não foi possível gerar o PDF: {err}")

    with st.expander("📊 Diagnóstico Detalhado", expanded=True):
        st.markdown(str(relatorio.get("diagnostico") or "—"))
        st.markdown("**Com base no histórico da empresa**")
        st.markdown(vm["frase_historico"])
        st.markdown("**Risco jurídico**")
        st.markdown(str(relatorio.get("risco_juridico") or "—"))

    impacto_val = float(vm.get("impacto_financeiro_estimado") or 0)
    impacto_titulo = _format_reais_br(impacto_val) if impacto_val > 0 else "a estimar"
    with st.expander(f"💰 Impacto Financeiro Estimado: {impacto_titulo}"):
        impacto_md = str(vm.get("impacto_financeiro_detalhe_md") or "").strip()
        if impacto_md:
            st.markdown(impacto_md)
        elif impacto_val > 0:
            st.markdown(f"**Total consolidado:** {_format_reais_br(impacto_val)}")
            st.caption(
                "Estimativa com base nos fatos validados (salário, tempo de serviço e verbas identificadas)."
            )
        else:
            render_barra_impacto_financeiro(vm["score_risco"])
            st.caption("Provisionamento quantitativo indisponível; exibindo faixa qualitativa pelo score.")
        impacto_txt = str(relatorio.get("impacto_financeiro") or "").strip()
        if impacto_txt:
            st.markdown("---")
            st.markdown("**Contexto narrativo**")
            st.markdown(impacto_txt)

    with st.expander("📌 Plano de Ação Recomendado"):
        if vm.get("checklist"):
            for item in vm["checklist"]:
                st.markdown(f"- ✔ {item}")
        else:
            st.caption("Nenhum item de checklist registrado.")
        if vm.get("proximos_passos"):
            st.markdown("**Próximos passos**")
            for item in vm["proximos_passos"]:
                st.markdown(f"- {item}")
        if relatorio.get("decisao_recomendada"):
            st.markdown("**Decisão recomendada**")
            st.markdown(str(relatorio.get("decisao_recomendada")))
        st.markdown(f"**👉 Recomendação final:** {vm['recomendacao_final']}")

    with st.expander("🧠 Estratégia Jurídica"):
        st.markdown(str(relatorio.get("estrategia") or "—"))
        st.markdown("---")
        st.markdown(
            _html_bloco_simulacao_decisao(vm["simulacao"], vm["nivel_risco"]),
            unsafe_allow_html=True,
        )

    with st.expander("⚖️ Base Legal Aplicável"):
        itens_legal = vm.get("base_legal") or relatorio.get("base_legal_simplificada") or []
        if itens_legal:
            for item in itens_legal:
                st.markdown(f"- {item}")
        else:
            st.caption("Base legal simplificada não informada neste relatório.")

    with st.expander("📈 Entenda como o Score foi calculado"):
        _render_resumo_scores(relatorio)
        se2 = vm.get("score_engine_v2") or {}
        linhas = _linhas_racional_score_sem_impacto(se2.get("racional") or [])
        if linhas:
            st.markdown("**Racional detalhado**")
            for linha in linhas:
                _render_linha_racional_score(linha)
        else:
            st.caption("Racional do score v2 não disponível para este caso.")

    st.caption("Este diagnóstico segue princípios da CLT e prática jurídica comum no Brasil.")



def _render_painel_controle(relatorio, vm, case_id):
    st.caption("Visão rápida para decisão e execução")
    st.markdown(
        f"""
<div class="dpia-report-card" style="border: 2px solid {vm["risco_cor"]}; border-left: 8px solid {vm["risco_cor"]}; padding: 18px;">
  <div style="font-size:0.9rem; color:#cbd5e1; font-weight:700;">Status do Caso</div>
  <div style="margin-top:6px;"><strong>Diagnóstico:</strong> {relatorio.get("diagnostico", "")}</div>
  <div style="margin-top:10px; font-size:1.2rem; font-weight:800; color:{vm["risco_cor"]};">{vm["risco_visual"]}</div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("#### Impacto Financeiro")
    if vm["impacto_financeiro_estimado"] > 0:
        st.markdown(
            f"**Impacto Potencial Estimado:** {_format_reais_br(vm['impacto_financeiro_estimado'])}"
        )
        st.caption(
            "Estimativa baseada em salário, tempo de serviço e nível de risco. "
            "Não substitui cálculo detalhado de verbas."
        )
    else:
        render_barra_impacto_financeiro(vm["score_risco"])
    st.markdown(
        f"""
<div class="dpia-report-card" style="border: 1px solid #334155;">
  {relatorio.get("impacto_financeiro", "")}
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("#### Plano de Ação Interativo")
    plano_interativo = (vm["checklist"] or []) + (vm["proximos_passos"] or [])
    st.session_state.setdefault("checklist_estado_por_caso", {})
    st.session_state.setdefault("timeline_por_caso", {})
    case_key = case_id or "caso_sem_id"
    estado_caso = st.session_state["checklist_estado_por_caso"].setdefault(case_key, {})
    timeline_caso = st.session_state["timeline_por_caso"].setdefault(case_key, [])

    def _autor_logado():
        uid = st.session_state.get("user_id")
        perfil = str(st.session_state.get("perfil_usuario") or "usuário").strip().lower()
        perfil_label = perfil.capitalize() if perfil else "Usuário"
        nome = str(st.session_state.get("user_nome") or "").strip()
        if not nome and uid is not None:
            try:
                nome = str(obter_email_usuario(int(uid)) or "").strip()
            except Exception:
                nome = ""
        if not nome:
            nome = "Usuário"
        return f"{nome} ({perfil_label})"

    def _evento_timeline(autor: str, acao: str, origem: str = "checklist") -> dict:
        return {
            "timestamp": datetime.now().isoformat(),
            "autor": str(autor or "Sistema").strip() or "Sistema",
            "acao": str(acao or "").strip(),
            "origem": str(origem or "checklist").strip().lower(),
        }

    def _normalizar_evento(evento):
        if isinstance(evento, dict):
            return {
                "timestamp": str(evento.get("timestamp") or ""),
                "autor": str(evento.get("autor") or "Sistema"),
                "acao": str(evento.get("acao") or ""),
                "origem": str(evento.get("origem") or "sistema").strip().lower(),
            }
        return {
            "timestamp": "",
            "autor": "Sistema",
            "acao": str(evento or ""),
            "origem": "sistema",
        }

    def _formatar_evento(evento: dict) -> str:
        ts_raw = str(evento.get("timestamp") or "").strip()
        try:
            dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            ts_fmt = dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            ts_fmt = ts_raw or "--/--/---- --:--"
        autor = str(evento.get("autor") or "Sistema").strip() or "Sistema"
        acao = str(evento.get("acao") or "").strip() or "Evento registrado."
        origem = str(evento.get("origem") or "sistema").strip().lower()
        tag_map = {
            "checklist": "CHECKLIST",
            "documento": "DOCUMENTO",
            "sistema": "SISTEMA",
        }
        tag = tag_map.get(origem, origem.upper() or "SISTEMA")
        return f"[{ts_fmt}] [{tag}] {autor}: {acao}"

    if not plano_interativo:
        plano_interativo = [
            "Validar documentos críticos em até 48h",
            "Evitar decisão irreversível sem validação",
        ]

    total_acoes = len(plano_interativo)
    acoes_concluidas = sum(
        1
        for idx in range(total_acoes)
        if st.session_state.get(f"painel_{case_key}_acao_{idx}", False)
    )
    risco_projetado = calcular_reducao_risco(
        vm["nivel_risco"], acoes_concluidas, total_acoes
    )
    st.markdown(
        _html_reducao_risco_plano(
            vm["nivel_risco"],
            risco_projetado,
            acoes_concluidas,
            total_acoes,
        ),
        unsafe_allow_html=True,
    )

    for idx, item in enumerate(plano_interativo):
        item_id = f"acao_{idx}"
        checkbox_key = f"painel_{case_key}_{item_id}"
        valor_anterior = bool(estado_caso.get(item_id, False))
        marcado = st.checkbox(item, value=valor_anterior, key=checkbox_key)
        if marcado != valor_anterior:
            estado_caso[item_id] = marcado
            if marcado:
                timeline_caso.insert(
                    0,
                    _evento_timeline(
                        _autor_logado(),
                        f"Ação '{item}' marcada como concluída.",
                        origem="checklist",
                    ),
                )
                try:
                    registrar_evento_produto(
                        nome_evento="checklist_item_concluido",
                        usuario_id=st.session_state.get("user_id"),
                        empresa_id=st.session_state.get("empresa_id"),
                        metadados={
                            "case_id": case_key,
                            "item": str(item),
                            "item_id": item_id,
                        },
                    )
                except Exception:
                    pass
        if marcado:
            st.caption(f"~~{item}~~")

    st.markdown("#### Simulação de Decisão")
    st.markdown(
        _html_bloco_simulacao_decisao(vm["simulacao"], vm["nivel_risco"]),
        unsafe_allow_html=True,
    )

    st.markdown("#### Histórico do Caso")
    if timeline_caso:
        for evento in timeline_caso:
            st.markdown(f"- {_formatar_evento(_normalizar_evento(evento))}")
    else:
        st.caption("Sem eventos registrados para este caso.")


def render_relatorio_consultoria(relatorio, case_id=None):
    st.markdown("### Relatório de Consultoria")
    vm = _build_relatorio_view_model(relatorio)
    st.session_state.setdefault("controlador_abas_relatorio", "Painel de Controle")
    aba_selecionada = st.radio(
        "Navegação do Relatório",
        ["Painel de Controle", "Relatório Completo"],
        key="controlador_abas_relatorio",
        horizontal=True,
        label_visibility="collapsed",
    )
    if aba_selecionada == "Painel de Controle":
        _render_painel_controle(relatorio, vm, case_id)
    else:
        _render_relatorio_completo(relatorio, vm)
