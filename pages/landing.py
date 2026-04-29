import os
import re
from html import escape as html_escape
from urllib.parse import quote

import streamlit as st

from banco import criar_tabelas, salvar_lead_demonstracao
from config_pricing import STARTER, PRO, BUSINESS
from ui.theme import apply_global_theme

# Número WhatsApp (apenas dígitos, ex.: 5511987654321). Sobrescreva com MP_WHATSAPP_PHONE.
_MP_WHATSAPP_DEFAULT = "5511999999999"
MP_WHATSAPP_PHONE = "".join(
    c for c in os.environ.get("MP_WHATSAPP_PHONE", _MP_WHATSAPP_DEFAULT) if c.isdigit()
) or _MP_WHATSAPP_DEFAULT

MP_WHATSAPP_MESSAGE = (
    "Olá, quero conhecer a plataforma M&P Consultoria Trabalhista e agendar uma demonstração."
)

MP_WA_URGENCY = "Agenda limitada para demonstrações esta semana"


def _mp_whatsapp_url():
    return f"https://wa.me/{MP_WHATSAPP_PHONE}?text={quote(MP_WHATSAPP_MESSAGE, safe='')}"


def _whatsapp_strategic_block(button_key: str, show_urgency: bool = True):
    if show_urgency:
        st.markdown(
            f'<p class="mp-wa-urgency">{MP_WA_URGENCY}</p>',
            unsafe_allow_html=True,
        )
    st.link_button(
        "Falar com especialista agora",
        _mp_whatsapp_url(),
        width="stretch",
        key=button_key,
        help="Abre o WhatsApp com mensagem pronta para demonstração.",
    )


st.set_page_config(page_title="DP-IA | Landing", layout="wide")
apply_global_theme()
criar_tabelas()

if "landing_lead_saved" not in st.session_state:
    st.session_state.landing_lead_saved = False


def _ir_para_login():
    st.session_state["landing_intent"] = "login"
    st.switch_page("app.py")


def _ir_para_teste_gratis():
    st.session_state["landing_intent"] = "trial"
    st.switch_page("app.py")

