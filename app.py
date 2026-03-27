import streamlit as st
import json

from banco import (
    criar_tabelas,
    salvar_analise,
    listar_empresas,
    cadastrar_empresa,
    incrementar_uso,
    obter_uso_usuario,
    login_usuario,
    criar_usuario
)

from insights_service import gerar_insights_empresa
from relatorio_service import gerar_relatorio_empresa

from analisador_caso import analisar_texto_usuario
from motor_consultor import analisar_caso
from ia_consultor import gerar_parecer_juridico
from ia_chat import gerar_resposta_chat

from pdf_generator import gerar_pdf_parecer

from plano_service import (
    get_plano_usuario,
    pode_gerar_pdf,
    pode_fazer_analise,
    get_limite_analises
)

from gerenciador_sessao import get_sessao

# 🔥 NOVO
from score_engine import calcular_score


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


criar_tabelas()

st.set_page_config(page_title="DP-IA", layout="wide")


# =========================
# LOGIN
# =========================
if "user_id" not in st.session_state:

    st.title("🔐 DP-IA | Login")

    aba = st.radio("Acesso", ["Entrar", "Criar conta"])

    email = st.text_input("Email")
    senha = st.text_input("Senha", type="password")

    if aba == "Entrar":
        if st.button("Entrar"):
            user_id = login_usuario(email, senha)
            if user_id:
                st.session_state.user_id = user_id
                st.rerun()
            else:
                st.error("Email ou senha inválidos")

    else:
        if st.button("Criar conta"):
            try:
                criar_usuario(email, senha)
                st.success("Conta criada! Faça login.")
            except:
                st.error("Email já cadastrado")

    st.stop()


usuario_id = st.session_state.user_id
sessao = get_sessao()


# =========================
# HEADER
# =========================
st.markdown("# 🧠 DP-IA")
st.markdown("### Consultor Trabalhista Inteligente para Empresas")


# =========================
# LOGOUT
# =========================
if st.sidebar.button("🚪 Sair"):
    del st.session_state["user_id"]
    st.rerun()


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
st.sidebar.markdown("## 🏢 Empresas")

empresas = listar_empresas(usuario_id)

if not empresas:
    st.sidebar.warning("Nenhuma empresa cadastrada")

empresa_nomes = [e[1] for e in empresas]
empresa_map = {e[1]: e[0] for e in empresas}

empresa_selecionada = st.sidebar.selectbox(
    "Selecionar empresa",
    empresa_nomes if empresa_nomes else ["--"]
)

empresa_id = empresa_map.get(empresa_selecionada)

st.session_state.empresa_id = empresa_id


st.sidebar.markdown("---")
st.sidebar.markdown("### ➕ Nova empresa")

nome_empresa = st.sidebar.text_input("Nome")
cnpj_empresa = st.sidebar.text_input("CNPJ")
cidade_empresa = st.sidebar.text_input("Cidade")
estado_empresa = st.sidebar.text_input("Estado")

if st.sidebar.button("Cadastrar empresa"):
    if nome_empresa:
        cadastrar_empresa(
            usuario_id,
            nome_empresa,
            cnpj_empresa,
            cidade_empresa,
            estado_empresa
        )
        st.success("Empresa cadastrada")
        st.rerun()


# =========================
# INSIGHTS
# =========================
if empresa_id:

    insights = gerar_insights_empresa(empresa_id)

    if insights:
        st.markdown("## 📊 Visão Inteligente da Empresa")

        col1, col2, col3 = st.columns(3)

        col1.metric("Casos", insights["total"])
        col2.metric("Alto risco", f"{insights['percentual_alto']}%")
        col3.metric("Problema", insights["problema"])

        if insights["percentual_alto"] > 40:
            st.error("🚨 Alto risco recorrente")
        elif insights["percentual_alto"] > 20:
            st.warning("⚠️ Atenção ao risco")
        else:
            st.success("✅ Risco controlado")

        st.markdown("---")


# =========================
# DIAGNÓSTICO INTELIGENTE
# =========================
if empresa_id:

    relatorio = gerar_relatorio_empresa(empresa_id)

    if relatorio:

        impacto_rel = relatorio.get("impacto", 0)

        try:
            impacto_rel = float(impacto_rel)
        except:
            impacto_rel = 0

        st.markdown("## 🧠 Diagnóstico Inteligente")

        st.markdown(f"""
A empresa apresenta padrão recorrente de risco trabalhista.

⚠️ **{relatorio['percentual']}% dos casos são de alto risco**

📌 **Principal problema identificado:**  
{relatorio['problema']}

💰 **Impacto financeiro estimado:**  
R$ {impacto_rel:,.2f}
""")

        st.markdown("---")


# =========================
# USO
# =========================
plano = get_plano_usuario()
uso = obter_uso_usuario(usuario_id)
limite = get_limite_analises(plano)

