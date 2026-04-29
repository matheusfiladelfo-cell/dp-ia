import streamlit as st
import json
import re

from banco import (
    criar_tabelas,
    obter_uso_usuario,
    salvar_feedback_resultado_analise,
    usuario_pode_acessar_plataforma,
)

from ia_chat import gerar_resposta_chat

from pdf_generator import gerar_pdf_parecer

from plano_service import (
    get_plano_usuario,
    pode_gerar_pdf,
    pode_fazer_analise,
    get_limite_analises,
    get_limite_empresas,
    pode_cadastrar_empresa,
)

from gerenciador_sessao import get_sessao

from application.analise_use_cases import (
    executar_analise_e_score,
    gerar_parecer_e_salvar_analise,
)
from application.auth_use_cases import (
    processar_login,
    processar_cadastro,
    processar_logout,
)
from application.empresa_use_cases import (
    listar_empresas_usuario,
    selecionar_empresa,
    cadastrar_empresa_usuario,
)
from application.dashboard_use_cases import gerar_insights_empresa_uc
from application.billing_use_cases import iniciar_checkout_plano
from application.subscription_use_cases import obter_status_assinatura
from application.onboarding_use_cases import obter_onboarding_status, finalizar_onboarding
from ui.layout import (
    render_app_theme,
    render_header,
    render_premium_card,
    render_result_intro_card,
    render_section_title,
    render_footer,
)
from ui.auth_views import render_auth_view
from ui.empresa_views import render_empresas_sidebar, render_nova_empresa_sidebar
from ui.insights_views import render_insights_empresa
from ui.usage_views import render_usage
from ui.analysis_views import (
    render_analysis_input,
    render_score,
    render_decisao_executiva,
    render_parecer_sections,
)
from ui.chat_views import render_chat_title, render_chat_input, render_chat_historico
from ui.onboarding_views import (
    render_onboarding_header,
    render_onboarding_hint_empresa,
    render_onboarding_hint_analise,
    render_onboarding_conclusao,
    render_jornada_versao_1,
)
from ui.pricing_views import render_planos_comparativo
from ui.billing_views import traduzir_erro_checkout, render_checkout_success
from ui.subscription_views import render_status_assinatura_card, render_cta_upgrade_free
from ui.empty_states import render_empty_state_plano_free_limitado


# 🔥 LIMPEZA TEXTO IA
def limpar_texto_ia(texto):
    if not texto:
        return ""

    linhas = texto.split("\n")

    linhas_limpas = []
    for linha in linhas:
        if any(p in linha.upper() for p in ["BLOCO 1", "BLOCO 2", "BLOCO 3"]):
            continue
        linhas_limpas.append(linha)

    return "\n".join(linhas_limpas).strip()


