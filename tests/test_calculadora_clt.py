"""Testes do motor determinístico calculadora_clt."""

from application.calculadora_clt import (
    estimar_passivo_detalhado,
    formatar_passivo_markdown,
)
from application.score_engine_v2 import calcular_impacto_financeiro_v2


def test_fgts_e_horas_extras():
    det = estimar_passivo_detalhado(
        ["Trabalhador sem recolhimento de FGTS e horas extras aos sábados"],
        salario=2800.0,
        meses=12,
    )
    assert det["fgts"] > 0
    assert det["horas_extras"] > 0
    assert det["total"] > 0


def test_assedio_dano_moral():
    det = estimar_passivo_detalhado(
        ["Relato de assédio moral e burnout"],
        salario=5000.0,
        meses=24,
    )
    assert det["dano_moral"] == 25000.0


def test_markdown_formatado():
    det = estimar_passivo_detalhado(["fgts atrasado"], 3000.0, 6)
    md = formatar_passivo_markdown(det)
    assert "Estimativa de Passivo Trabalhista" in md
    assert "FGTS" in md
    assert "Total Estimado" in md


def test_integracao_score_engine_com_verbas():
    fatos = {
        "valor_salario": "R$ 2.800,00",
        "data_admissao": "01/01/2022",
        "data_demissao": "01/01/2024",
        "motivo_reclamacao": "FGTS não depositado e hora extra habitual",
    }
    total, _, _, md = calcular_impacto_financeiro_v2(fatos, 70)
    assert total > 0
    assert "FGTS" in md