st.markdown(
    """
<style>
    .mp-wrap { max-width: 1080px; margin: 0 auto; padding-bottom: 2rem; }
    .mp-hero {
        margin-top: 0.7rem;
        padding: 2.1rem 1.7rem;
        border-radius: 22px;
        border: 1px solid rgba(96, 165, 250, 0.35);
        background: linear-gradient(145deg, rgba(15,23,42,0.95), rgba(17,24,39,0.96));
        box-shadow: 0 0 0 1px rgba(59,130,246,0.14), 0 26px 60px rgba(2,6,23,0.5), 0 0 45px rgba(59,130,246,0.18);
        color: #f8fafc;
        animation: mpUp 0.35s ease;
    }
    .mp-brand { font-size: 0.95rem; color: #93c5fd; font-weight: 700; margin-bottom: 0.55rem; }
    .mp-hero h1 { margin: 0; font-size: 2.22rem; line-height: 1.17; color: #f8fafc; }
    .mp-hero p { margin-top: 0.75rem; color: #cbd5e1; font-size: 1.06rem; }
    .mp-proof {
        margin-top: 0.8rem;
        display: inline-block;
        padding: 0.38rem 0.7rem;
        border-radius: 999px;
        border: 1px solid rgba(212,175,55,0.45);
        color: #f8fafc;
        background: rgba(30,41,59,0.62);
        font-size: 0.82rem;
        font-weight: 700;
    }
    .mp-section-title {
        margin: 1.65rem 0 0.72rem 0;
        color: #ffffff;
        font-size: 1.22rem;
        font-weight: 700;
        letter-spacing: 0.01em;
    }
    .mp-card {
        background: rgba(15,23,42,.88);
        border: 1px solid rgba(148, 163, 184, 0.24);
        border-radius: 16px;
        padding: 1rem;
        color: #f8fafc;
        height: 100%;
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }
    .mp-card:hover {
        transform: translateY(-2px);
        border-color: rgba(96,165,250,0.40);
        box-shadow: 0 10px 24px rgba(2,6,23,0.32), 0 0 18px rgba(59,130,246,0.14);
    }
    .mp-card p { color: #cbd5e1; margin-bottom: 0; }
    .mp-step {
        border-left: 3px solid rgba(96,165,250,0.62);
    }
    .mp-pricing {
        border: 1px solid rgba(148,163,184,0.24);
        border-radius: 16px;
        background: rgba(15,23,42,.88);
        padding: 1rem;
        color: #f8fafc;
    }
    .mp-pricing.mp-pricing-featured {
        border: 1px solid rgba(212,175,55,0.55);
        background: linear-gradient(165deg, rgba(30,41,59,0.95), rgba(30,58,138,0.42));
        box-shadow: 0 0 0 1px rgba(59,130,246,0.22), 0 18px 40px rgba(2,6,23,0.45), 0 0 28px rgba(212,175,55,0.12);
        transform: scale(1.02);
    }
    .mp-pricing .badge {
        display: inline-block;
        padding: 0.2rem 0.5rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        margin-bottom: 0.45rem;
        border: 1px solid rgba(96,165,250,0.4);
        color: #93c5fd;
    }
    .mp-pricing.mp-pricing-featured .badge {
        border-color: rgba(212,175,55,0.55);
        color: #fde68a;
        background: rgba(212,175,55,0.12);
    }
    .mp-authority {
        margin: 1.35rem 0 0.5rem 0;
        padding: 1rem 1.15rem;
        border-radius: 16px;
        border: 1px solid rgba(96,165,250,0.28);
        background: rgba(15,23,42,.88);
        text-align: center;
        color: #f8fafc;
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .mp-roi {
        margin: 0.35rem 0 0.15rem 0;
        padding: 1.4rem 1.5rem;
        border-radius: 18px;
        border: 1px solid rgba(212,175,55,0.42);
        background: linear-gradient(152deg, rgba(15,23,42,0.96), rgba(30,58,138,0.28));
        box-shadow: 0 14px 40px rgba(2,6,23,0.42), 0 0 28px rgba(212,175,55,0.1);
    }
    .mp-roi .mp-roi-line1 {
        margin: 0;
        font-size: 1.14rem;
        font-weight: 800;
        line-height: 1.38;
        color: #f8fafc;
    }
    .mp-roi .mp-roi-line2 {
        margin: 0.85rem 0 0 0;
        font-size: 1.06rem;
        font-weight: 700;
        color: #fde68a;
        letter-spacing: 0.02em;
    }
    .mp-institutional {
        margin: 1rem 0 0.35rem 0;
        padding: 1.05rem 1.2rem;
        border-radius: 16px;
        border: 1px solid rgba(148,163,184,0.22);
        background: rgba(15,23,42,0.55);
        text-align: center;
        color: #cbd5e1;
        font-size: 0.98rem;
        font-weight: 600;
        line-height: 1.5;
        font-style: italic;
    }
    .mp-beta {
        margin: 0.85rem 0 0.45rem 0;
        padding: 1.05rem 1.25rem;
        border-radius: 16px;
        border: 1px solid rgba(212,175,55,0.48);
        background: linear-gradient(125deg, rgba(30,41,59,0.92), rgba(76,29,149,0.22));
        text-align: center;
        color: #fef9c3;
        font-size: 1.02rem;
        font-weight: 800;
        letter-spacing: 0.03em;
        box-shadow: 0 10px 28px rgba(2,6,23,0.38);
    }
    .mp-objection {
        border: 1px solid rgba(148,163,184,0.22);
        border-radius: 14px;
        background: rgba(15,23,42,.88);
        padding: 0.92rem 1rem;
        height: 100%;
    }
    .mp-objection strong {
        display: block;
        color: #ffffff;
        font-size: 0.95rem;
        margin-bottom: 0.45rem;
        font-weight: 700;
    }
    .mp-objection p {
        margin: 0;
        color: #cbd5e1;
        font-size: 0.88rem;
        line-height: 1.48;
    }
    .mp-faq {
        border: 1px solid rgba(148,163,184,0.24);
        border-radius: 12px;
        background: rgba(15,23,42,.88);
        padding: 0.85rem 0.95rem;
        margin-bottom: 0.55rem;
    }
    .mp-final {
        margin-top: 1.25rem;
        padding: 1.2rem 1.35rem;
        border-radius: 16px;
        background: linear-gradient(135deg, rgba(15,23,42,.88), rgba(30,64,175,0.35));
        border: 1px solid rgba(212,175,55,0.30);
        color: #f8fafc;
    }
    @keyframes mpUp {
        from { opacity: 0.6; transform: translateY(6px); }
        to { opacity: 1; transform: translateY(0px); }
    }
    @media (max-width: 768px) {
        .mp-hero h1 { font-size: 1.62rem; }
        .mp-hero p { font-size: 0.95rem; }
    }
    form[data-testid="stForm"] {
        border: 1px solid rgba(96,165,250,0.38) !important;
        border-radius: 18px !important;
        padding: 1.35rem 1.45rem 1.5rem 1.45rem !important;
        margin: 0.75rem 0 1.25rem 0 !important;
        background: linear-gradient(165deg, rgba(15,23,42,0.96), rgba(30,41,59,0.9)) !important;
        box-shadow: 0 14px 36px rgba(2,6,23,0.38), 0 0 24px rgba(59,130,246,0.1);
    }
    .mp-lead-hint {
        color: #94a3b8;
        font-size: 0.9rem;
        margin: -0.35rem 0 0.85rem 0;
        line-height: 1.45;
    }
    .mp-lead-success {
        border: 1px solid rgba(52,211,153,0.5);
        border-radius: 18px;
        padding: 1.35rem 1.45rem;
        margin: 0.85rem 0 1.25rem 0;
        background: linear-gradient(145deg, rgba(15,23,42,0.95), rgba(6,78,59,0.35));
        box-shadow: 0 12px 32px rgba(2,6,23,0.35), 0 0 22px rgba(52,211,153,0.12);
    }
    .mp-lead-success .mp-lead-success-title {
        color: #ffffff;
        font-size: 1.18rem;
        font-weight: 800;
        margin: 0 0 0.4rem 0;
        letter-spacing: 0.01em;
    }
    .mp-lead-success .mp-lead-success-sub {
        color: #cbd5e1;
        font-size: 1.02rem;
        margin: 0;
    }
    .mp-wa-urgency {
        color: #fcd34d;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin: 0.5rem 0 0.45rem 0;
        opacity: 0.92;
    }
    a.mp-wa-fab {
        position: fixed;
        right: 1.15rem;
        bottom: 1.15rem;
        z-index: 100002;
        width: 56px;
        height: 56px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(145deg, rgba(15,23,42,0.97), rgba(22,101,52,0.45));
        border: 1px solid rgba(52,211,153,0.42);
        box-shadow: 0 10px 28px rgba(2,6,23,0.55), 0 0 20px rgba(16,185,129,0.15);
        color: #ecfdf5;
        text-decoration: none;
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }
    a.mp-wa-fab:hover {
        transform: translateY(-2px) scale(1.03);
        border-color: rgba(52,211,153,0.65);
        box-shadow: 0 14px 36px rgba(2,6,23,0.6), 0 0 26px rgba(16,185,129,0.28);
    }
    a.mp-wa-fab svg {
        display: block;
    }
    .mp-wa-fab-pulse {
        position: fixed;
        right: 1.15rem;
        bottom: 1.15rem;
        width: 56px;
        height: 56px;
        border-radius: 50%;
        z-index: 100001;
        pointer-events: none;
        border: 1px solid rgba(52,211,153,0.25);
        animation: mpWaPulse 2.6s ease-in-out infinite;
    }
    @keyframes mpWaPulse {
        0%, 100% { transform: scale(1); opacity: 0.35; }
        50% { transform: scale(1.12); opacity: 0.08; }
    }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="mp-wrap">
<div class="mp-hero">
    <div class="mp-brand">⚖️ M&P Consultoria Trabalhista</div>
    <h1>Reduza riscos trabalhistas e tome decisões empresariais com segurança.</h1>
    <p>Plataforma estratégica para empresários, RH e contadores.</p>
    <div class="mp-proof">Sem cartão • Resultado imediato • 7 dias grátis</div>
</div>
""",
    unsafe_allow_html=True,
)

