"""
Gestão de equipe por empresa (admin).
"""

from collections import Counter

import pandas as pd
import streamlit as st

from application.email_service import enviar_email_convite_primeiro_acesso
from banco import (
    atualizar_perfil_membro_empresa,
    criar_ou_reenviar_convite_primeiro_acesso,
    listar_convites_primeiro_acesso_empresa,
    listar_membros_empresa,
    remover_membro_empresa,
)


def render_gestao_equipe(usuario_atual_id, empresa_id, empresa_nome: str | None):
    st.markdown("### Gestão de Equipe")
    if empresa_nome:
        st.caption(f"Empresa: **{empresa_nome}**")

    if not empresa_id:
        st.warning("Selecione uma empresa na barra lateral.")
        return

    st.markdown("#### Convidar novo usuário")
    c1, c2 = st.columns(2)
    with c1:
        nome_inv = st.text_input("Nome", key="equipe_convite_nome")
    with c2:
        email_inv = st.text_input("E-mail", key="equipe_convite_email")
    perfil_inv = st.selectbox(
        "Perfil",
        ["colaborador", "gestor", "admin"],
        key="equipe_convite_perfil",
        help="Admin: equipe e todos os casos. Gestor: todos os casos. Colaborador: apenas próprios casos.",
    )

    if st.button("Enviar convite", key="equipe_btn_convite", type="primary"):
        ok, msg, token_convite = criar_ou_reenviar_convite_primeiro_acesso(
            int(empresa_id),
            nome_inv,
            email_inv,
            perfil_inv,
            convidado_por_usuario_id=int(usuario_atual_id),
        )
        if ok:
            envio_ok = enviar_email_convite_primeiro_acesso(
                destinatario=email_inv,
                nome_destinatario=nome_inv,
                empresa_nome=empresa_nome or "Empresa",
                perfil=perfil_inv,
                token=token_convite or "",
            )
            if envio_ok:
                st.success("Convite enviado por e-mail com sucesso.")
            else:
                st.warning(
                    "Convite registrado, mas o envio de e-mail falhou. "
                    "Revise as configurações de e-mail e use 'Reenviar convite'."
                )
            st.rerun()
        else:
            st.error(msg)

    st.markdown("#### Convites")
    convites = listar_convites_primeiro_acesso_empresa(int(empresa_id))
    if convites:
        df_conv = pd.DataFrame(convites)
        if "convite_id" in df_conv.columns:
            df_conv = df_conv.drop(columns=["convite_id"])
        ren = {
            "nome": "Nome",
            "email": "E-mail",
            "perfil": "Perfil",
            "status": "Status",
            "criado_em": "Criado em",
            "expira_em": "Expira em",
            "aceito_em": "Aceito em",
        }
        df_conv = df_conv.rename(columns={k: v for k, v in ren.items() if k in df_conv.columns})
        st.dataframe(df_conv, hide_index=True, width="stretch")

    else:
        st.caption("Nenhum convite registrado para esta empresa.")

    st.markdown("---")
    st.markdown("#### Membros da empresa")

    membros = listar_membros_empresa(empresa_id)
    if not membros:
        st.info("Nenhum membro listado.")
        return

    ordem_status = {"🟡 Pendente": 0, "⚫ Expirado": 1, "🟢 Aceito": 2}
    membros_ordenados = sorted(
        membros,
        key=lambda membro: (
            ordem_status.get(str(membro.get("status_convite") or ""), 99),
            str(membro.get("nome") or "").lower(),
        ),
    )

    contagem_status = Counter(
        str(membro.get("status_convite") or "🟢 Aceito") for membro in membros_ordenados
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Pendentes", contagem_status.get("🟡 Pendente", 0))
    with c2:
        st.metric("Expirados", contagem_status.get("⚫ Expirado", 0))
    with c3:
        st.metric("Aceitos", contagem_status.get("🟢 Aceito", 0))

    df = pd.DataFrame(membros_ordenados)
    df_show = df.drop(columns=["status_convite_raw"], errors="ignore")

    edited = st.data_editor(
        df_show,
        column_config={
            "usuario_id": st.column_config.NumberColumn("ID", disabled=True),
            "nome": st.column_config.TextColumn("Nome", disabled=True),
            "email": st.column_config.TextColumn("E-mail", disabled=True),
            "perfil": st.column_config.SelectboxColumn(
                "Perfil",
                options=["admin", "gestor", "colaborador"],
                required=True,
            ),
            "status_convite": st.column_config.TextColumn("Status", disabled=True),
        },
        hide_index=True,
        width="stretch",
        key=f"equipe_editor_{empresa_id}",
    )

    if st.button("Salvar alterações de perfil", key="equipe_btn_salvar_perfis"):
        alterou = False
        for _, row in edited.iterrows():
            uid = int(row["usuario_id"])
            novo = str(row["perfil"]).strip().lower()
            atual = next((m["perfil"] for m in membros_ordenados if m["usuario_id"] == uid), None)
            if atual is None or novo == atual:
                continue
            try:
                atualizar_perfil_membro_empresa(int(empresa_id), uid, novo)
                alterou = True
            except ValueError as err:
                st.error(str(err))
        if alterou:
            st.success("Perfis atualizados.")
            st.rerun()

    st.markdown("##### Ações por membro")
    for m in membros_ordenados:
        cols = st.columns([4, 2, 1, 1])
        with cols[0]:
            st.caption(f"{m['nome']} ({m['email']}) — {m['perfil']}")
        with cols[1]:
            st.caption(m.get("status_convite", "🟢 Aceito"))
        with cols[2]:
            status_raw = str(m.get("status_convite_raw") or "").strip().lower()
            if status_raw in {"pendente", "expirado"}:
                if st.button("Reenviar", key=f"equipe_reenviar_member_{empresa_id}_{m['usuario_id']}"):
                    ok2, msg2, token2 = criar_ou_reenviar_convite_primeiro_acesso(
                        int(empresa_id),
                        str(m.get("nome") or ""),
                        str(m.get("email") or ""),
                        str(m.get("perfil") or "colaborador"),
                        convidado_por_usuario_id=int(usuario_atual_id),
                    )
                    if ok2:
                        envio_ok2 = enviar_email_convite_primeiro_acesso(
                            destinatario=str(m.get("email") or ""),
                            nome_destinatario=str(m.get("nome") or ""),
                            empresa_nome=empresa_nome or "Empresa",
                            perfil=str(m.get("perfil") or "colaborador"),
                            token=token2 or "",
                        )
                        if envio_ok2:
                            st.success("Convite reenviado com sucesso.")
                        else:
                            st.warning("Convite atualizado, mas o envio de e-mail falhou.")
                        st.rerun()
                    else:
                        st.error(msg2)
        with cols[3]:
            uid_alvo = m["usuario_id"]
            if st.button("Remover", key=f"equipe_rm_{empresa_id}_{uid_alvo}"):
                try:
                    remover_membro_empresa(int(empresa_id), int(uid_alvo))
                    st.success("Membro removido.")
                    st.rerun()
                except ValueError as err:
                    st.error(str(err))
