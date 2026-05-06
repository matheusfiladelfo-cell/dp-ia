"""
Interface de validação humana dos fatos extraídos de documentos.
Somente fatos persistidos em analises_fatos_validados devem alimentar score_engine v2.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import datetime

from application.document_fatos_llm import CHAVES_JSON, aplicar_fatos_documento_na_sessao
from banco import (
    criar_analise_stub_validacao_fatos,
    listar_fatos_validados,
    obter_email_usuario,
    substituir_fatos_validados,
)


def documento_tem_fatos_validados_persistidos(msg: dict) -> bool:
    aid = msg.get("analise_id_fatos")
    if not aid:
        return False
    try:
        return len(listar_fatos_validados(int(aid))) > 0
    except (TypeError, ValueError):
        return False


def _fatos_padrao_para_ui(msg: dict) -> dict:
    raw = dict(msg.get("fatos_extraidos") or {})
    out: dict = {}
    for k in CHAVES_JSON:
        if k == "evidencias_mencionadas":
            v = raw.get(k)
            out[k] = list(v) if isinstance(v, list) else []
        else:
            val = raw.get(k)
            out[k] = val if val not in (None, "") else "Não encontrado"
    return out


def _valor_celula_editor(chave: str, fatos: dict) -> str:
    val = fatos.get(chave)
    if chave == "evidencias_mencionadas":
        if isinstance(val, list) and val:
            return "; ".join(str(x).strip() for x in val if str(x).strip())
        return "Não encontrado"
    return str(val if val is not None else "").strip() or "Não encontrado"


def _dataframe_editor_inicial(fatos: dict) -> pd.DataFrame:
    rows = [{"Fato": k, "Valor": _valor_celula_editor(k, fatos)} for k in CHAVES_JSON]
    return pd.DataFrame(rows)


def _norm_ev(val_str: str) -> str:
    parts = sorted(x.strip().lower() for x in str(val_str).split(";") if x.strip())
    return "|".join(parts)


def _infer_fonte(chave: str, valor_editado: str, orig_ia: dict | None) -> str:
    orig_ia = orig_ia or {}
    ve = str(valor_editado).strip()
    if chave == "evidencias_mencionadas":
        vo = orig_ia.get(chave)
        if isinstance(vo, list):
            orig_norm = _norm_ev("; ".join(str(x) for x in vo))
        else:
            orig_norm = _norm_ev(str(vo or ""))
        return "documento_ia" if orig_norm == _norm_ev(ve) else "inserido_manualmente"
    vo = str(orig_ia.get(chave, "")).strip().lower()
    return "documento_ia" if vo == ve.strip().lower() else "inserido_manualmente"


def _dict_desde_editor(df: pd.DataFrame) -> dict:
    out: dict = {}
    for _, row in df.iterrows():
        chave = str(row["Fato"]).strip()
        raw_val = str(row["Valor"]).strip()
        if chave == "evidencias_mencionadas":
            if raw_val.lower() in {"", "não encontrado", "nao encontrado", "-"}:
                out[chave] = []
            else:
                out[chave] = [x.strip() for x in raw_val.split(";") if x.strip()]
        else:
            out[chave] = raw_val if raw_val else "Não encontrado"
    return out


def render_validacao_fatos_documento(sessao, msg: dict, empresa_id=None, usuario_id=None):
    if "fatos_extraidos" not in msg:
        return

    doc_uid = msg.get("doc_msg_uid")
    if not doc_uid:
        return

    st.markdown("---")
    st.markdown(
        "**Validação dos fatos** *(somente após aprovação os valores gravados poderão ser usados como "
        "entrada oficial para o motor de score — a extração por IA continua sendo rascunho).*"
    )

    if not empresa_id or usuario_id is None:
        st.info("Selecione uma empresa e mantenha sessão autenticada para gravar fatos validados.")
        return

    travado = documento_tem_fatos_validados_persistidos(msg)
    aid = msg.get("analise_id_fatos")

    if travado and aid:
        rows_db = listar_fatos_validados(int(aid))
        mapa = {r["nome_fato"]: r["valor_fato"] for r in rows_db}
        df_ro = pd.DataFrame(
            [{"Fato": k, "Valor": mapa.get(k, "—")} for k in CHAVES_JSON]
        )
        st.dataframe(df_ro, width="stretch")
        st.success("Fatos validados e salvos com sucesso!")
        st.caption("Edição bloqueada — valores conforme última aprovação gravada no banco.")
        return

    base = _fatos_padrao_para_ui(msg)
    df0 = _dataframe_editor_inicial(base)
    key_ed = f"doc_fatos_ed_{doc_uid}"
    key_bt = f"doc_fatos_aprov_{doc_uid}"

    edited = st.data_editor(
        df0,
        column_config={
            "Fato": st.column_config.TextColumn("Fato", disabled=True),
            "Valor": st.column_config.TextColumn("Valor"),
        },
        hide_index=True,
        width="stretch",
        key=key_ed,
        num_rows="fixed",
    )

    if st.button("Aprovar e Salvar Fatos", key=key_bt, type="primary"):
        aprovado_dict = _dict_desde_editor(edited)
        orig_ia = msg.get("fatos_ia_originais") or {}

        analise_id = msg.get("analise_id_fatos")
        if analise_id is None:
            analise_id = criar_analise_stub_validacao_fatos(int(empresa_id), int(usuario_id))
            sessao.atualizar_mensagem_documento(doc_uid, {"analise_id_fatos": int(analise_id)})

        linhas = []
        for _, row in edited.iterrows():
            nome_fato = str(row["Fato"]).strip()
            valor_fato = str(row["Valor"]).strip()
            fonte = _infer_fonte(nome_fato, valor_fato, orig_ia)
            linhas.append((nome_fato, valor_fato, fonte))

        substituir_fatos_validados(int(analise_id), int(usuario_id), linhas)

        st.session_state["ultimo_stub_analise_id_fatos_validados"] = int(analise_id)

        sessao.atualizar_mensagem_documento(
            doc_uid,
            {
                "fatos_extraidos": aprovado_dict,
                "fatos_validados_travado": True,
            },
        )
        aplicar_fatos_documento_na_sessao(sessao, aprovado_dict)

        case_id = st.session_state.get("relatorio_consultoria_case_id")
        if case_id:
            st.session_state.setdefault("timeline_por_caso", {})
            timeline = st.session_state["timeline_por_caso"].setdefault(str(case_id), [])
            perfil = str(st.session_state.get("perfil_usuario") or "usuário").strip().lower()
            perfil_label = perfil.capitalize() if perfil else "Usuário"
            autor_nome = str(st.session_state.get("user_nome") or "").strip() or "Usuário"
            if autor_nome == "Usuário":
                try:
                    autor_nome = str(obter_email_usuario(int(usuario_id)) or "").strip() or autor_nome
                except Exception:
                    pass
            nome_doc = str(msg.get("arquivo") or "documento")
            timeline.insert(
                0,
                {
                    "timestamp": datetime.now().isoformat(),
                    "autor": f"{autor_nome} ({perfil_label})",
                    "acao": f"Fatos do documento '{nome_doc}' foram validados.",
                    "origem": "documento",
                },
            )

        st.success("Fatos validados e salvos com sucesso!")
        st.rerun()
