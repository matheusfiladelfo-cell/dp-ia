import base64
import hashlib
import hmac
import json
import os
import struct
import time

import pandas as pd
import streamlit as st

from application.analytics_service import (
    calcular_kpis_principais,
    obter_dados_crescimento_usuarios_por_dia,
    obter_distribuicao_eventos_produto,
    obter_distribuicao_eventos_produto_por_nome,
    obter_distribuicao_planos,
    obter_labels_periodo,
)
from banco import (
    admin_definir_bloqueio_usuario,
    admin_definir_plano_e_status,
    admin_listar_todos_usuarios_catalogo,
    listar_eventos_produto,
    listar_historico_planos_assinatura,
    listar_historico_status_usuario,
    listar_todas_as_empresas,
    registrar_admin_audit,
)
from ui.admin_views import render_admin_dashboard


def _totp_valid(code: str, secret_b32: str, step_seconds: int = 30, drift_steps: int = 1) -> bool:
    c = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(c) != 6:
        return False
    try:
        key = base64.b32decode(secret_b32.strip().upper(), casefold=True)
    except Exception:
        return False
    now_counter = int(time.time() // step_seconds)
    for delta in range(-drift_steps, drift_steps + 1):
        counter = now_counter + delta
        msg = struct.pack(">Q", counter)
        digest = hmac.new(key, msg, hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        binary = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
        expected = str(binary % 1000000).zfill(6)
        if hmac.compare_digest(expected, c):
            return True
    return False


def _admin_mfa_enabled() -> bool:
    return bool(
        str(os.getenv("ADMIN_MFA_TOTP_SECRET", "")).strip()
        or str(os.getenv("ADMIN_MFA_CODE", "")).strip()
    )


@st.dialog("Confirmar ação de usuário")
def _dialog_confirmar_acao_usuario(
    user_id: int,
    email: str,
    acao_label: str,
    bloquear_valor: int,
    actor_user_id: int,
    actor_email: str,
):
    st.write(f"Você tem certeza que deseja **{acao_label}** o usuário **{email}**?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirmar", key=f"confirm_user_{user_id}_{bloquear_valor}", type="primary"):
            registrar_admin_audit(
                admin_user_id=int(actor_user_id),
                action="superadmin_user_block_toggle",
                target_type="usuario",
                target_id=str(user_id),
                details=f"acao={acao_label};autor={actor_email}",
            )
            ok = admin_definir_bloqueio_usuario(
                usuario_id=int(user_id),
                bloqueado=int(bloquear_valor),
                actor_admin_id=int(actor_user_id),
            )
            if ok:
                st.toast(f"Ação concluída: usuário {email} {acao_label}.")
            else:
                st.error("Não foi possível concluir a ação.")
            st.rerun()
    with c2:
        if st.button("Cancelar", key=f"cancel_user_{user_id}_{bloquear_valor}"):
            st.rerun()


@st.dialog("Alterar plano da empresa")
def _dialog_alterar_plano_empresa(
    empresa_id: int,
    empresa_nome: str,
    proprietario_id: int,
    proprietario_email: str,
    plano_atual: str,
    actor_user_id: int,
    actor_email: str,
):
    st.write(
        f"Empresa **{empresa_nome}** (ID {empresa_id})\n\n"
        f"Proprietário: **{proprietario_email or 'N/A'}**"
    )
    col1, col2 = st.columns(2)
    with col1:
        plano_destino = st.selectbox(
            "Plano",
            ["FREE", "PRO", "PREMIUM"],
            index=["FREE", "PRO", "PREMIUM"].index(plano_atual if plano_atual in {"FREE", "PRO", "PREMIUM"} else "FREE"),
            key=f"modal_empresa_plano_{empresa_id}",
        )
    with col2:
        status_destino = st.selectbox(
            "Status",
            ["active", "suspended"],
            index=0,
            key=f"modal_empresa_status_{empresa_id}",
        )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirmar alteração", key=f"confirm_empresa_plano_{empresa_id}", type="primary"):
            if proprietario_id <= 0:
                st.error("Empresa sem proprietário válido para alteração de plano.")
                return
            registrar_admin_audit(
                admin_user_id=int(actor_user_id),
                action="superadmin_empresa_plan_change",
                target_type="empresa",
                target_id=str(empresa_id),
                details=(
                    f"empresa={empresa_nome};proprietario_id={proprietario_id};"
                    f"plano={plano_destino};status={status_destino};autor={actor_email}"
                ),
            )
            ok = admin_definir_plano_e_status(
                usuario_id=int(proprietario_id),
                plano=str(plano_destino),
                status_assinatura=str(status_destino),
                actor_admin_id=int(actor_user_id),
            )
            if ok:
                st.toast(f"Plano da empresa {empresa_nome} atualizado para {plano_destino}.")
            else:
                st.error("Não foi possível aplicar plano/status para este proprietário.")
            st.rerun()
    with c2:
        if st.button("Cancelar", key=f"cancel_empresa_plano_{empresa_id}"):
            st.rerun()


def render_superadmin_panel(user_id: int, email: str | None = None):
    st.markdown("## Painel de Controle Global")
    st.caption("Área restrita do Super Admin.")

    if _admin_mfa_enabled():
        mfa_ok = st.session_state.get("admin_mfa_ok_user_id") == int(user_id)
        if not mfa_ok:
            st.markdown("### Verificação adicional de segurança")
            with st.form("superadmin_mfa_form"):
                mfa_code = st.text_input(
                    "Código MFA (6 dígitos)",
                    max_chars=6,
                    placeholder="000000",
                )
                mfa_submit = st.form_submit_button("Validar acesso Super Admin")
            if mfa_submit:
                totp_secret = str(os.getenv("ADMIN_MFA_TOTP_SECRET", "")).strip()
                static_code = str(os.getenv("ADMIN_MFA_CODE", "")).strip()
                ok = False
                if totp_secret:
                    ok = _totp_valid(mfa_code, totp_secret)
                elif static_code:
                    ok = hmac.compare_digest(str(mfa_code or "").strip(), static_code)
                if ok:
                    st.session_state["admin_mfa_ok_user_id"] = int(user_id)
                    registrar_admin_audit(
                        admin_user_id=int(user_id),
                        action="superadmin_mfa_success",
                        target_type="superadmin_panel",
                        target_id="superadmin_panel.py",
                        details=f"email={email or '-'}",
                    )
                    st.rerun()
                else:
                    registrar_admin_audit(
                        admin_user_id=int(user_id),
                        action="superadmin_mfa_failure",
                        target_type="superadmin_panel",
                        target_id="superadmin_panel.py",
                        details=f"email={email or '-'}",
                    )
                    st.error("Código de verificação inválido.")
            return

    tab_visao, tab_analytics, tab_empresas, tab_usuarios, tab_hist_status, tab_hist_planos, tab_eventos = st.tabs(
        [
            "Visão Geral",
            "Analytics de Negócio",
            "Empresas",
            "Usuários",
            "Histórico de Status",
            "Histórico de Planos",
            "Eventos de Produto",
        ]
    )

    with tab_visao:
        render_admin_dashboard()

    with tab_analytics:
        st.markdown("### Analytics de Negócio")
        opcoes_periodo = {
            "Últimos 7 dias": 7,
            "Últimos 30 dias": 30,
            "Últimos 90 dias": 90,
        }
        label_periodo = st.radio(
            "Período de análise",
            options=list(opcoes_periodo.keys()),
            key="superadmin_analytics_periodo_label",
            horizontal=True,
        )
        periodo_dias = int(opcoes_periodo.get(label_periodo, 30))
        labels = obter_labels_periodo(periodo_dias=periodo_dias)
        p1, p2 = st.columns(2)
        with p1:
            st.caption(f"**Período Atual:** {labels.get('label_atual', '-')}")
        with p2:
            st.caption(f"**Período Anterior:** {labels.get('label_anterior', '-')}")
        st.divider()

        kpis = calcular_kpis_principais(periodo_dias=periodo_dias)
        c1, c2, c3 = st.columns(3)
        with c1:
            k = kpis.get("total_usuarios_ativos") or {}
            st.metric(
                f"Usuários Ativos ({periodo_dias}d)",
                int(k.get("value") or 0),
                delta=f"{float(k.get('delta') or 0.0):+.0%}",
            )
        with c2:
            k = kpis.get("total_empresas") or {}
            st.metric(
                f"Empresas Criadas ({periodo_dias}d)",
                int(k.get("value") or 0),
                delta=f"{float(k.get('delta') or 0.0):+.0%}",
            )
        with c3:
            k = kpis.get("total_analises_periodo") or {}
            st.metric(
                f"Análises no Período ({periodo_dias}d)",
                int(k.get("value") or 0),
                delta=f"{float(k.get('delta') or 0.0):+.0%}",
            )

        st.markdown(f"#### Crescimento de Usuários ({periodo_dias} dias)")
        crescimento = obter_dados_crescimento_usuarios_por_dia(periodo_dias=periodo_dias)
        if not crescimento.empty:
            st.line_chart(crescimento, height=260)
        else:
            st.caption("Sem dados de crescimento de usuários no período.")

        d1, d2 = st.columns(2)
        with d1:
            st.markdown("#### Distribuição de Planos")
            dist_planos = obter_distribuicao_planos()
            if dist_planos:
                df_planos = pd.DataFrame(dist_planos).set_index("plano")
                st.bar_chart(df_planos["total"], height=280)
                st.dataframe(pd.DataFrame(dist_planos), hide_index=True, width="stretch")
            else:
                st.caption("Sem dados de plano disponíveis.")
        with d2:
            st.markdown(f"#### Eventos de Produto por Dia ({periodo_dias}d)")
            serie_eventos = obter_distribuicao_eventos_produto(periodo_dias=periodo_dias)
            if not serie_eventos.empty:
                st.line_chart(serie_eventos, height=280)
                dist_eventos = obter_distribuicao_eventos_produto_por_nome(periodo_dias=periodo_dias)
                st.dataframe(pd.DataFrame(dist_eventos), hide_index=True, width="stretch")
            else:
                st.caption("Sem eventos de produto registrados.")

    with tab_empresas:
        st.markdown("### Catálogo Global de Empresas")
        busca_empresa = st.text_input(
            "Buscar empresa por nome ou CNPJ",
            key="superadmin_busca_empresas",
            placeholder="Digite nome da empresa ou CNPJ",
        )
        filtro_empresas_free = st.checkbox(
            "Filtrar apenas empresas em plano 'Free' ou 'Trial'",
            key="superadmin_filtro_empresas_free",
        )
        empresas = listar_todas_as_empresas()
        termo = str(busca_empresa or "").strip().lower()
        if termo:
            empresas = [
                e
                for e in empresas
                if termo in str(e.get("nome_empresa", "")).lower()
                or termo in str(e.get("cnpj", "")).lower()
            ]
        if filtro_empresas_free:
            empresas = [
                e
                for e in empresas
                if str(e.get("plano_atual", "FREE")).strip().upper() in {"FREE", "TRIAL"}
            ]
        if not empresas:
            st.info("Nenhuma empresa encontrada para o filtro informado.")
        else:
            df_emp_raw = pd.DataFrame(empresas)
            if "plano_atual" in df_emp_raw.columns:
                df_emp_raw["Plano Atual"] = df_emp_raw["plano_atual"].map(
                    lambda p: str(p or "FREE").upper()
                )

            df_emp = df_emp_raw.rename(
                columns={
                    "nome_empresa": "Nome da Empresa",
                    "cnpj": "CNPJ",
                    "email_proprietario": "Proprietário (E-mail)",
                    "data_criacao_empresa": "Data de Criação",
                    "id_empresa": "ID",
                    "id_proprietario": "ID Proprietário",
                }
            )
            df_emp = df_emp.drop(columns=["plano_atual"], errors="ignore")
            df_emp["Alterar Plano"] = False
            edited_emp = st.data_editor(
                df_emp,
                hide_index=True,
                width="stretch",
                key="superadmin_empresas_editor",
                column_config={
                    "Alterar Plano": st.column_config.CheckboxColumn("Alterar Plano", default=False),
                },
                disabled=[
                    "ID",
                    "ID Proprietário",
                    "Nome da Empresa",
                    "CNPJ",
                    "Proprietário (E-mail)",
                    "Data de Criação",
                    "Plano Atual",
                ],
            )

            alvo_emp = next((row for _, row in edited_emp.iterrows() if bool(row.get("Alterar Plano"))), None)
            if alvo_emp is not None:
                _dialog_alterar_plano_empresa(
                    empresa_id=int(alvo_emp.get("ID") or 0),
                    empresa_nome=str(alvo_emp.get("Nome da Empresa") or ""),
                    proprietario_id=int(alvo_emp.get("ID Proprietário") or 0),
                    proprietario_email=str(alvo_emp.get("Proprietário (E-mail)") or ""),
                    plano_atual=str(alvo_emp.get("Plano Atual") or "FREE"),
                    actor_user_id=int(user_id),
                    actor_email=str(email or ""),
                )

    with tab_usuarios:
        st.markdown("### Catálogo Global de Usuários")
        busca_usuario = st.text_input(
            "Buscar usuário por e-mail ou nome",
            key="superadmin_busca_usuarios",
            placeholder="Digite e-mail ou nome do usuário",
        )
        filtro_usuarios_criticos = st.checkbox(
            "Filtrar apenas usuários bloqueados/suspensos",
            key="superadmin_filtro_usuarios_criticos",
        )
        usuarios = admin_listar_todos_usuarios_catalogo()
        termo_u = str(busca_usuario or "").strip().lower()
        if termo_u:
            usuarios = [
                u
                for u in usuarios
                if termo_u in str(u.get("email", "")).lower()
                or termo_u in str(u.get("nome", "")).lower()
            ]
        if filtro_usuarios_criticos:
            usuarios = [
                u
                for u in usuarios
                if str(u.get("status_usuario", "")).strip().lower() in {"bloqueado", "suspenso"}
            ]
        if not usuarios:
            st.info("Nenhum usuário encontrado para o filtro informado.")
        else:
            df_usr = pd.DataFrame(usuarios).rename(
                columns={
                    "email": "E-mail",
                    "nome": "Nome",
                    "data_cadastro": "Data de Cadastro",
                    "status_usuario": "Status",
                    "plano_atual": "Plano Atual",
                    "id_usuario": "ID",
                }
            )
            df_usr["Alternar Bloqueio"] = False
            edited_usr = st.data_editor(
                df_usr,
                hide_index=True,
                width="stretch",
                key="superadmin_usuarios_editor",
                column_config={
                    "Alternar Bloqueio": st.column_config.CheckboxColumn("Alternar Bloqueio", default=False),
                },
                disabled=[
                    "ID",
                    "E-mail",
                    "Nome",
                    "Data de Cadastro",
                    "Status",
                    "Plano Atual",
                ],
            )

            alvo_usr = next((row for _, row in edited_usr.iterrows() if bool(row.get("Alternar Bloqueio"))), None)
            if alvo_usr is not None:
                uid = int(alvo_usr.get("ID") or 0)
                alvo_email = str(alvo_usr.get("E-mail") or "")
                status_atual = str(alvo_usr.get("Status") or "").lower()
                bloquear_valor = 0 if status_atual == "bloqueado" else 1
                acao_label = "desbloquear" if bloquear_valor == 0 else "bloquear"
                _dialog_confirmar_acao_usuario(
                    user_id=uid,
                    email=alvo_email,
                    acao_label=acao_label,
                    bloquear_valor=bloquear_valor,
                    actor_user_id=int(user_id),
                    actor_email=str(email or ""),
                )

    with tab_hist_status:
        st.markdown("### Histórico de Status de Usuários")
        hist_status = listar_historico_status_usuario(limit=100)
        if not hist_status:
            st.info("Sem registros de histórico de status até o momento.")
        else:
            st.dataframe(pd.DataFrame(hist_status), hide_index=True, width="stretch")

    with tab_hist_planos:
        st.markdown("### Histórico de Planos e Status de Assinatura")
        hist_planos = listar_historico_planos_assinatura(limit=100)
        if not hist_planos:
            st.info("Sem registros de histórico de planos até o momento.")
        else:
            st.dataframe(pd.DataFrame(hist_planos), hide_index=True, width="stretch")

    with tab_eventos:
        st.markdown("### Eventos de Produto")
        eventos = listar_eventos_produto(limit=100)
        if not eventos:
            st.info("Sem eventos de produto até o momento.")
        else:
            st.dataframe(pd.DataFrame(eventos), hide_index=True, width="stretch")
            with st.expander("Ver metadados dos eventos (JSON)", expanded=False):
                for row in eventos[:20]:
                    st.markdown(
                        f"**Evento #{row.get('id')}** — {row.get('nome_evento')} "
                        f"({row.get('timestamp_evento')})"
                    )
                    raw_json = row.get("metadados_json") or "{}"
                    try:
                        st.json(json.loads(raw_json))
                    except Exception:
                        st.code(str(raw_json))
