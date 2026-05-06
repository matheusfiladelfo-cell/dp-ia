"""
Contrato conceitual da API de integração payroll.

Implementação HTTP (FastAPI/Flask) ficará em camada separada; este módulo define
caminho, método e formato esperado para documentação e validações futuras.
"""

from __future__ import annotations

import json

# Endpoint RESTful planejado
INTEGRATION_PAYROLL_SYNC_METHOD = "POST"
INTEGRATION_PAYROLL_SYNC_PATH = "/api/v1/integrations/payroll/sync"

# Cabeçalho: Authorization: Bearer <API_KEY>


def montar_url_payroll_sync(api_base_url: str) -> str:
    base = str(api_base_url or "").strip().rstrip("/")
    if not base:
        base = "https://<seu-dominio>"
    return f"{base}{INTEGRATION_PAYROLL_SYNC_PATH}"


PAYLOAD_EXEMPLO_DICT = {
    "employees": [
        {
            "employee_id_externo": "12345",
            "nome_completo": "Mariana Oliveira",
            "data_admissao": "2021-06-15",
            "cargo": "Analista de Marketing",
            "salario_bruto": 5500.00,
            "tipo_contrato": "CLT",
        }
    ]
}


def payload_exemplo_json_compacto() -> str:
    return json.dumps(PAYLOAD_EXEMPLO_DICT, ensure_ascii=False, indent=2)


# Fluxo planejado do endpoint (quando o servidor REST existir):
# 1. Ler Authorization: Bearer <token>.
# 2. banco.validar_api_key(token) → empresa_id ou None.
# 3. Se inválido: HTTP 401.
# 4. Validar JSON com lista `employees` (campos como em PAYLOAD_EXEMPLO_DICT).
# 5. banco.upsert_funcionarios_integracao_lote(empresa_id, employees).
# 6. HTTP 200 com resumo (ex.: quantidade upsertada).
