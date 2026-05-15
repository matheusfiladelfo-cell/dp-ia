"""Testes do gerador de PDF do relatório."""

from pathlib import Path

import pytest

from application.pdf_generator import gerar_pdf_relatorio


def _fonte_disponivel() -> bool:
    from application import pdf_generator as pg

    try:
        pg._resolver_fontes()
        return True
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not _fonte_disponivel(), reason="Fonte TTF Unicode não disponível no ambiente")
def test_gerar_pdf_relatorio_retorna_bytes_pdf():
    dados = {
        "risco": "ALTO",
        "score": "Score v2: ALTO (78/100)",
        "diagnostico": "Possível vínculo irregular identificado nos fatos.",
        "impacto_financeiro": "**Estimativa de Passivo Trabalhista:**\n* FGTS: R$ 1.200,00\n**Total Estimado: R$ 1.200,00**",
        "acao": "• Validar documentos\n• Evitar demissão imediata",
        "estrategia": "Priorizar regularização antes de rescisão.",
        "base_legal": "• Art. 7º CF\n• CLT art. 477",
    }
    pdf_bytes = gerar_pdf_relatorio(dados)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 500


@pytest.mark.skipif(not _fonte_disponivel(), reason="Fonte TTF Unicode não disponível no ambiente")
def test_pdf_com_acentuacao_portugues():
    dados = {
        "risco": "MÉDIO",
        "score": "Score v1: MÉDIO (45/100)",
        "diagnostico": "Análise com acentuação: ação, estratégia, insalubridade.",
        "impacto_financeiro": "Total a estimar.",
        "acao": "Próximos passos recomendados.",
        "estrategia": "Negociação prévia.",
        "base_legal": "Legislação trabalhista brasileira.",
    }
    pdf_bytes = gerar_pdf_relatorio(dados)
    assert pdf_bytes.startswith(b"%PDF")