st.markdown(f"💼 Plano: {plano}")
st.markdown(f"📊 Uso: {uso} / {limite}")


# =========================
# ANÁLISE
# =========================
if modo == "🔵 Análise":

    texto_usuario = st.text_area("Descreva o caso:")

    if st.button("Analisar"):

        if not empresa_id:
            st.error("Selecione uma empresa")
            st.stop()

        if not pode_fazer_analise(usuario_id):
            st.error("Limite atingido")
            st.stop()

        with st.spinner("🧠 Analisando caso trabalhista..."):

            dados = analisar_texto_usuario(texto_usuario)

            resultado = analisar_caso(
                dados.get("tipo_caso"),
                dados
            )

            impacto_temp = resultado.get("impacto", 0)

            # ✅ CORREÇÃO DEFINITIVA
            tipo_para_score = dados.get("tipo_risco") or dados.get("tipo_caso") or "geral"

            if dados.get("tipo_risco") in ["assedio_moral", "acidente_trabalho"]:
                resultado["risco"] = "ALTO"

            score_data = calcular_score({
                "risco": resultado.get("risco", "BAIXO"),
                "impacto": impacto_temp,
                "tem_prova": dados.get("tem_prova", False),
                "testemunha": dados.get("testemunha", False),
                "reincidente": dados.get("reincidente", False),
                "tipo": tipo_para_score
            })

            score = score_data["score"]
            probabilidade = score_data["probabilidade_condenacao"]
            nivel = score_data["nivel"]
            motivos = score_data["motivos"]

        with st.spinner("⚖️ Gerando parecer jurídico..."):

            parecer = gerar_parecer_juridico(
                contexto=texto_usuario,
                dados=dados,
                resultado=resultado,
                score=score,
                probabilidade=probabilidade
            )

        incrementar_uso(usuario_id)

        def cor_score(score):
            if score >= 80:
                return "🔴"
            elif score >= 60:
                return "🟠"
            elif score >= 40:
                return "🟡"
            else:
                return "🟢"

        st.markdown("## 📊 Índice de Risco Trabalhista (DP-IA)")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Score", f"{cor_score(score)} {score}/100")

        with col2:
            st.metric("Probabilidade de Condenação", f"{probabilidade}%")

        with col3:
            st.metric("Nível de Risco", nivel)

        st.markdown("### 🧠 Fatores que influenciaram o score")

        for m in motivos:
            impacto_m = m["impacto"]
            sinal = "+" if impacto_m >= 0 else "-"
            st.write(f"{sinal}{impacto_m} → {m['fator']}")

        st.markdown("---")

        st.markdown("## 📊 Diagnóstico")
        st.markdown(limpar_texto_ia(parecer.get("diagnostico")))

        st.markdown("## ⚖️ Fundamentação Jurídica")
        st.markdown(limpar_texto_ia(parecer.get("fundamentacao")))

        st.markdown("## 📉 Impactos Trabalhistas")
        st.markdown(parecer.get("impactos"))

        st.markdown("## 💰 Impacto Financeiro")

        impacto = parecer.get("impacto_financeiro", 0)

        try:
            impacto = float(impacto)
        except:
            impacto = 0

        st.markdown(f"### R$ {impacto:,.2f}")

        st.markdown("## 🎯 Recomendação")
        st.markdown(limpar_texto_ia(parecer.get("recomendacao")))

        if pode_gerar_pdf(plano):
            pdf_path = gerar_pdf_parecer(
                empresa_selecionada,
                parecer,
                resultado
            )

            with open(pdf_path, "rb") as f:
                st.download_button("📄 Baixar PDF", f)

        salvar_analise(
            empresa_id,
            dados.get("tipo_caso"),
            parecer.get("risco"),
            resultado.get("pontuacao"),
            dados,
            {
                **resultado,
                "score": score,
                "probabilidade": probabilidade,
                "nivel": nivel,
                "motivos": motivos
            },
            parecer
        )


# =========================
# CHAT
# =========================
else:

    st.subheader("💬 Assistente")

    user_input = st.chat_input("Digite sua dúvida...")

    if user_input:
        sessao.adicionar("user", user_input)

        resposta = gerar_resposta_chat(
            sessao.gerar_contexto_llm()
        )

        sessao.adicionar("assistant", resposta)
        st.rerun()

    for msg in sessao.historico:
        with st.chat_message(msg["role"]):
            st.write(msg["texto"])


# =========================
# DIREITOS
# =========================
st.markdown("---")

st.caption("""
© 2025 DP-IA — Desenvolvido por Matheus Filadelfo Pires da Costa

Todos os direitos reservados.
Uso exclusivo. Proibida reprodução sem autorização.

Este sistema fornece apoio à decisão e não substitui consultoria jurídica.
""")