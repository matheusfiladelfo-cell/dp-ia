import streamlit as st


def _linhas_permissoes_por_perfil(perfil: str | None):
    perfil_norm = str(perfil or "").strip().lower()
    if perfil_norm == "admin":
        return "Admin", [
            "✅ Visualizar todos os casos da empresa.",
            "✅ Criar novos casos e análises.",
            "✅ Acessar o Dashboard Corporativo.",
            "✅ Gerenciar membros da equipe.",
            "✅ Gerenciar integrações e chaves de API.",
        ]
    if perfil_norm == "gestor":
        return "Gestor", [
            "✅ Visualizar todos os casos da empresa.",
            "✅ Criar novos casos e análises.",
            "✅ Acessar o Dashboard Corporativo.",
            "❌ Gerenciar membros da equipe.",
            "❌ Gerenciar integrações e chaves de API.",
        ]
    if perfil_norm == "colaborador":
        return "Colaborador", [
            "❌ Visualizar casos de outros usuários da empresa.",
            "✅ Criar novos casos e análises.",
            "❌ Acessar o Dashboard Corporativo.",
            "❌ Gerenciar membros da equipe.",
            "❌ Gerenciar integrações e chaves de API.",
        ]
    return "Sem perfil", [
        "❌ Perfil não identificado para a empresa selecionada.",
    ]


def render_resumo_permissoes(perfil: str | None):
    titulo_perfil, linhas = _linhas_permissoes_por_perfil(perfil)
    st.sidebar.caption(f"Seu perfil: **{titulo_perfil}**")
    with st.sidebar.expander("Ver minhas permissões", expanded=False):
        for linha in linhas:
            st.markdown(linha)
        st.caption(
            "Estas permissões são aplicadas para a empresa atualmente selecionada. "
            "Se você pertence a outras empresas, seu perfil pode ser diferente em cada uma delas."
        )
