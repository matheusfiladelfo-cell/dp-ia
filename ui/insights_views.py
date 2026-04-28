import streamlit as st


def render_insights_empresa(insights):
    if not insights:
        return

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