cta_col1, cta_col2 = st.columns(2)
with cta_col1:
    if st.button("Agendar Demonstração", key="landing_specialist_btn_top", type="primary", width="stretch"):
        _ir_para_login()
with cta_col2:
    if st.button("Teste Estratégico Gratuito", key="landing_trial_btn_top", width="stretch"):
        _ir_para_teste_gratis()

_whatsapp_strategic_block("landing_wa_cta_hero")

st.markdown('<div class="mp-section-title">Benefícios</div>', unsafe_allow_html=True)
b1, b2, b3, b4 = st.columns(4)
b1.markdown('<div class="mp-card"><h4>🛡️ Evite passivos trabalhistas</h4><p>Antecipe riscos e proteja o caixa da empresa.</p></div>', unsafe_allow_html=True)
b2.markdown('<div class="mp-card"><h4>⚡ Decida rápido</h4><p>Análise objetiva para você agir no timing certo.</p></div>', unsafe_allow_html=True)
b3.markdown('<div class="mp-card"><h4>⚖️ Mais segurança jurídica</h4><p>Decisões alinhadas à realidade trabalhista.</p></div>', unsafe_allow_html=True)
b4.markdown('<div class="mp-card"><h4>💰 Economia real</h4><p>Menos retrabalho, multas e negociações mal feitas.</p></div>', unsafe_allow_html=True)

