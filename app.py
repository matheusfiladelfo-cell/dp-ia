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

        sessao.adicionar("user", texto_usuario)

        contexto = sessao.gerar_contexto_llm()

        dados = analisar_texto_usuario(texto_usuario)
        sessao.atualizar_dados(dados)

        dados_consolidados = sessao.obter_dados()

        resultado = analisar_caso(
            dados_consolidados.get("tipo_caso"),
            dados_consolidados
        )

        parecer = gerar_parecer_juridico(
            contexto=contexto,
            dados=dados_consolidados,
            resultado=resultado
        )

        sessao.adicionar("assistant", str(parecer))

    # =========================
    # OUTPUT PROFISSIONAL
    # =========================

    st.markdown("## 📊 Resultado da análise")

    st.markdown(f"### ⚠ RISCO: {parecer.get('risco', 'N/A')}")

    st.markdown("---")

    # 🔥 DIAGNÓSTICO
    st.subheader("🧠 O que está acontecendo")
    st.write(parecer.get("diagnostico", ""))

    # 🔥 MOTIVO DO RISCO
    st.subheader("⚠ Por que isso é risco")
    st.write(parecer.get("motivo_risco", ""))

    # 🔥 BASE LEGAL (FIXA + IA)
    st.subheader("⚖️ Base legal")
    st.write("""
A CLT (art. 7º da Constituição e art. 59 da CLT) exige pagamento de horas extras com adicional mínimo de 50%.
A Justiça do Trabalho reconhece reflexos em férias, 13º, FGTS e DSR quando as horas são habituais.
Também pode aplicar o piso da categoria, aumentando o valor da condenação.
""")

    # 🔥 AÇÕES
    st.subheader("✅ O que fazer agora")

    for acao in parecer.get("o_que_fazer", []):
        st.write(f"✔ {acao}")

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