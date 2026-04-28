import streamlit as st
from ui.theme import apply_global_theme


st.set_page_config(page_title="DP-IA | Landing", layout="wide")
apply_global_theme()


def _ir_para_login():
    st.session_state["landing_intent"] = "login"
    st.switch_page("app.py")


def _ir_para_teste_gratis():
    st.session_state["landing_intent"] = "trial"
    st.switch_page("app.py")

st.markdown(
    """
<style>
    .mp-wrap { max-width: 1080px; margin: 0 auto; }
    .mp-hero {
        margin-top: 0.7rem;
        padding: 2.1rem 1.7rem;
        border-radius: 22px;
        border: 1px solid rgba(96, 165, 250, 0.35);
        background: linear-gradient(145deg, rgba(15,23,42,0.95), rgba(17,24,39,0.96));
        box-shadow: 0 0 0 1px rgba(59,130,246,0.14), 0 26px 60px rgba(2,6,23,0.5), 0 0 45px rgba(59,130,246,0.18);
        color: #e2e8f0;
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
        margin: 1.45rem 0 0.65rem 0;
        color: #f1f5f9;
        font-size: 1.2rem;
        font-weight: 800;
        letter-spacing: 0.01em;
    }
    .mp-card {
        background: rgba(15, 23, 42, 0.82);
        border: 1px solid rgba(148, 163, 184, 0.24);
        border-radius: 16px;
        padding: 1rem;
        color: #e2e8f0;
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
        background: rgba(15,23,42,0.82);
        padding: 1rem;
        color: #e2e8f0;
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
    .mp-faq {
        border: 1px solid rgba(148,163,184,0.24);
        border-radius: 12px;
        background: rgba(15,23,42,0.75);
        padding: 0.85rem 0.95rem;
        margin-bottom: 0.55rem;
    }
    .mp-final {
        margin-top: 1rem;
        padding: 1.1rem 1.2rem;
        border-radius: 16px;
        background: linear-gradient(135deg, rgba(30,41,59,0.95), rgba(30,64,175,0.35));
        border: 1px solid rgba(212,175,55,0.30);
        color: #e2e8f0;
    }
    @keyframes mpUp {
        from { opacity: 0.6; transform: translateY(6px); }
        to { opacity: 1; transform: translateY(0px); }
    }
    @media (max-width: 768px) {
        .mp-hero h1 { font-size: 1.62rem; }
        .mp-hero p { font-size: 0.95rem; }
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
    <h1>⚖️ Evite erros trabalhistas antes que virem prejuízo.</h1>
    <p>Consultoria estratégica trabalhista com apoio jurídico inteligente para empresários, RH e contadores.</p>
    <div class="mp-proof">Sem cartão • Resultado imediato • 7 dias grátis</div>
</div>
""",
    unsafe_allow_html=True,
)

cta_col1, cta_col2 = st.columns(2)
with cta_col1:
    if st.button("🚀 Teste grátis agora", key="landing_trial_btn_top", type="primary", width="stretch"):
        _ir_para_teste_gratis()
with cta_col2:
    if st.button("📞 Falar com especialista", key="landing_specialist_btn_top", width="stretch"):
        _ir_para_login()

st.markdown('<div class="mp-section-title">Quanto custa decidir errado?</div>', unsafe_allow_html=True)
d1, d2, d3, d4, d5 = st.columns(5)
d1.markdown('<div class="mp-card"><h4>⚠️ Processo inesperado</h4><p>A empresa é surpreendida sem defesa preparada.</p></div>', unsafe_allow_html=True)
d2.markdown('<div class="mp-card"><h4>📉 Rescisão errada</h4><p>Falhas simples geram passivo elevado.</p></div>', unsafe_allow_html=True)
d3.markdown('<div class="mp-card"><h4>🤰 Gestante dispensada</h4><p>Risco jurídico clássico com alto impacto.</p></div>', unsafe_allow_html=True)
d4.markdown('<div class="mp-card"><h4>⏱️ Horas extras</h4><p>Jornada mal documentada aumenta condenação.</p></div>', unsafe_allow_html=True)
d5.markdown('<div class="mp-card"><h4>🤝 Acordo ruim</h4><p>Negociação sem estratégia gera custo desnecessário.</p></div>', unsafe_allow_html=True)