# 🔥 VALIDAÇÃO EMAIL
def email_valido(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


# 🔥 VALIDAÇÃO CNPJ
def validar_cnpj(cnpj):
    cnpj = ''.join(filter(str.isdigit, cnpj))

    if len(cnpj) != 14:
        return False

    if cnpj == cnpj[0] * 14:
        return False

    def calcular_digito(cnpj, peso):
        soma = sum(int(a) * b for a, b in zip(cnpj, peso))
        resto = soma % 11
        return '0' if resto < 2 else str(11 - resto)

    peso1 = [5,4,3,2,9,8,7,6,5,4,3,2]
    peso2 = [6] + peso1

    dig1 = calcular_digito(cnpj[:12], peso1)
    dig2 = calcular_digito(cnpj[:13], peso2)

    return cnpj[-2:] == dig1 + dig2


criar_tabelas()

st.set_page_config(page_title="DP-IA", layout="wide")
render_app_theme()


# =========================
# LOGIN
# =========================
if "user_id" not in st.session_state:
    if "auth_processing" not in st.session_state:
        st.session_state["auth_processing"] = False
    if "auth_pending_action" not in st.session_state:
        st.session_state["auth_pending_action"] = None

    landing_intent = st.session_state.pop("landing_intent", None)
    default_tab = "Criar conta" if landing_intent == "trial" else "Entrar"
    banner_text = (
        "Você está no fluxo de teste grátis. Crie sua conta para começar."
        if landing_intent == "trial"
        else None
    )

    aba, email, senha, acao_clicada = render_auth_view(
        default_tab=default_tab,
        banner_text=banner_text,
        is_processing=st.session_state["auth_processing"],
    )

    if acao_clicada and not st.session_state["auth_processing"]:
        st.session_state["auth_processing"] = True
        st.session_state["auth_pending_action"] = aba
        st.rerun()

    if email and not email_valido(email):
        st.warning("Digite um email válido")

    if st.session_state["auth_processing"]:
        acao_execucao = st.session_state.get("auth_pending_action") or aba

        if acao_execucao == "Entrar":
            with st.spinner("Carregando dados..."):
                if not email_valido(email):
                    st.error("Email inválido")
                    st.session_state["auth_processing"] = False
                    st.session_state["auth_pending_action"] = None
                    st.stop()

                if not processar_login(email, senha):
                    st.error("Não foi possível entrar. Verifique email e senha e tente novamente.")
                    st.session_state["auth_processing"] = False
                    st.session_state["auth_pending_action"] = None

        else:
            with st.spinner("Carregando dados..."):
                if not email_valido(email):
                    st.error("Digite um email válido")
                    st.session_state["auth_processing"] = False
                    st.session_state["auth_pending_action"] = None
                    st.stop()

                if processar_cadastro(email, senha):
                    st.success("Conta criada com sucesso. Faça login para continuar.")
                else:
                    st.error("Não foi possível criar a conta. Esse email pode já estar cadastrado.")

                st.session_state["auth_processing"] = False
                st.session_state["auth_pending_action"] = None

    st.stop()


usuario_id = st.session_state.user_id
if not usuario_pode_acessar_plataforma(usuario_id):
    del st.session_state["user_id"]
    st.rerun()

sessao = get_sessao()
plano = get_plano_usuario(usuario_id)


# =========================
# HEADER (ALTERADO)
# =========================
render_header()

# 🔥 CARD PREMIUM
render_premium_card()


# =========================
# LOGOUT
# =========================
if st.sidebar.button("🚪 Sair"):
    processar_logout()

st.sidebar.markdown(
    """
<div class="mp-empty-state" style="margin-top:8px;">
  <div style="font-weight:700; color:#93c5fd;">Trial comercial</div>
  <div style="font-size:0.86rem; color:#cbd5e1;">7 dias grátis ou 3 análises grátis para validar resultado real.</div>
</div>
""",
    unsafe_allow_html=True,
)
if st.sidebar.button("🚀 Upgrade Pro/Business", width="stretch", key="sidebar_upgrade_monetizacao"):
    st.info("Acesse a seção Upgrade Comercial para concluir assinatura.")


# =========================
# MODO
# =========================
modo = st.radio(
    "Modo de uso",
    ["🔵 Análise", "🟢 Conversa assistida"],
    horizontal=True
)


# =========================
# EMPRESAS
# =========================
empresas = listar_empresas_usuario(usuario_id)
empresa_selecionada, empresa_id = render_empresas_sidebar(empresas)
selecionar_empresa(empresa_id)
total_empresas = len(empresas)


nome_empresa, cnpj_empresa, cidade_empresa, estado_empresa, cadastrar_clicked = (
    render_nova_empresa_sidebar()
)

if cadastrar_clicked:

    if not nome_empresa:
        st.error("Informe o nome da empresa")
        st.stop()

    if not validar_cnpj(cnpj_empresa):
        st.error("CNPJ inválido. Revise o número informado e tente novamente.")
        st.stop()

    if not pode_cadastrar_empresa(usuario_id, total_empresas):
        limite_empresas_plano = get_limite_empresas(plano)
        st.error(f"Seu plano permite até {limite_empresas_plano} empresa(s).")
        st.stop()

    cadastrar_empresa_usuario(
        usuario_id,
        nome_empresa,
        cnpj_empresa,
        cidade_empresa,
        estado_empresa,
    )

    st.success("Empresa cadastrada")
    st.rerun()


# =========================
# INSIGHTS (MANTIDO)
# =========================
if empresa_id:
    insights = gerar_insights_empresa_uc(empresa_id)
    render_insights_empresa(insights)


# =========================
# USO
# =========================
uso = obter_uso_usuario(usuario_id)
limite = get_limite_analises(plano)

# =========================
# ONBOARDING
# =========================
onboarding_status = obter_onboarding_status(usuario_id, total_empresas, uso)
onboarding_ativo = onboarding_status.get("ativo", False)
if onboarding_ativo:
    render_onboarding_header(onboarding_status.get("etapa_atual", 1))

render_section_title("Resumo Comercial")
status_assinatura = obter_status_assinatura(usuario_id, plano)
render_status_assinatura_card(status_assinatura)
render_jornada_versao_1(total_empresas, uso, status_assinatura)
if plano == "FREE":
    if render_cta_upgrade_free():
        st.info("Escolha abaixo entre Pro ou Business para continuar o upgrade.")
    render_empty_state_plano_free_limitado()
render_usage(plano, uso, limite)
if not pode_gerar_pdf(plano):
    st.caption("PDF premium disponível apenas nos planos pagos (Pro e Premium).")

render_section_title("Upgrade Comercial")
render_planos_comparativo(plano)
provedor_pagamento = st.selectbox(
    "Gateway de pagamento",
    ["ASAAS", "MERCADO_PAGO"],
    help="Estrutura preparada para integração oficial com gateway brasileiro.",
)
col_upgrade_1, col_upgrade_2 = st.columns(2)
with col_upgrade_1:
    assinar_pro = st.button("💳 Assinar Pro • R$197", width="stretch")
with col_upgrade_2:
    assinar_premium = st.button("💳 Assinar Business • R$397", width="stretch")

if assinar_pro or assinar_premium:
    plano_destino = "PRO" if assinar_pro else "PREMIUM"
    checkout_resp = iniciar_checkout_plano(
        usuario_id=usuario_id,
        plano=plano_destino,
        provider=provedor_pagamento,
    )
    if checkout_resp.get("ok"):
        render_checkout_success(
            plano_destino=plano_destino,
            checkout_url=checkout_resp.get("checkout_url"),
            sandbox=checkout_resp.get("sandbox", False),
        )
    else:
        erro_amigavel = traduzir_erro_checkout(checkout_resp.get("error", "erro desconhecido"))
        st.error(erro_amigavel)


# =========================
# ANÁLISE (ALTERADA VISUAL)
# =========================
if modo == "🔵 Análise":
    render_section_title("Nova Análise")

    if onboarding_ativo and onboarding_status.get("etapa_atual") == 1:
        render_onboarding_hint_empresa()
    elif onboarding_ativo and onboarding_status.get("etapa_atual") == 2:
        render_onboarding_hint_analise()
    elif onboarding_ativo and onboarding_status.get("etapa_atual") == 3:
        render_onboarding_conclusao()
        finalizar_onboarding(usuario_id)

    st.markdown("**Sugestões rápidas**")
    s1, s2, s3, s4, s5 = st.columns(5)
    with s1:
        if st.button("Funcionário processou empresa", width="stretch", key="sug_processo"):
            st.session_state["analysis_input_prefill"] = (
                "Funcionário processou a empresa alegando verbas rescisórias e dano moral. "
                "Quero avaliar risco, defesa e estratégia de acordo."
            )
            st.rerun()
    with s2:
        if st.button("Pedido de demissão", width="stretch", key="sug_demissao"):
            st.session_state["analysis_input_prefill"] = (
                "Funcionário pediu demissão, mas há dúvida sobre estabilidade e documentação. "
                "Preciso avaliar risco jurídico e próximos passos."
            )
            st.rerun()
    with s3:
        if st.button("Gestante dispensada", width="stretch", key="sug_gestante"):
            st.session_state["analysis_input_prefill"] = (
                "Colaboradora gestante foi dispensada e não recebeu verbas corretamente. "
                "Preciso de avaliação estratégica de risco e exposição."
            )
            st.rerun()
    with s4:
        if st.button("Horas extras cobradas", width="stretch", key="sug_hora_extra"):
            st.session_state["analysis_input_prefill"] = (
                "Equipe está cobrando horas extras com base em registros de ponto. "
                "Quero avaliar probabilidade de condenação e faixa de impacto."
            )
            st.rerun()
    with s5:
        if st.button("Assédio alegado", width="stretch", key="sug_assedio"):
            st.session_state["analysis_input_prefill"] = (
                "Há alegação de assédio moral com possíveis testemunhas e mensagens. "
                "Preciso de parecer estratégico para decisão empresarial."
            )
            st.rerun()

    texto_usuario, analisar_clicked = render_analysis_input()

    if analisar_clicked:

        if not empresa_id:
            st.error("Selecione uma empresa para iniciar a análise.")
            st.stop()

        if not pode_fazer_analise(usuario_id):
            st.markdown(
                """
<div class="mp-empty-state">
  <div style="font-weight:700; color:#93c5fd;">Limite de análises atingido</div>
  <div style="color:#cbd5e1; font-size:0.9rem;">Faça upgrade para Pro/Business e continue com volume ampliado e PDF premium.</div>
</div>
""",
                unsafe_allow_html=True,
            )
            st.stop()

        with st.status("Analisando risco jurídico...", expanded=True) as status:
            analise_data = executar_analise_e_score(texto_usuario)
            status.write("Cruzando evidências...")
            dados = analise_data["dados"]
            resultado = analise_data["resultado"]
            score = analise_data["score"]
            probabilidade = analise_data["probabilidade"]
            nivel = analise_data["nivel"]
            motivos = analise_data["motivos"]
            status.write("Calculando exposição...")
            parecer = gerar_parecer_e_salvar_analise(
                texto_usuario=texto_usuario,
                usuario_id=usuario_id,
                empresa_id=empresa_id,
                dados=dados,
                resultado=resultado,
                score=score,
                probabilidade=probabilidade,
                nivel=nivel,
                motivos=motivos,
            )
            status.write("Montando estratégia...")
            status.update(label="Parecer estratégico pronto", state="complete")

        render_result_intro_card()
        render_section_title("Relatório Executivo")

        def cor_score(score):
            if score >= 80:
                return "🔴"
            elif score >= 60:
                return "🟠"
            elif score >= 40:
                return "🟡"
            else:
                return "🟢"

        render_score(score, probabilidade, nivel, cor_score)
        render_decisao_executiva(score)
        render_parecer_sections(parecer, limpar_texto_ia)
        st.markdown(
            """
<div class="mp-empty-state">
  <div style="font-weight:700; color:#93c5fd;">Quer escalar decisões com padrão premium?</div>
  <div style="color:#cbd5e1; font-size:0.9rem;">Upgrade para Pro/Business e libere PDF executivo, mais análises e prioridade operacional.</div>
</div>
""",
            unsafe_allow_html=True,
        )
        cta_result_1, cta_result_2 = st.columns(2)
        with cta_result_1:
            if st.button("🚀 Upgrade para Pro", width="stretch", key="result_upgrade_pro"):
                st.info("Use a seção Upgrade Comercial para concluir assinatura Pro.")
        with cta_result_2:
            if st.button("🏢 Upgrade para Business", width="stretch", key="result_upgrade_business"):
                st.info("Use a seção Upgrade Comercial para concluir assinatura Business.")

        st.markdown("### Coleta de Feedback do Resultado")
        schema_version = str(parecer.get("parecer_schema_version", "desconhecida"))
        feedback_signature = (
            f"{usuario_id}:{empresa_id}:{score}:{nivel}:{schema_version}:{resultado.get('risco', '')}:{resultado.get('pontuacao', '')}"
        )
        feedback_salvo = st.session_state.get("feedback_resultado_salvo") == feedback_signature

        if not feedback_salvo:
            with st.form("coleta_feedback_resultado", clear_on_submit=False):
                ajudou = st.radio(
                    "A resposta ajudou?",
                    options=["Sim", "Não"],
                    horizontal=True,
                )
                risco_coerente = st.radio(
                    "O risco parece coerente com o caso?",
                    options=["Sim", "Não"],
                    horizontal=True,
                )
                recomendacao_util = st.radio(
                    "A recomendação foi útil para decisão?",
                    options=["Sim", "Não"],
                    horizontal=True,
                )
                nota_geral = st.slider("Nota geral do resultado (1 a 5)", 1, 5, 4)
                observacoes = st.text_area(
                    "Comentário opcional para calibração futura",
                    placeholder="Ex: faltou considerar documento X ou o risco ficou acima do esperado.",
                    height=90,
                )
                enviar_feedback = st.form_submit_button(
                    "Salvar feedback para calibração",
                    width="stretch",
                )

                if enviar_feedback:
                    salvar_feedback_resultado_analise(
                        usuario_id=usuario_id,
                        empresa_id=empresa_id,
                        ajudou=(ajudou == "Sim"),
                        risco_coerente=(risco_coerente == "Sim"),
                        recomendacao_util=(recomendacao_util == "Sim"),
                        nota_geral=nota_geral,
                        score=score,
                        nivel=nivel,
                        parecer_schema_version=schema_version,
                        observacoes=observacoes.strip(),
                    )
                    st.session_state["feedback_resultado_salvo"] = feedback_signature
                    st.success("Feedback salvo com sucesso. Obrigado por ajudar na calibração do DP-IA.")
        else:
            st.caption("Feedback desta análise já foi registrado.")

        if pode_gerar_pdf(plano):
            pdf_path = gerar_pdf_parecer(
                empresa_selecionada,
                parecer,
                resultado
            )

            with open(pdf_path, "rb") as f:
                st.download_button("📄 Baixar PDF", f, file_name="parecer.pdf")

# =========================
# CHAT
# =========================
else:
    render_section_title("Conversa Assistida")
    render_chat_title()
    user_input = render_chat_input()

    if user_input:
        sessao.adicionar("user", user_input)

        resposta = gerar_resposta_chat(
            sessao.gerar_contexto_llm()
        )

        sessao.adicionar("assistant", resposta)
        st.rerun()

    render_chat_historico(sessao.historico)


# =========================
# DIREITOS (ALTERADO)
# =========================
render_footer()