import streamlit as st
from ui.theme import apply_global_theme


def render_app_theme():
    apply_global_theme()
    st.markdown(
        """
<style>
    .dpia-hero {
        padding: 1.2rem 1.4rem;
        border-radius: 16px;
        background: linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(30,64,175,0.40) 100%);
        color: #f8fafc;
        border: 1px solid rgba(96,165,250,0.28);
        box-shadow: 0 0 0 1px rgba(59,130,246,0.10), 0 18px 42px rgba(2,6,23,0.42), 0 0 36px rgba(59,130,246,0.16);
        margin-bottom: 1rem;
    }
    .dpia-hero h1 {
        margin: 0;
        font-size: 1.4rem;
        font-weight: 700;
    }
    .dpia-hero p {
        margin: 0.35rem 0 0 0;
        color: #cbd5e1;
    }
    .dpia-section-title {
        margin-top: 0.5rem;
        margin-bottom: 0.25rem;
        color: #e2e8f0;
        font-weight: 700;
        font-size: 1.02rem;
    }
</style>
""",
        unsafe_allow_html=True,
    )


def render_header():
    st.markdown(
        """
<div class="dpia-hero">
    <h1>⚖️ M&P Consultoria Trabalhista</h1>
    <p><strong>Inteligência Estratégica Empresarial</strong><br>Decisão orientada por dados e IA para liderança de RH.</p>
    <div class="mp-cred-strip">Conformidade trabalhista • Análise estratégica • Decisão orientada por IA</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_premium_card():
    st.markdown(
        """
<div style="
padding:18px;
border-radius:12px;
border: 1px solid rgba(212,175,55,0.28);
background: linear-gradient(135deg, #111827, #1e293b);
color:white;
margin-bottom:16px;
box-shadow: 0 10px 28px rgba(2,6,23,0.45), 0 0 30px rgba(59,130,246,0.14);
">
<h3 style="margin:0 0 6px 0;">📊 Análise Inteligente de Risco Trabalhista <span class="mp-gold-accent">• Premium</span></h3>
<p style="margin-bottom:0;">
Identifique riscos, reduza passivos e conduza decisões com padrão executivo.
</p>
</div>
""",
        unsafe_allow_html=True,
    )


def render_result_intro_card():
    st.markdown(
        """
<div class="dpia-report-card">
<strong>Resultado Executivo</strong><br>
Relatório consolidado para tomada de decisão no RH.
</div>
""",
        unsafe_allow_html=True,
    )


def render_section_title(title):
    st.markdown(
        f'<div class="dpia-section-title">{title}</div>',
        unsafe_allow_html=True,
    )


def render_footer():
    st.markdown("---")
    st.caption(
        """
⚖️ M&P Consultoria Trabalhista
Inteligência Estratégica Empresarial

Tecnologia aplicada à prevenção de passivos trabalhistas.
"""
    )