st.markdown('<div class="mp-section-title">Como funciona</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
c1.markdown('<div class="mp-card mp-step"><h4>1) Descreva o caso</h4><p>Informe o cenário trabalhista em linguagem simples.</p></div>', unsafe_allow_html=True)
c2.markdown('<div class="mp-card mp-step"><h4>2) Receba análise estratégica</h4><p>Risco, exposição e recomendação objetiva para decisão.</p></div>', unsafe_allow_html=True)
c3.markdown('<div class="mp-card mp-step"><h4>3) Decida com segurança</h4><p>Aja com clareza e reduza chance de erro caro.</p></div>', unsafe_allow_html=True)

st.markdown('<div class="mp-section-title">ROI</div>', unsafe_allow_html=True)
st.markdown(
    """
<div class="mp-roi">
  <p class="mp-roi-line1">Um único passivo trabalhista pode custar milhares.</p>
  <p class="mp-roi-line2">Prevenir custa menos.</p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="mp-section-title">Benefício financeiro</div>', unsafe_allow_html=True)
st.markdown(
    """
<div class="mp-card">
  <h4>💰 Uma decisão certa pode economizar milhares.</h4>
  <p>Ao antecipar risco trabalhista, sua empresa reduz custos com acordos mal estruturados, condenações e retrabalho jurídico.</p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="mp-section-title">Para quem é</div>', unsafe_allow_html=True)
pq1, pq2, pq3, pq4 = st.columns(4)
pq1.markdown('<div class="mp-card"><strong>Empresas</strong></div>', unsafe_allow_html=True)
pq2.markdown('<div class="mp-card"><strong>RH</strong></div>', unsafe_allow_html=True)
pq3.markdown('<div class="mp-card"><strong>Contadores</strong></div>', unsafe_allow_html=True)
pq4.markdown('<div class="mp-card"><strong>Franquias</strong></div>', unsafe_allow_html=True)

st.markdown(
    '<div class="mp-authority">Desenvolvido para empresas modernas</div>',
    unsafe_allow_html=True,
)

st.markdown('<div class="mp-section-title">Prova social</div>', unsafe_allow_html=True)
ps1, ps2 = st.columns(2)
ps1.markdown('<div class="mp-card"><h4>⭐ “Agora temos direção clara em casos críticos.”</h4><p>Coordenadora de RH, indústria com múltiplas unidades.</p></div>', unsafe_allow_html=True)
ps2.markdown('<div class="mp-card"><h4>⭐ “Reduziu retrabalho entre RH e jurídico.”</h4><p>Controller, rede de serviços com expansão nacional.</p></div>', unsafe_allow_html=True)

st.markdown(
    '<div class="mp-institutional">Empresários, RHs e contadores buscam soluções modernas para reduzir riscos.</div>',
    unsafe_allow_html=True,
)

st.markdown('<div class="mp-section-title">Planos resumidos</div>', unsafe_allow_html=True)
p1, p2, p3 = st.columns(3)
p1.markdown(f'<div class="mp-pricing"><div class="badge">START</div><h4>Starter</h4><p><b>R${STARTER}/mês</b></p><p>Trial: 7 dias grátis ou 3 análises.</p></div>', unsafe_allow_html=True)
p2.markdown(f'<div class="mp-pricing mp-pricing-featured"><div class="badge">MAIS RECOMENDADO</div><h4>Pro</h4><p><b>R${PRO}/mês</b></p><p>Mais análises, PDF premium e escala operacional.</p></div>', unsafe_allow_html=True)
p3.markdown(f'<div class="mp-pricing"><div class="badge">ESCALA</div><h4>Business</h4><p><b>R${BUSINESS}/mês</b></p><p>Capacidade máxima para operação de alto volume.</p></div>', unsafe_allow_html=True)

_whatsapp_strategic_block("landing_wa_cta_planos")

st.markdown(
    '<div class="mp-beta">Condição especial para os primeiros clientes deste mês.</div>',
    unsafe_allow_html=True,
)

st.markdown('<div class="mp-section-title">Solicite uma demonstração</div>', unsafe_allow_html=True)

if st.session_state.landing_lead_saved:
    st.markdown(
        """
<div class="mp-lead-success">
  <div class="mp-lead-success-title">Recebemos seu interesse.</div>
  <p class="mp-lead-success-sub">Entraremos em contato.</p>
</div>
""",
        unsafe_allow_html=True,
    )
    if st.button("Nova solicitação", key="landing_lead_reset", width="stretch"):
        st.session_state.landing_lead_saved = False
        st.rerun()
else:
    st.markdown(
        '<p class="mp-lead-hint">Preencha os dados abaixo. Nossa equipe comercial retorna em horário útil.</p>',
        unsafe_allow_html=True,
    )
    with st.form("landing_demo_form"):
        r1, r2 = st.columns(2)
        with r1:
            lead_nome = st.text_input(
                "Nome",
                placeholder="Seu nome completo",
                key="lead_nome",
            )
        with r2:
            lead_empresa = st.text_input(
                "Empresa",
                placeholder="Razão social ou nome fantasia",
                key="lead_empresa",
            )
        r3, r4 = st.columns(2)
        with r3:
            lead_whatsapp = st.text_input(
                "WhatsApp",
                placeholder="DDD + número",
                key="lead_whatsapp",
            )
        with r4:
            lead_email = st.text_input(
                "E-mail",
                placeholder="nome@empresa.com.br",
                key="lead_email",
            )
        lead_plano = st.selectbox(
            "Plano de interesse",
            ("Starter", "Pro", "Business", "Ainda não defini"),
            key="lead_plano",
        )
        submitted_demo = st.form_submit_button(
            "Quero conhecer",
            type="primary",
            width="stretch",
        )

    if submitted_demo:
        erros = []
        if not (lead_nome or "").strip():
            erros.append("Informe seu nome.")
        if not (lead_empresa or "").strip():
            erros.append("Informe a empresa.")
        if not (lead_whatsapp or "").strip():
            erros.append("Informe o WhatsApp.")
        if not (lead_email or "").strip():
            erros.append("Informe o e-mail.")
        elif not re.match(
            r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
            (lead_email or "").strip(),
        ):
            erros.append("Informe um e-mail válido.")
        for msg in erros:
            st.error(msg)
        if not erros:
            ok, _det = salvar_lead_demonstracao(
                lead_nome,
                lead_empresa,
                lead_whatsapp,
                lead_email,
                lead_plano,
            )
            if ok:
                st.session_state.landing_lead_saved = True
                st.rerun()
            else:
                st.error(
                    "Não foi possível registrar seu pedido agora. "
                    "Tente novamente em instantes ou use os botões de contato acima."
                )

st.markdown('<div class="mp-section-title">Objeções</div>', unsafe_allow_html=True)
ob1, ob2 = st.columns(2)
ob3, ob4 = st.columns(2)
ob1.markdown(
    '<div class="mp-objection"><strong>Serve para pequenas empresas?</strong><p>Sim. Do MEI à holding — você usa só o que precisa, sem burocracia desnecessária.</p></div>',
    unsafe_allow_html=True,
)
ob2.markdown(
    '<div class="mp-objection"><strong>Posso testar antes?</strong><p>Sim. Trial estratégico sem cartão para você sentir valor antes de escalar.</p></div>',
    unsafe_allow_html=True,
)
ob3.markdown(
    '<div class="mp-objection"><strong>Preciso advogado interno?</strong><p>Não é obrigatório. A plataforma orienta decisões; seu jurídico complementa quando fizer sentido.</p></div>',
    unsafe_allow_html=True,
)
ob4.markdown(
    '<div class="mp-objection"><strong>É rápido de usar?</strong><p>Minutos. Linguagem clara, fluxo direto e resultado na hora para quem precisa decidir.</p></div>',
    unsafe_allow_html=True,
)

st.markdown('<div class="mp-section-title">FAQ</div>', unsafe_allow_html=True)
st.markdown('<div class="mp-faq"><strong>Preciso cartão para testar?</strong><br><span style="color:#cbd5e1;">Não. Você pode iniciar no trial sem cartão.</span></div>', unsafe_allow_html=True)
st.markdown('<div class="mp-faq"><strong>Em quanto tempo recebo resultado?</strong><br><span style="color:#cbd5e1;">Em minutos, com leitura executiva e recomendação prática.</span></div>', unsafe_allow_html=True)
st.markdown('<div class="mp-faq"><strong>Serve para empresas pequenas e grandes?</strong><br><span style="color:#cbd5e1;">Sim. O fluxo foi desenhado para operação enxuta e escala.</span></div>', unsafe_allow_html=True)

st.markdown(
    """
<div class="mp-final">
  <div style="color:#fcd34d;font-size:0.78rem;font-weight:800;letter-spacing:0.06em;text-transform:uppercase;margin-bottom:0.5rem;">"""
    + MP_WA_URGENCY
    + """</div>
  <h3 style="margin: 0 0 0.35rem 0;">Pronto para decidir com segurança?</h3>
  <div style="color:#cbd5e1;">Priorize <strong style="color:#ffffff;">Agendar Demonstração</strong> com nosso time ou inicie o teste estratégico gratuito — sem cartão.</div>
</div>
""",
    unsafe_allow_html=True,
)

_whatsapp_strategic_block("landing_wa_cta_footer", show_urgency=False)

col_f1, col_f2 = st.columns(2)
with col_f1:
    if st.button("Agendar Demonstração", key="landing_specialist_btn_bottom", type="primary", width="stretch"):
        _ir_para_login()
with col_f2:
    if st.button("Teste Estratégico Gratuito", key="landing_trial_btn_bottom", width="stretch"):
        _ir_para_teste_gratis()

st.markdown("</div>", unsafe_allow_html=True)

_wa_href = html_escape(_mp_whatsapp_url(), quote=True)
st.markdown(
    f"""
<div class="mp-wa-fab-pulse" aria-hidden="true"></div>
<a href="{_wa_href}" target="_blank" rel="noopener noreferrer" class="mp-wa-fab" title="WhatsApp — M&amp;P Consultoria Trabalhista" aria-label="Falar no WhatsApp com a M&amp;P Consultoria Trabalhista">
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="28" height="28" fill="currentColor" aria-hidden="true">
    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.435 9.884-9.884 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
  </svg>
</a>
""",
    unsafe_allow_html=True,
)
