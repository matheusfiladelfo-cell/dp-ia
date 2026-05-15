import streamlit as st
import json
import re
import os
import time
import uuid
from datetime import datetime, timedelta
from streamlit_option_menu import option_menu

from banco import (
    concluir_convite_primeiro_acesso,
    criar_tabelas,
    obter_email_usuario,
    obter_uso_usuario,
    incrementar_uso,
    registrar_admin_audit,
    registrar_falha_login,
    salvar_analise,
    salvar_feedback_resultado_analise,
    is_usuario_admin,
    usuario_pode_acessar_plataforma,
    validar_token_convite_primeiro_acesso,
    verificar_rate_limit_login,
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
    gerar_relatorio_consultoria,
    gerar_relatorio_final,
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
from application.permissoes_use_cases import (
    filtrar_casos_por_perfil,
    pode_acessar_gestao_equipe,
    pode_cadastrar_nova_empresa,
    pode_gerenciar_integracoes_payroll,
    pode_ver_dashboard_corporativo,
    resolver_perfil_na_empresa,
    usuario_pode_abrir_caso,
)
from application.dashboard_use_cases import gerar_insights_empresa_uc
from application.onboarding_use_cases import obter_onboarding_status, finalizar_onboarding
from ui.layout import (
    render_app_theme,
    render_header,
    render_result_intro_card,
    render_section_title,
    render_footer,
)
from ui.auth_views import (
    render_auth_view,
    render_esqueci_senha_view,
    render_primeiro_acesso_view,
    render_reset_password_view,
)
from ui.empresa_views import render_empresas_sidebar, render_nova_empresa_sidebar
from ui.insights_views import render_insights_empresa
from ui.usage_views import render_usage
from ui.chat_views import (
    render_chat_title,
    render_chat_document_upload,
    render_chat_input,
    render_chat_historico,
    render_relatorio_consultoria,
)
from ui.dashboard_corporativo_views import render_dashboard_corporativo
from ui.equipe_views import render_gestao_equipe
from ui.integracoes_views import render_integracoes
from ui.permissoes_views import render_resumo_permissoes
from ui.utils import carregar_css_customizado
from superadmin_panel import render_superadmin_panel
from ui.onboarding_views import (
    render_onboarding_header,
    render_onboarding_hint_empresa,
    render_onboarding_hint_analise,
    render_onboarding_conclusao,
)

SESSION_IDLE_TIMEOUT_MINUTES = int(os.getenv("SESSION_IDLE_TIMEOUT_MINUTES", "60"))


def _query_param_scalar(key: str) -> str:
    raw = st.query_params.get(key)
    if raw is None:
        return ""
    if isinstance(raw, (list, tuple)):
        return str(raw[0] if raw else "").strip()
    return str(raw).strip()


def _enforce_production_security_env():
    env = str(os.getenv("APP_ENV", "")).strip().lower()
    if env != "production":
        return

    missing = []
    if not str(os.getenv("ADMIN_MASTER_EMAIL", "")).strip():
        missing.append("ADMIN_MASTER_EMAIL")
    if not str(os.getenv("STREAMLIT_SERVER_COOKIE_SECRET", "")).strip():
        missing.append("STREAMLIT_SERVER_COOKIE_SECRET")

    asaas_token = str(os.getenv("ASAAS_WEBHOOK_TOKEN", "")).strip()
    mp_token = str(os.getenv("MP_WEBHOOK_TOKEN", "")).strip()
    if not asaas_token and not mp_token:
        missing.append("ASAAS_WEBHOOK_TOKEN ou MP_WEBHOOK_TOKEN")

    if missing:
        st.error(
            "Configuração de segurança obrigatória ausente para produção. "
            "Defina as variáveis: " + ", ".join(missing)
        )
        st.stop()


def _obter_ip_cliente():
    try:
        ctx = getattr(st, "context", None)
        headers = getattr(ctx, "headers", None) if ctx is not None else None
        if not headers:
            return None
        xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
        if xff:
            return str(xff).split(",")[0].strip()
        xrip = headers.get("x-real-ip") or headers.get("X-Real-IP")
        if xrip:
            return str(xrip).strip()
    except Exception:
        return None
    return None


def _check_session_idle_timeout():
    if "user_id" not in st.session_state:
        return

    now_ts = time.time()
    timeout_seconds = max(5, SESSION_IDLE_TIMEOUT_MINUTES) * 60
    last_ts = st.session_state.get("_last_activity_ts")

    if last_ts and (now_ts - float(last_ts)) > timeout_seconds:
        del st.session_state["user_id"]
        st.session_state["session_timeout_notice"] = True
        st.session_state.pop("_last_activity_ts", None)
        st.rerun()

    st.session_state["_last_activity_ts"] = now_ts


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


def _extrair_prazo_acao(texto_acao):
    texto = str(texto_acao or "").lower()
    match_horas = re.search(r"(\d+)\s*h", texto)
    if match_horas:
        return {"prazo_horas": int(match_horas.group(1))}
    match_dias = re.search(r"(\d+)\s*dias?", texto)
    if match_dias:
        return {"prazo_dias": int(match_dias.group(1))}
    return {}


def _estruturar_proximos_passos_com_prazo(passos):
    itens = []
    for passo in passos or []:
        registro = {"texto": str(passo or "").strip()}
        registro.update(_extrair_prazo_acao(passo))
        itens.append(registro)
    return itens


def _criar_evento_timeline(autor: str, acao: str, origem: str = "sistema") -> dict:
    return {
        "timestamp": datetime.now().isoformat(),
        "autor": str(autor or "Sistema").strip() or "Sistema",
        "acao": str(acao or "").strip(),
        "origem": str(origem or "sistema").strip().lower(),
    }


def render_template_email(dados: dict) -> str:
    template_path = os.path.join("templates", "email_alert.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception:
        return (
            f"<h3>Alerta de Prazo: Ação Requerida</h3>"
            f"<p><strong>Empresa:</strong> {dados.get('empresa_nome', 'Empresa')}</p>"
            f"<p>{dados.get('mensagem_alerta', '')}</p>"
        )

    substituicoes = {
        "{{empresa_nome}}": str(dados.get("empresa_nome", "Empresa")),
        "{{mensagem_alerta}}": str(dados.get("mensagem_alerta", "")),
        "{{severidade}}": str(dados.get("severidade", "média")),
        "{{app_url}}": str(dados.get("app_url", "#")),
        "{{logo_url}}": str(dados.get("logo_url", "")),
    }
    for marcador, valor in substituicoes.items():
        html = html.replace(marcador, valor)
    return html


def enviar_email_alerta(destinatario: str, assunto: str, dados_alerta: dict) -> bool:
    app_env = str(os.getenv("APP_ENV", "")).strip().lower()
    corpo_html = render_template_email(dados_alerta)

    if app_env == "development":
        st.info(f"MODO DEV: E-mail para {destinatario} com assunto '{assunto}'")
        with st.expander("Preview do e-mail (modo desenvolvimento)", expanded=False):
            st.markdown(corpo_html, unsafe_allow_html=True)
        return True

    try:
        api_key = st.secrets["sendgrid"]["api_key"]
    except Exception:
        return False

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        remetente = str(os.getenv("ALERT_FROM_EMAIL", "no-reply@mpconsultoria.com")).strip()
        mensagem = Mail(
            from_email=remetente,
            to_emails=str(destinatario).strip(),
            subject=str(assunto).strip(),
            html_content=corpo_html,
        )
        client = SendGridAPIClient(api_key)
        response = client.send(mensagem)
        return int(getattr(response, "status_code", 500)) < 400
    except Exception:
        return False


def verificar_prazos_pendentes(usuario_id_sessao=None, perfil_usuario_sessao=None):
    alertas = []
    agora = datetime.now()
    hoje_txt = agora.strftime("%Y-%m-%d")
    casos = filtrar_casos_por_perfil(
        st.session_state.get("casos_ativos_notificacao") or [],
        usuario_id_sessao,
        perfil_usuario_sessao,
    )
    checklist_por_caso = st.session_state.get("checklist_estado_por_caso") or {}
    st.session_state.setdefault("alertas_email_controle", {})
    controle_envio = st.session_state["alertas_email_controle"]

    for caso in casos:
        case_id = str(caso.get("case_id") or "")
        empresa_nome = str(caso.get("empresa_nome") or "Empresa")
        gerado_em_raw = str(caso.get("gerado_em") or "")
        if not gerado_em_raw:
            continue
        try:
            gerado_em = datetime.fromisoformat(gerado_em_raw)
        except ValueError:
            continue

        passos = caso.get("proximos_passos_estruturados") or []
        offset_checklist = int(caso.get("offset_checklist") or 0)
        estado_caso = checklist_por_caso.get(case_id) or {}
        for idx, passo in enumerate(passos):
            if estado_caso.get(f"acao_{offset_checklist + idx}"):
                continue

            prazo_horas = passo.get("prazo_horas")
            prazo_dias = passo.get("prazo_dias")
            if prazo_horas is None and prazo_dias is None:
                continue

            vencimento = gerado_em
            if prazo_horas is not None:
                vencimento = gerado_em + timedelta(hours=int(prazo_horas))
            elif prazo_dias is not None:
                vencimento = gerado_em + timedelta(days=int(prazo_dias))

            dias_restantes = (vencimento.date() - agora.date()).days
            if dias_restantes not in {0, 1}:
                continue

            when_txt = "vence hoje" if dias_restantes == 0 else "vence amanhã"
            severidade = "alta" if dias_restantes == 0 else "media"
            passo_txt = str(passo.get("texto", "sem descrição"))
            controle_key = f"{case_id}:{idx}:{passo_txt}"

            if dias_restantes == 0:
                ultimo_envio = controle_envio.get(controle_key)
                if ultimo_envio != hoje_txt:
                    destinatario = str(caso.get("usuario_email") or "").strip()
                    if destinatario:
                        app_url = str(os.getenv("APP_URL", "")).strip() or "#"
                        assunto = f"[M&P] Prazo crítico hoje - {empresa_nome}"
                        dados_alerta = {
                            "empresa_nome": empresa_nome,
                            "mensagem_alerta": f'Ação "{passo_txt}" vence hoje.',
                            "severidade": "alta",
                            "app_url": app_url,
                            "logo_url": str(os.getenv("LOGO_URL", "")).strip(),
                        }
                        if enviar_email_alerta(destinatario, assunto, dados_alerta):
                            controle_envio[controle_key] = hoje_txt

            alertas.append(
                {
                    "case_id": case_id,
                    "empresa_id": caso.get("empresa_id"),
                    "empresa_nome": empresa_nome,
                    "mensagem": f'Ação "{passo_txt}" {when_txt}.',
                    "severidade": severidade,
                }
            )

    return alertas


criar_tabelas()

st.set_page_config(page_title="DP-IA", layout="wide")
_enforce_production_security_env()
render_app_theme()
carregar_css_customizado()


# =========================
# LOGIN
# =========================
if "user_id" not in st.session_state:
    page_reset = _query_param_scalar("page").lower()
    token_redef = _query_param_scalar("token")
    if page_reset == "reset_password" and token_redef:
        render_reset_password_view(token_redef)
        st.stop()

    token_convite = str(st.query_params.get("convite", "") or "").strip()
    if token_convite:
        convite = validar_token_convite_primeiro_acesso(token_convite)
        if convite:
            email_convite = str(convite.get("email") or "")
            nova_senha, confirmar, enviar = render_primeiro_acesso_view(email_convite)
            if enviar:
                if len(str(nova_senha or "")) < 8:
                    st.error("A senha deve ter pelo menos 8 caracteres.")
                    st.stop()
                if nova_senha != confirmar:
                    st.error("As senhas não conferem.")
                    st.stop()
                ok_convite, msg_convite = concluir_convite_primeiro_acesso(token_convite, nova_senha)
                if ok_convite:
                    st.query_params.clear()
                    st.success(msg_convite)
                    st.info("Agora faça login com seu e-mail e a nova senha.")
                else:
                    st.error(msg_convite)
            st.stop()
        st.error("Este link de primeiro acesso é inválido ou expirou.")
        if st.button("Ir para login", key="primeiro_acesso_ir_login"):
            st.query_params.clear()
            st.rerun()
        st.stop()

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
    if st.session_state.pop("session_timeout_notice", False):
        st.info("Sua sessão expirou por inatividade. Faça login novamente para continuar.")

    if st.session_state.get("auth_view_mode") == "forgot_password":
        render_esqueci_senha_view()
        st.stop()

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
                ip_cliente = _obter_ip_cliente()
                if not email_valido(email):
                    st.error("Email inválido")
                    st.session_state["auth_processing"] = False
                    st.session_state["auth_pending_action"] = None
                    st.stop()

                permitido_login, _ = verificar_rate_limit_login(email, ip_cliente)
                if not permitido_login:
                    st.error("Não foi possível entrar. Verifique email e senha e tente novamente.")
                    st.session_state["auth_processing"] = False
                    st.session_state["auth_pending_action"] = None
                    st.stop()

                if not processar_login(email, senha):
                    registrar_falha_login(email, ip_cliente)
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

                cadastro = processar_cadastro(email, senha)
                if cadastro is True:
                    st.success("Conta criada com sucesso. Faça login para continuar.")
                elif cadastro == "duplicate":
                    st.error(
                        "Este e-mail já está cadastrado. Por favor, faça login ou recupere sua senha."
                    )
                else:
                    st.error("Não foi possível criar a conta. Tente novamente em instantes.")

                st.session_state["auth_processing"] = False
                st.session_state["auth_pending_action"] = None

    st.stop()


usuario_id = st.session_state.user_id
_check_session_idle_timeout()
usuario_id = st.session_state.user_id
if not usuario_pode_acessar_plataforma(usuario_id):
    del st.session_state["user_id"]
    st.rerun()

usuario_e_admin = is_usuario_admin(usuario_id)

sessao = get_sessao()
plano = get_plano_usuario(usuario_id)
st.session_state.setdefault("user_nome", obter_email_usuario(usuario_id) or "Usuário")


# =========================
# HEADER (ALTERADO)
# =========================
render_header()


# =========================
# LOGOUT
# =========================
if st.sidebar.button("🚪 Sair"):
    processar_logout()

st.sidebar.divider()

# =========================
# EMPRESAS
# =========================
empresas = listar_empresas_usuario(usuario_id)
empresa_selecionada, empresa_id = render_empresas_sidebar(empresas)
selecionar_empresa(empresa_id)
total_empresas = len(empresas)

perfil_usuario = resolver_perfil_na_empresa(usuario_id, empresa_id)
st.session_state["perfil_usuario"] = perfil_usuario
if empresa_id is not None and perfil_usuario is None:
    st.error(
        "Seu usuário não está vinculado a esta empresa na equipe. "
        "Peça um convite ao administrador."
    )
    st.stop()

render_resumo_permissoes(perfil_usuario)

st.session_state.setdefault("pagina_ativa", "Consultoria")
nav_opts = ["Consultoria", "Gestão de Equipe", "Integrações", "Dashboard Corporativo"]
# Bootstrap Icons (sem prefixo bi-) — alinhados ao streamlit-option-menu
icons_nav = ["kanban", "people", "plug", "view-stacked"]
paginas_validas = nav_opts + (["SuperAdminPanel"] if usuario_e_admin else [])
if st.session_state.get("pagina_ativa") not in paginas_validas:
    st.session_state["pagina_ativa"] = "Consultoria"

st.sidebar.divider()
with st.sidebar:
    if usuario_e_admin and st.session_state.get("pagina_ativa") == "SuperAdminPanel":
        st.info("Modo Super Admin ativo")
        if st.button("Voltar para operação", key="superadmin_back"):
            st.session_state["pagina_ativa"] = "Consultoria"
            st.rerun()
    else:
        st.markdown("### Navegação")
        st.caption("Consultoria, equipe, integrações e painéis.")
        st.divider()
        area_principal = option_menu(
            menu_title=None,
            options=nav_opts,
            icons=icons_nav,
            menu_icon="layers",
            default_index=nav_opts.index(st.session_state["pagina_ativa"]),
            key="menu_navegacao_mp",
            styles={
                "container": {
                    "padding": "0.15rem 0 0.35rem 0!important",
                    "background-color": "transparent",
                },
                "icon": {
                    "color": "#60a5fa",
                    "font-size": "1.08rem",
                    "opacity": "0.95",
                },
                "nav-link": {
                    "font-size": "0.94rem",
                    "text-align": "left",
                    "margin": "0.12rem 0",
                    "padding": "0.5rem 0.65rem",
                    "border-radius": "10px",
                    "color": "#cbd5e1",
                    "--hover-color": "rgba(30, 41, 59, 0.85)",
                },
                "nav-link-selected": {
                    "background-color": "rgba(37, 99, 235, 0.28)",
                    "color": "#fffbeb",
                    "font-weight": "600",
                    "border-left": "3px solid #fbbf24",
                    "padding-left": "0.55rem",
                    "box-shadow": "inset 0 0 0 1px rgba(251, 191, 36, 0.12)",
                },
            },
        )
        st.session_state["pagina_ativa"] = area_principal

    if usuario_e_admin:
        st.divider()
        st.markdown("### Super Admin")
        st.caption("Gestão global da plataforma.")
        if st.button("Painel de Controle Global", key="btn_superadmin_panel", icon="🛡️"):
            st.session_state["pagina_ativa"] = "SuperAdminPanel"
            st.rerun()

area_principal = st.session_state.get("pagina_ativa", "Consultoria")

st.sidebar.divider()

alertas_prazo = verificar_prazos_pendentes(usuario_id, perfil_usuario)
if alertas_prazo:
    with st.sidebar.expander(f"🔔 Alertas ({len(alertas_prazo)})", expanded=False):
        for idx_alerta, alerta in enumerate(alertas_prazo):
            indicador = "🔴" if alerta.get("severidade") == "alta" else "🟡"
            st.write(f'{indicador} {alerta["empresa_nome"]}: {alerta["mensagem"]}')
            if st.button(
                "Ir para o caso",
                key=f'goto_case_{alerta["case_id"]}_{idx_alerta}',
                width="stretch",
            ):
                st.session_state["caso_selecionado_para_exibicao"] = alerta["case_id"]
                st.session_state["empresa_selecionada_alerta"] = alerta.get("empresa_id")
                st.session_state["controlador_abas_relatorio"] = "Painel de Controle"
                st.rerun()
else:
    st.sidebar.caption("🔔 Alertas (0)")


mostrar_nova_empresa = (total_empresas == 0) or pode_cadastrar_nova_empresa(perfil_usuario)
if mostrar_nova_empresa:
    nome_empresa, cnpj_empresa, cidade_empresa, estado_empresa, cadastrar_clicked = (
        render_nova_empresa_sidebar()
    )
else:
    st.sidebar.markdown("---")
    st.sidebar.caption("Novas empresas: apenas gestor ou administrador da equipe.")
    nome_empresa, cnpj_empresa, cidade_empresa, estado_empresa, cadastrar_clicked = (
        "",
        "",
        "",
        "",
        False,
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

if area_principal == "SuperAdminPanel":
    if usuario_e_admin:
        render_superadmin_panel(user_id=usuario_id, email=obter_email_usuario(usuario_id))
    else:
        registrar_admin_audit(
            admin_user_id=usuario_id,
            action="superadmin_access_denied_app",
            target_type="superadmin_panel",
            target_id="app.py",
            details=f"user_id={usuario_id}",
        )
        st.error("Acesso negado.")
        st.warning("Esta tentativa de acesso foi registrada.")
    render_footer()
    st.stop()


# =========================
# INSIGHTS (MANTIDO)
# =========================
if empresa_id and area_principal == "Consultoria":
    filtro_insights = usuario_id if perfil_usuario == "colaborador" else None
    insights = gerar_insights_empresa_uc(empresa_id, criado_por_usuario_id=filtro_insights)
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

render_usage(plano, uso, limite)

if area_principal == "Gestão de Equipe":
    if not pode_acessar_gestao_equipe(perfil_usuario):
        st.error("Acesso negado.")
        st.stop()
    render_gestao_equipe(usuario_id, empresa_id, empresa_selecionada)
    render_footer()
    st.stop()

if area_principal == "Integrações":
    if not pode_gerenciar_integracoes_payroll(perfil_usuario):
        st.error("Acesso negado.")
        st.stop()
    if not empresa_id:
        st.warning("Selecione uma empresa para configurar integrações.")
        st.stop()
    render_integracoes(usuario_id, empresa_id, empresa_selecionada)
    render_footer()
    st.stop()

if area_principal == "Dashboard Corporativo":
    if not pode_ver_dashboard_corporativo(perfil_usuario):
        st.error("Acesso negado.")
        st.stop()
    render_dashboard_corporativo(
        empresa_id,
        empresa_selecionada,
        usuario_visualizador_id=usuario_id,
        perfil_visualizador=perfil_usuario,
    )
    render_footer()
    st.stop()


# =========================
# CONVERSA ASSISTIDA (FLUXO PRINCIPAL)
# =========================
render_section_title("Conversa Assistida")
render_chat_title()
render_chat_document_upload(sessao, usuario_id=usuario_id, empresa_id=empresa_id)
user_input = render_chat_input()

if user_input:
    st.session_state["relatorio_consultoria_gerado"] = False
    st.session_state.pop("auto_trigger_toast_sig", None)
    st.session_state.pop("relatorio_consultoria_payload", None)
    st.session_state.pop("parecer_pdf_payload", None)
    st.session_state.pop("resultado_pdf_payload", None)
    sessao.adicionar("user", user_input)
    resposta = gerar_resposta_chat(sessao.gerar_contexto_llm())
    sessao.adicionar("assistant", resposta)
    st.rerun()

render_chat_historico(sessao, empresa_id=empresa_id, usuario_id=usuario_id)

sinais = sessao.obter_sinais_identificados()
if sinais:
    st.caption("Sinais identificados: " + ", ".join(sinais))

interacoes_suficientes = sessao.total_interacoes_usuario() >= 3
pergunta_pendente = sessao.ha_pergunta_pendente()
auto_trigger = interacoes_suficientes and not pergunta_pendente

if auto_trigger:
    st.caption("🟢 Pronto para gerar relatório")
else:
    st.caption("🟡 Coletando informações")

gerar_relatorio_clicked = st.button(
    "Gerar parecer estratégico completo",
    width="stretch",
    type="primary",
    key="gerar_relatorio_consultoria",
)

deve_gerar_relatorio = gerar_relatorio_clicked or (
    auto_trigger and not st.session_state.get("relatorio_consultoria_gerado")
)
if auto_trigger and not st.session_state.get("relatorio_consultoria_gerado"):
    auto_sig = f"{sessao.total_interacoes_usuario()}:{len(sessao.historico)}"
    if st.session_state.get("auto_trigger_toast_sig") != auto_sig:
        st.toast("Detectamos que a conversa amadureceu. Preparando para gerar o parecer estratégico...")
        st.session_state["auto_trigger_toast_sig"] = auto_sig
if deve_gerar_relatorio:
    if not empresa_id:
        st.error("Selecione uma empresa para gerar o relatório de consultoria.")
        st.stop()

    if not pode_fazer_analise(usuario_id):
        st.markdown(
            """
<div class="mp-empty-state">
  <div style="font-weight:700; color:#93c5fd;">Limite de análises atingido</div>
  <div style="color:#cbd5e1; font-size:0.9rem;">Limite atual atingido para esta conta. Procure a área comercial para revisão de plano.</div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.stop()

    conversa = sessao.historico_completo_texto()
    if not conversa.strip():
        st.warning("Inicie a conversa antes de gerar o relatório.")
        st.stop()

    with st.status("Gerando relatório de consultoria...", expanded=True) as status:
        status.write("Extraindo contexto da conversa...")
        filtro_hist = usuario_id if perfil_usuario == "colaborador" else None
        stub_fatos_id = st.session_state.get("ultimo_stub_analise_id_fatos_validados")
        relatorio = gerar_relatorio_consultoria(
            conversa,
            empresa_id=empresa_id,
            criado_por_usuario_id=filtro_hist,
            analise_id_stub_fatos=stub_fatos_id,
        )
        status.write("Consolidando diagnóstico executivo...")
        status.update(label="Relatório de consultoria pronto", state="complete")

    risco_relatorio = relatorio.get("fluxo_consulta", {}).get("risco", "INCONCLUSIVO")
    pontuacao_relatorio = int(relatorio.get("fluxo_consulta", {}).get("pontuacao") or 0)
    parecer_pdf = {
        "diagnostico": relatorio.get("diagnostico", ""),
        "fundamentacao": relatorio.get("risco_juridico", ""),
        "impactos": relatorio.get("estrategia", ""),
        "impacto_financeiro": 0,
        "recomendacao": relatorio.get("plano_acao", ""),
        "risco": risco_relatorio,
    }
    resultado_pdf = {
        "risco": risco_relatorio,
        "pontuacao": pontuacao_relatorio,
    }

    incrementar_uso(usuario_id)
    analise_id_relatorio = salvar_analise(
        empresa_id,
        "consultoria_conversa",
        risco_relatorio,
        pontuacao_relatorio,
        {"conversa": conversa, "sinais_identificados": sinais},
        {"origem_fluxo": "conversa_assistida", **resultado_pdf},
        parecer_pdf,
        criado_por_usuario_id=usuario_id,
    )

    st.session_state["relatorio_consultoria_gerado"] = True
    st.session_state["relatorio_consultoria_payload"] = relatorio
    st.session_state["parecer_pdf_payload"] = parecer_pdf
    st.session_state["resultado_pdf_payload"] = resultado_pdf
    case_id = f"empresa_{empresa_id}_{uuid.uuid4()}"
    st.session_state["relatorio_consultoria_case_id"] = case_id
    st.session_state.setdefault("checklist_estado_por_caso", {})
    st.session_state["checklist_estado_por_caso"][case_id] = {}
    st.session_state.setdefault("timeline_por_caso", {})
    st.session_state["timeline_por_caso"][case_id] = [
        _criar_evento_timeline("Sistema", "Relatório de Consultoria gerado.", origem="sistema")
    ]
    st.session_state.setdefault("casos_ativos_notificacao", [])
    proximos_passos = relatorio.get("proximos_passos_recomendados") or []
    checklist_base = relatorio.get("plano_acao_checklist") or []
    st.session_state["casos_ativos_notificacao"] = [
        c for c in st.session_state["casos_ativos_notificacao"] if c.get("case_id") != case_id
    ]
    st.session_state["casos_ativos_notificacao"].append(
        {
            "case_id": case_id,
            "empresa_id": empresa_id,
            "empresa_nome": empresa_selecionada,
            "usuario_email": obter_email_usuario(usuario_id),
            "criado_por_usuario_id": usuario_id,
            "analise_id": analise_id_relatorio,
            "gerado_em": datetime.now().isoformat(),
            "offset_checklist": len(checklist_base),
            "proximos_passos_estruturados": _estruturar_proximos_passos_com_prazo(proximos_passos),
            "relatorio_payload": relatorio,
            "parecer_pdf_payload": parecer_pdf,
            "resultado_pdf_payload": resultado_pdf,
        }
    )
    st.rerun()

case_id_selecionado = st.session_state.get("caso_selecionado_para_exibicao")
if case_id_selecionado:
    casos_ativos = st.session_state.get("casos_ativos_notificacao") or []
    caso_alvo = next((c for c in casos_ativos if c.get("case_id") == case_id_selecionado), None)
    if caso_alvo and not usuario_pode_abrir_caso(caso_alvo, usuario_id, perfil_usuario):
        st.warning("Você não tem permissão para abrir este caso.")
        st.session_state.pop("caso_selecionado_para_exibicao", None)
    elif caso_alvo:
        st.session_state["relatorio_consultoria_case_id"] = case_id_selecionado
        st.session_state["relatorio_consultoria_payload"] = caso_alvo.get("relatorio_payload")
        st.session_state["parecer_pdf_payload"] = caso_alvo.get("parecer_pdf_payload")
        st.session_state["resultado_pdf_payload"] = caso_alvo.get("resultado_pdf_payload")
        st.session_state["relatorio_consultoria_gerado"] = True
        st.session_state.pop("caso_selecionado_para_exibicao", None)
        st.rerun()
    st.session_state.pop("caso_selecionado_para_exibicao", None)

if st.session_state.get("relatorio_consultoria_payload"):
    render_result_intro_card()
    render_relatorio_consultoria(
        st.session_state["relatorio_consultoria_payload"],
        case_id=st.session_state.get("relatorio_consultoria_case_id"),
    )

    if pode_gerar_pdf(plano):
        pdf_path = gerar_pdf_parecer(
            empresa_selecionada,
            st.session_state["parecer_pdf_payload"],
            st.session_state["resultado_pdf_payload"],
        )
        with open(pdf_path, "rb") as f:
            st.download_button("📄 Baixar PDF", f, file_name="relatorio_consultoria.pdf")


# =========================
# DIREITOS (ALTERADO)
# =========================
render_footer()