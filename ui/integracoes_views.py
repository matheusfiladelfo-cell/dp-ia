"""
Painel de integrações (payroll / RH) — exclusivo administradores da empresa na UI.
"""

from __future__ import annotations

import json
import os

import streamlit as st

from application.integrations_api_contract import (
    INTEGRATION_PAYROLL_SYNC_METHOD,
    INTEGRATION_PAYROLL_SYNC_PATH,
    PAYLOAD_EXEMPLO_DICT,
    montar_url_payroll_sync,
    payload_exemplo_json_compacto,
)
from banco import (
    contar_funcionarios_integracao,
    gerar_e_salvar_api_key,
    obter_metadados_chave_api_ativa,
    obter_ultima_sincronizacao_funcionarios,
    revogar_api_key,
)


def _session_plain_key(empresa_id: int) -> str:
    return f"_payroll_api_plain_secret_{int(empresa_id)}"


def render_integracoes(_usuario_id: int, empresa_id: int, empresa_nome: str):
    st.markdown("### 🔌 Integrações")
    st.caption(
        f"Empresa: **{empresa_nome}** · Configure chaves de API para sincronização de dados de funcionários."
    )

    api_base = os.getenv("PUBLIC_API_BASE_URL", "").strip() or "https://<seu-dominio>"
    url_sync = montar_url_payroll_sync(api_base)

    meta = obter_metadados_chave_api_ativa(empresa_id)
    ultima = obter_ultima_sincronizacao_funcionarios(empresa_id)
    total_fun = contar_funcionarios_integracao(empresa_id)

    ativa = meta is not None
    ultima_txt = ultima or "Nunca registrada"
    linha_chave = ""
    if ativa and meta:
        linha_chave = (
            f'<p style="margin:10px 0 0 0; font-size:0.92rem; color:#94a3b8;">'
            f'Chave criada em: <strong>{meta.get("criada_em") or "—"}</strong></p>'
        )
    badge = (
        "🟢 <strong>Ativa</strong> — há uma chave de API válida."
        if ativa
        else "⚪ <strong>Inativa</strong> — gere uma chave para permitir chamadas à API."
    )
    st.markdown(
        f"""
<div class="dpia-report-card" style="border: 1px solid #334155; padding: 16px; margin-bottom: 16px;">
  <strong>Status da integração</strong>
  <p style="margin:12px 0 0 0;">{badge}</p>
  {linha_chave}
  <p style="margin:10px 0 0 0; font-size:0.92rem; color:#94a3b8;">
    Última sincronização (último upsert de funcionários): <strong>{ultima_txt}</strong>
  </p>
  <p style="margin:4px 0 0 0; font-size:0.92rem; color:#94a3b8;">
    Funcionários na base de integração: <strong>{total_fun}</strong>
  </p>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("#### Chave de API")
    sk_plain = _session_plain_key(empresa_id)
    plain_visivel = st.session_state.get(sk_plain)

    if plain_visivel:
        st.warning(
            "Copie a chave agora. Ela não poderá ser recuperada depois — apenas revogada e substituída."
        )
        st.text_input(
            "Segredo da API (mostrada uma vez nesta sessão)",
            value=plain_visivel,
            disabled=True,
            key=f"api_plain_show_{empresa_id}",
        )
    else:
        placeholder = (
            "••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••"
            if ativa
            else "(sem chave ativa — use Gerar Nova Chave)"
        )
        st.text_input(
            "Segredo da API",
            value=placeholder,
            disabled=True,
            key=f"api_masked_{empresa_id}_{ativa}",
        )

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Gerar Nova Chave", type="primary", key=f"gen_api_{empresa_id}"):
            novo = gerar_e_salvar_api_key(empresa_id)
            st.session_state[sk_plain] = novo
            st.success("Nova chave criada. Guarde-a em local seguro.")
            st.rerun()
    with col_b:
        if st.button("Revogar Chave", key=f"rev_api_{empresa_id}"):
            revogar_api_key(empresa_id)
            st.session_state.pop(sk_plain, None)
            st.info("Chaves ativas desta empresa foram revogadas.")
            st.rerun()

    curl_json_linha = json.dumps(PAYLOAD_EXEMPLO_DICT, ensure_ascii=False, separators=(",", ":"))

    with st.expander("Instruções para o time de TI (endpoint e exemplo curl)", expanded=False):
        st.markdown(
            f"""
**Método e caminho:** `{INTEGRATION_PAYROLL_SYNC_METHOD} {INTEGRATION_PAYROLL_SYNC_PATH}`

**URL base configurável:** defina a variável de ambiente `PUBLIC_API_BASE_URL` no servidor da aplicação
para refletir o domínio público onde a API REST será exposta (quando implementada).

**URL de exemplo (montagem):** `{url_sync}`

**Autenticação:** envie o segredo no cabeçalho HTTP:

`Authorization: Bearer <SUA_API_KEY>`

**Corpo da requisição:** JSON com a lista `employees`:

```json
{payload_exemplo_json_compacto()}
```

**Exemplo com curl:**

```bash
curl -X POST "{url_sync}" \\
  -H "Authorization: Bearer SUA_API_KEY_AQUI" \\
  -H "Content-Type: application/json" \\
  -d '{curl_json_linha}'
```

**Nota:** nesta fase o endpoint HTTP ainda não está exposto pelo Streamlit; o modelo de dados,
hash da chave e esta interface já permitem preparar o cliente e auditar chaves com segurança.
"""
        )
