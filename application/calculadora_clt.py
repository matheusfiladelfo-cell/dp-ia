"""
Motor determinístico de estimativa de passivo trabalhista (palavras-chave + regras fixas).
Não utiliza LLM; apenas leitura de textos de fatos validados.
"""

from __future__ import annotations

import unicodedata

# Base média informada na especificação (adicional de insalubridade 20%).
SALARIO_MINIMO_REFERENCIA = 1412.00
HORAS_EXTRAS_MENSAIS_ESTIMADAS = 40
DIVISOR_HORA_EXTRA = 220
MULTIPLICADOR_HORA_EXTRA = 1.5
PERCENTUAL_FGTS = 0.08
PERCENTUAL_INSALUBRIDADE = 0.20
PERCENTUAL_REFLEXOS = 0.30
MULTIPLICADOR_DANO_MORAL_SALARIOS = 5


def _norm_texto(s: str) -> str:
    t = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _texto_consolidado(fatos_textos: list[str]) -> str:
    return _norm_texto(" ".join(str(t or "") for t in fatos_textos))


def _fmt_brl(valor: float) -> str:
    v = float(valor or 0)
    inteiro, dec = f"{v:,.2f}".split(".")
    inteiro = inteiro.replace(",", ".")
    return f"R$ {inteiro},{dec}"


def estimar_passivo_detalhado(
    fatos_textos: list[str], salario: float, meses: int
) -> dict:
    """
    Estima verbas por palavras-chave nos fatos.
    Retorna valores por rubrica e total (0 nas rubricas não identificadas).
    """
    try:
        sal = float(salario)
        m = max(1, int(meses))
    except (TypeError, ValueError):
        return {
            "fgts": 0.0,
            "insalubridade": 0.0,
            "horas_extras": 0.0,
            "reflexos": 0.0,
            "dano_moral": 0.0,
            "total": 0.0,
            "rubicas_ativas": [],
        }

    if sal <= 0:
        return {
            "fgts": 0.0,
            "insalubridade": 0.0,
            "horas_extras": 0.0,
            "reflexos": 0.0,
            "dano_moral": 0.0,
            "total": 0.0,
            "rubicas_ativas": [],
        }

    texto = _texto_consolidado(fatos_textos)
    rubricas_ativas: list[str] = []

    fgts = 0.0
    if "fgts" in texto:
        fgts = (sal * PERCENTUAL_FGTS) * m
        rubricas_ativas.append("fgts")

    insalubridade = 0.0
    if any(
        k in texto
        for k in ("insalubridade", "epi", "ruido", "quimico")
    ):
        insalubridade = (SALARIO_MINIMO_REFERENCIA * PERCENTUAL_INSALUBRIDADE) * m
        rubricas_ativas.append("insalubridade")

    horas_extras = 0.0
    if any(
        k in texto
        for k in ("hora extra", "horas extras", "jornada", "sabado")
    ):
        horas_extras = (
            (sal / DIVISOR_HORA_EXTRA) * MULTIPLICADOR_HORA_EXTRA * HORAS_EXTRAS_MENSAIS_ESTIMADAS * m
        )
        rubricas_ativas.append("horas_extras")

    dano_moral = 0.0
    if any(k in texto for k in ("assedio", "xingamento", "burnout")):
        dano_moral = sal * MULTIPLICADOR_DANO_MORAL_SALARIOS
        rubricas_ativas.append("dano_moral")

    reflexos = 0.0
    base_reflexos = horas_extras + insalubridade
    if base_reflexos > 0:
        reflexos = base_reflexos * PERCENTUAL_REFLEXOS
        rubricas_ativas.append("reflexos")

    total = fgts + insalubridade + horas_extras + reflexos + dano_moral

    return {
        "fgts": round(fgts, 2),
        "insalubridade": round(insalubridade, 2),
        "horas_extras": round(horas_extras, 2),
        "reflexos": round(reflexos, 2),
        "dano_moral": round(dano_moral, 2),
        "total": round(total, 2),
        "rubicas_ativas": rubricas_ativas,
        "salario_base": round(sal, 2),
        "meses_servico": m,
    }


def formatar_passivo_markdown(detalhe: dict) -> str:
    """Formata o dicionário da calculadora em Markdown para exibição."""
    linhas: list[str] = ["**Estimativa de Passivo Trabalhista:**"]

    if float(detalhe.get("fgts") or 0) > 0:
        linhas.append(f"* FGTS (Atraso/Multa): {_fmt_brl(detalhe['fgts'])}")

    he_ref = float(detalhe.get("horas_extras") or 0) + float(detalhe.get("reflexos") or 0)
    if he_ref > 0:
        linhas.append(f"* Horas Extras e Reflexos: {_fmt_brl(he_ref)}")

    if float(detalhe.get("insalubridade") or 0) > 0:
        linhas.append(f"* Insalubridade: {_fmt_brl(detalhe['insalubridade'])}")

    if float(detalhe.get("dano_moral") or 0) > 0:
        linhas.append(f"* Possível Dano Moral: {_fmt_brl(detalhe['dano_moral'])}")

    total = float(detalhe.get("total") or 0)
    linhas.append(f"**Total Estimado: {_fmt_brl(total)}**")
    linhas.append(
        "*(Nota: Cálculo estimado com base nos fatos relatados para fins de provisionamento)*"
    )
    return "\n".join(linhas)


def fatos_dict_para_textos(fatos: dict) -> list[str]:
    """Extrai strings dos fatos validados para busca de palavras-chave."""
    textos: list[str] = []
    for valor in (fatos or {}).values():
        if valor is None:
            continue
        if isinstance(valor, (list, tuple)):
            textos.extend(str(x) for x in valor if str(x).strip())
        else:
            s = str(valor).strip()
            if s and s.lower() not in {"não encontrado", "nao encontrado", "n/a", "-"}:
                textos.append(s)
    return textos