st.markdown('<div class="mp-section-title">Como funciona</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
c1.markdown('<div class="mp-card mp-step"><h4>1) Descreva o caso</h4><p>Informe o cenário trabalhista em linguagem simples.</p></div>', unsafe_allow_html=True)
c2.markdown('<div class="mp-card mp-step"><h4>2) Receba análise estratégica</h4><p>Risco, exposição e recomendação objetiva para decisão.</p></div>', unsafe_allow_html=True)
c3.markdown('<div class="mp-card mp-step"><h4>3) Decida com segurança</h4><p>Aja com clareza e reduza chance de erro caro.</p></div>', unsafe_allow_html=True)

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

st.markdown('<div class="mp-section-title">Prova social</div>', unsafe_allow_html=True)
ps1, ps2 = st.columns(2)
ps1.markdown('<div class="mp-card"><h4>⭐ “Agora temos direção clara em casos críticos.”</h4><p>Coordenadora de RH, indústria com múltiplas unidades.</p></div>', unsafe_allow_html=True)
ps2.markdown('<div class="mp-card"><h4>⭐ “Reduziu retrabalho entre RH e jurídico.”</h4><p>Controller, rede de serviços com expansão nacional.</p></div>', unsafe_allow_html=True)

st.markdown('<div class="mp-section-title">Planos resumidos</div>', unsafe_allow_html=True)
p1, p2, p3 = st.columns(3)
p1.markdown('<div class="mp-pricing"><div class="badge">START</div><h4>Starter</h4><p><b>R$97/mês</b></p><p>Trial: 7 dias grátis ou 3 análises.</p></div>', unsafe_allow_html=True)
p2.markdown('<div class="mp-pricing"><div class="badge">RECOMENDADO</div><h4>Pro</h4><p><b>R$197/mês</b></p><p>Mais análises, PDF premium e escala operacional.</p></div>', unsafe_allow_html=True)
p3.markdown('<div class="mp-pricing"><div class="badge">ESCALA</div><h4>Business</h4><p><b>R$397/mês</b></p><p>Capacidade máxima para operação de alto volume.</p></div>', unsafe_allow_html=True)

st.markdown('<div class="mp-section-title">FAQ</div>', unsafe_allow_html=True)
st.markdown('<div class="mp-faq"><strong>Preciso cartão para testar?</strong><br><span style="color:#cbd5e1;">Não. Você pode iniciar no trial sem cartão.</span></div>', unsafe_allow_html=True)
st.markdown('<div class="mp-faq"><strong>Em quanto tempo recebo resultado?</strong><br><span style="color:#cbd5e1;">Em minutos, com leitura executiva e recomendação prática.</span></div>', unsafe_allow_html=True)
st.markdown('<div class="mp-faq"><strong>Serve para empresas pequenas e grandes?</strong><br><span style="color:#cbd5e1;">Sim. O fluxo foi desenhado para operação enxuta e escala.</span></div>', unsafe_allow_html=True)

st.markdown(
    """
<div class="mp-final">
  <h3 style="margin: 0 0 0.35rem 0;">Entre hoje e decida melhor amanhã.</h3>
  <div style="color:#cbd5e1;">Teste grátis agora e transforme risco trabalhista em vantagem de gestão.</div>
</div>
""",
    unsafe_allow_html=True,
)

col_f1, col_f2 = st.columns(2)
with col_f1:
    if st.button("🚀 Teste grátis agora", key="landing_trial_btn_bottom", type="primary", width="stretch"):
        _ir_para_teste_gratis()
with col_f2:
    if st.button("📞 Falar com especialista", key="landing_specialist_btn_bottom", width="stretch"):
        _ir_para_login()

st.markdown("</div>", unsafe_allow_html=True)
