"""
Parsing de moeda, datas e tempo no padrão brasileiro (BRL, dd/mm/aaaa).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Any

_NAO_ENCONTRADO = frozenset(
    {
        "",
        "não encontrado",
        "nao encontrado",
        "n/a",
        "-",
        "null",
        "none",
    }
)


def _eh_vazio(val: Any) -> bool:
    x = str(val or "").strip().lower()
    return not x or x in _NAO_ENCONTRADO


def parse_moeda_br(valor: Any) -> float | None:
    """
    Converte salário/remuneração em float.
    Aceita: 2800, "R$ 2.800,00", "2.800,00", 2800.5, etc.
    """
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        try:
            v = float(valor)
            return v if v > 0 else None
        except (TypeError, ValueError):
            return None

    s = unicodedata.normalize("NFKC", str(valor).strip())
    if _eh_vazio(s):
        return None

    s = s.replace("\u00a0", "").replace(" ", "")
    s = re.sub(r"^[Rr]\$", "", s)
    s = re.sub(r"[^\d,.-]", "", s)
    if not s or s in {".", ",", "-"}:
        return None

    try:
        if "," in s:
            if "." in s:
                s = s.replace(".", "")
            s = s.replace(",", ".")
        elif "." in s:
            partes = s.split(".")
            if len(partes) > 1 and all(len(p) == 3 for p in partes[1:]):
                s = "".join(partes)
            elif len(partes) == 2 and len(partes[1]) == 3 and partes[0].isdigit():
                s = partes[0] + partes[1]
        v = float(s)
    except (TypeError, ValueError):
        return None

    return v if v > 0 else None


def parse_data_br(val: str | None) -> date | None:
    """Interpreta datas comuns no Brasil e ISO."""
    if val is None or _eh_vazio(val):
        return None
    s = str(val).strip()
    for fmt in (
        "%d/%m/%Y",
        "%d/%m/%y",
        "%d-%m-%Y",
        "%d-%m-%y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(s[:19], fmt).date()
        except ValueError:
            continue
    m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    return None


def meses_entre_datas(data_admissao: str, data_demissao: str) -> int:
    """Diferença aproximada em meses entre admissão e demissão (ou hoje)."""
    adm = parse_data_br(data_admissao)
    if adm is None:
        return 0
    dem = parse_data_br(data_demissao) or date.today()
    if dem < adm:
        return 0
    dias = max(0, (dem - adm).days)
    return max(1, int(round(dias / 30.44)))


def extrair_meses_de_texto(texto: str) -> int:
    """Ex.: '52 meses', '4 anos' → inteiro de meses."""
    if not texto:
        return 0
    t = str(texto).lower()
    m = re.search(r"(\d+)\s*(?:mes|meses)\b", t)
    if m:
        try:
            return max(0, int(m.group(1)))
        except ValueError:
            return 0
    m = re.search(r"(\d+)\s*(?:ano|anos)\b", t)
    if m:
        try:
            return max(0, int(m.group(1))) * 12
        except ValueError:
            return 0
    return 0


def parse_tempo_meses_fatos(fatos: dict) -> int:
    """
    Ordem: tempo_meses / tempo_empresa_meses explícitos → texto → datas de admissão/demissão.
    """
    for chave in ("tempo_meses", "tempo_empresa_meses", "tempo_servico_meses"):
        bruto = fatos.get(chave)
        if bruto is None or _eh_vazio(bruto):
            continue
        try:
            meses = int(float(str(bruto).strip().replace(",", ".")))
            if meses > 0:
                return meses
        except (TypeError, ValueError):
            continue

    texto = " ".join(
        str(fatos.get(k) or "")
        for k in ("tempo_servico", "tempo_empresa", "motivo_reclamacao", "cargo")
    )
    meses_txt = extrair_meses_de_texto(texto)
    if meses_txt > 0:
        return meses_txt

    return meses_entre_datas(
        str(fatos.get("data_admissao") or ""),
        str(fatos.get("data_demissao") or ""),
    )
