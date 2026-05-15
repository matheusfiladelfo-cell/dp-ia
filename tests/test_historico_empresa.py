"""Histórico da empresa: rótulos amigáveis e resumo sem identificadores internos."""

from banco import rotulo_tipo_caso_para_exibicao


def test_rotulo_consultoria_conversa_amigavel():
    assert rotulo_tipo_caso_para_exibicao("consultoria_conversa") == "Análise de Risco Trabalhista"
    assert "consultoria" not in rotulo_tipo_caso_para_exibicao("consultoria_conversa").lower()


def test_rotulo_nao_expoe_snake_case_desconhecido():
    lab = rotulo_tipo_caso_para_exibicao("tipo_interno_xyz")
    assert "_" not in lab
    assert lab == "Análises trabalhistas registradas"
