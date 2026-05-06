"""
Auditoria de risco em massa sobre funcionários sincronizados (integração payroll).
Regras simplificadas e rápidas — não substituem análise jurídica individual.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime

from banco import listar_funcionarios_integracao

_MIN_DIAS_10_ANOS = int(10 * 365.25)
_VAR_SALARIAL_FRAC = 0.20


def _norm_txt(s: str) -> str:
    t = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _norm_cargo(cargo: str | None) -> str:
    return " ".join(str(cargo or "").strip().lower().split()) or "(sem cargo)"


def _eh_vinculo_pj(tipo_contrato: str | None) -> bool:
    if tipo_contrato is None or not str(tipo_contrato).strip():
        return False
    t = _norm_txt(tipo_contrato)
    return bool(re.search(r"\bpj\b", t))


def _parse_data_admissao(val) -> date | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    low = s.lower()
    if low in {"não encontrado", "nao encontrado", "-", "n/a"}:
        return None
    if "T" in s:
        s = s.split("T", 1)[0].strip()
    elif len(s) > 10 and s[10] == " ":
        s = s[:10].strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            chunk = s[:10] if fmt == "%Y-%m-%d" else s
            return datetime.strptime(chunk, fmt).date()
        except ValueError:
            continue
    m = re.match(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    return None


def _median(vals: list[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return float(s[mid])
    return (float(s[mid - 1]) + float(s[mid])) / 2.0


def _salario_float(row: dict) -> float | None:
    sal = row.get("salario_bruto")
    if sal is None:
        return None
    try:
        v = float(sal)
    except (TypeError, ValueError):
        return None
    if v < 0:
        return None
    return v


def executar_auditoria_risco_massa(empresa_id: int) -> dict:
    """
    Varre empresa_funcionarios_integracao e aplica regras leves de risco.

    Retorno persistível em JSON (empresa_auditorias_risco.resultado_json).
    """
    eid = int(empresa_id)
    rows = listar_funcionarios_integracao(eid)
    total = len(rows)

    lista_riscos: list[dict] = []
    pj_ids: set[int] = set()
    eq_ids: set[int] = set()
    long_ids: set[int] = set()

    hoje = date.today()

    by_cargo: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cargo[_norm_cargo(r.get("cargo"))].append(r)

    # Risco vínculo PJ
    for r in rows:
        rid = int(r["id"])
        if _eh_vinculo_pj(r.get("tipo_contrato")):
            pj_ids.add(rid)
            lista_riscos.append(
                {
                    "id": rid,
                    "nome": str(r.get("nome_completo") or ""),
                    "employee_id_externo": str(r.get("employee_id_externo") or ""),
                    "risco": "Vínculo PJ",
                }
            )

    # Equiparação salarial (mesmo cargo, salário afastado >20% da mediana do grupo)
    for _cargo, members in by_cargo.items():
        if len(members) < 2:
            continue
        com_salario: list[tuple[dict, float]] = []
        for m in members:
            sf = _salario_float(m)
            if sf is None:
                continue
            com_salario.append((m, sf))
        if len(com_salario) < 2:
            continue
        med = _median([s for _, s in com_salario])
        if med <= 0:
            continue
        for m, sf in com_salario:
            if abs(sf - med) / med > _VAR_SALARIAL_FRAC:
                rid = int(m["id"])
                if rid not in eq_ids:
                    eq_ids.add(rid)
                    lista_riscos.append(
                        {
                            "id": rid,
                            "nome": str(m.get("nome_completo") or ""),
                            "employee_id_externo": str(m.get("employee_id_externo") or ""),
                            "risco": "Equiparação salarial (>20% vs mediana do cargo)",
                        }
                    )

    # Longo tempo de casa (>10 anos)
    for r in rows:
        adm = _parse_data_admissao(r.get("data_admissao"))
        if adm is None:
            continue
        if (hoje - adm).days >= _MIN_DIAS_10_ANOS:
            rid = int(r["id"])
            if rid not in long_ids:
                long_ids.add(rid)
                lista_riscos.append(
                    {
                        "id": rid,
                        "nome": str(r.get("nome_completo") or ""),
                        "employee_id_externo": str(r.get("employee_id_externo") or ""),
                        "risco": "Longo tempo de casa (>10 anos)",
                    }
                )

    lista_riscos.sort(key=lambda x: (str(x.get("nome") or "").lower(), str(x.get("risco") or "")))

    ids_com_qualquer = pj_ids | eq_ids | long_ids

    return {
        "total_funcionarios_auditados": total,
        "total_funcionarios_com_risco": len(ids_com_qualquer),
        "riscos_identificados": {
            "risco_vinculo_pj": len(pj_ids),
            "risco_equiparacao_salarial": len(eq_ids),
            "risco_longo_servico": len(long_ids),
        },
        "lista_funcionarios_risco": lista_riscos,
    }
