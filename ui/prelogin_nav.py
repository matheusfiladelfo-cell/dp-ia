"""
Navegação lateral pré-login (substitui o menu multipage nativo do Streamlit).
"""

from __future__ import annotations

import streamlit as st
from streamlit_option_menu import option_menu

from ui.nav_styles import MP_OPTION_MENU_STYLES

# (rótulo PT, caminho switch_page, ícone bootstrap)
PRELOGIN_NAV = (
    ("Página Inicial", "pages/landing.py", "house"),
    ("Acessar Plataforma", "app.py", "box-arrow-in-right"),
    ("Dashboard Público", "pages/dashboard.py", "bar-chart"),
)

_LABELS = [item[0] for item in PRELOGIN_NAV]
_PATHS = [item[1] for item in PRELOGIN_NAV]
_ICONS = [item[2] for item in PRELOGIN_NAV]


def render_prelogin_sidebar_nav(current_path: str) -> None:
    """
    Menu lateral estilizado antes do login. Não altera roteamento além de st.switch_page.
    """
    if st.session_state.get("user_id"):
        return

    current_path = str(current_path or "").strip()
    try:
        default_index = _PATHS.index(current_path)
    except ValueError:
        default_index = 0

    with st.sidebar:
        st.markdown(
            '<p class="mp-sidebar-brand">M&amp;P Consultoria</p>',
            unsafe_allow_html=True,
        )
        st.caption("Inteligência trabalhista para decisões de RH.")

        escolha = option_menu(
            menu_title=None,
            options=_LABELS,
            icons=_ICONS,
            menu_icon="cast",
            default_index=default_index,
            key="menu_prelogin_mp",
            styles=MP_OPTION_MENU_STYLES,
        )

        try:
            destino = _PATHS[_LABELS.index(escolha)]
        except ValueError:
            destino = _PATHS[default_index]

        if destino != current_path:
            st.switch_page(destino)
