import streamlit as st

from banco import criar_tabelas, salvar_analise
from analisador_caso import analisar_texto_usuario
from motor_consultor import analisar_caso
from ia_consultor import gerar_parecer_juridico

from gerenciador_sessao import get_sessao, resetar_sessao


criar_tabelas()

st.set_page_config(page_title="DP-IA", layout="wide")

st.title("DP-IA | Consultor Trabalhista Inteligente")

sessao = get_sessao()

# =========================
# RESET
# =========================
if st.button("🔄 Nova análise"):
    resetar_sessao()
    st.rerun()


texto_usuario = st.text_area("Descreva o caso ou responda ao consultor:")


# =========================
# PROCESSAMENTO
# =========================
if st.button("Enviar"):

    if not texto_usuario:
        st.warning("Digite uma mensagem")
        st.stop()

    with st.spinner("Analisando caso..."):

        # HISTÓRICO
        sessao.adicionar("user", texto_usuario)

        contexto = sessao.gerar_contexto_llm()

        # 🔥 ANALISAR SOMENTE TEXTO ATUAL (CORREÇÃO CRÍTICA)
        dados = analisar_texto_usuario(texto_usuario)

        sessao.atualizar_dados(dados)

        dados_consolidados = sessao.obter_dados()

        # 🔥 MOTOR AGORA É AUXILIAR (NÃO DECIDE MAIS SOZINHO)
        resultado = analisar_caso(
            dados_consolidados.get("tipo_caso"),
            dados_consolidados
        )

        # 🔥 IA AGORA É O CÉREBRO PRINCIPAL
        parecer = gerar_parecer_juridico(
            contexto=contexto,
            dados=dados_consolidados,
            resultado=resultado
        )

        sessao.adicionar("assistant", str(parecer))

    # =========================
    # OUTPUT (PROFISSIONAL)
    # =========================

    st.markdown("## 📊 Resultado da análise")

    # 🔥 RISCO VEM DA IA (NÃO MAIS DO MOTOR)
    st.markdown(f"### ⚠ RISCO: {parecer.get('risco', 'N/A')}")

    st.markdown("---")

    st.subheader("Consultoria trabalhista")

    st.markdown(f"📊 **DIAGNÓSTICO:**\n{parecer.get('diagnostico', '')}")
    st.markdown(f"\n⚠ **RISCO:**\n{parecer.get('risco', '')}")
    st.markdown(f"\n📚 **FUNDAMENTAÇÃO LEGAL:**\n{parecer.get('fundamentacao', '')}")
    st.markdown(f"\n✅ **RECOMENDAÇÃO:**\n{parecer.get('recomendacao', '')}")

    # =========================
    # PERGUNTAS
    # =========================
    if dados.get("perguntas"):
        st.markdown("---")
        st.warning("🔎 Para refinar a análise:")

        for p in dados["perguntas"]:
            st.write(f"🔹 {p['pergunta']}")
            st.caption(p["motivo"])

    # =========================
    # SALVAR
    # =========================
    salvar_analise(
        None,
        None,
        parecer.get("risco", "N/A"),
        str(parecer)
    )


# =========================
# HISTÓRICO
# =========================
st.markdown("---")
st.markdown("### 🗂️ Conversa")

for m in sessao.historico:
    if m["role"] == "user":
        st.markdown(f"**👤 Usuário:** {m['texto']}")
    else:
        st.markdown(f"**🧠 Consultor:** {m['texto']}")