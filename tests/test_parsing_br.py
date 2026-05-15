"""Testes de parsing BRL para impacto financeiro."""

from application.parsing_br import parse_moeda_br, parse_tempo_meses_fatos
from application.score_engine_v2 import calcular_impacto_financeiro_v2, calcular_score_v2_1


def test_parse_moeda_br_formatos():
    assert parse_moeda_br("R$ 2.800,00") == 2800.0
    assert parse_moeda_br("2.800,00") == 2800.0
    assert parse_moeda_br("2800") == 2800.0
    assert parse_moeda_br("4.500") == 4500.0
    assert parse_moeda_br(5200) == 5200.0
    assert parse_moeda_br("") is None
    assert parse_moeda_br("Não encontrado") is None


def test_parse_tempo_meses_fatos():
    fatos_datas = {
        "data_admissao": "01/01/2022",
        "data_demissao": "01/05/2024",
    }
    assert parse_tempo_meses_fatos(fatos_datas) >= 12

    fatos_int = {"tempo_empresa_meses": 52}
    assert parse_tempo_meses_fatos(fatos_int) == 52

    fatos_texto = {"motivo_reclamacao": "trabalhou 18 meses sem registro"}
    assert parse_tempo_meses_fatos(fatos_texto) == 18


def test_impacto_financeiro_com_salario_brl():
    fatos = {
        "tipo_contrato": "CLT",
        "data_admissao": "10/03/2023",
        "data_demissao": "01/05/2024",
        "valor_salario": "R$ 2.800,00",
        "motivo_reclamacao": "Verbas rescisórias",
        "evidencias_mencionadas": "",
    }
    impacto, _, _ = calcular_impacto_financeiro_v2(fatos, 50)
    assert impacto > 0

    _, _, racional, _, _, _, _ = calcular_score_v2_1(fatos)
    assert not any(
        "não foi possível estimar" in str(l).lower() for l in racional
    )
