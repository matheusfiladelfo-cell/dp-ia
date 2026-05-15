"""
Geração de PDF do Relatório Completo (fpdf2 + fonte Unicode).
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

_FONTS_DIR = Path(__file__).resolve().parent / "fonts"

_FONT_CANDIDATES: list[tuple[str, str | None]] = [
    (_FONTS_DIR / "DejaVuSans.ttf", _FONTS_DIR / "DejaVuSans-Bold.ttf"),
    (Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf")),
    (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    (Path("/usr/share/fonts/TTF/DejaVuSans.ttf"), Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf")),
    (Path("/Library/Fonts/Arial.ttf"), Path("/Library/Fonts/Arial Bold.ttf")),
]


def _resolver_fontes() -> tuple[Path, Path | None]:
    for regular, bold in _FONT_CANDIDATES:
        if regular.is_file():
            bold_path = bold if bold and bold.is_file() else None
            return regular, bold_path
    raise FileNotFoundError(
        "Nenhuma fonte TTF Unicode encontrada. Coloque DejaVuSans.ttf em application/fonts/ "
        "ou instale DejaVu/Arial no sistema."
    )


def _plain_text(texto: str) -> str:
    s = str(texto or "").strip()
    if not s:
        return ""
    s = re.sub(r"^#+\s*", "", s, flags=re.MULTILINE)
    s = s.replace("**", "").replace("__", "")
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s.strip()


def _as_text(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (list, tuple)):
        return "\n".join(_as_text(v) for v in valor if str(v or "").strip())
    return str(valor).strip()


class _RelatorioPDF(FPDF):
    def __init__(self, font_regular: Path, font_bold: Path | None):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=18)
        family = "RelatorioUTF"
        self.add_font(family, "", str(font_regular))
        if font_bold:
            self.add_font(family, "B", str(font_bold))
        else:
            self.add_font(family, "B", str(font_regular))
        self._family = family

    def _titulo_secao(self, titulo: str) -> None:
        self.ln(5)
        self.set_font(self._family, "B", 12)
        self.multi_cell(0, 7, titulo, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def _corpo(self, texto: str, *, markdown: bool = False) -> None:
        self.set_font(self._family, "", 10)
        conteudo = (texto or "").strip() or "—"
        self.multi_cell(
            0,
            5,
            conteudo,
            markdown=markdown,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )


def gerar_pdf_relatorio(dados_relatorio: dict) -> bytes:
    """
    Monta o PDF do relatório completo a partir de um dicionário de textos.

    Chaves esperadas (str ou list[str]):
      risco, score, diagnostico, impacto_financeiro, acao, estrategia, base_legal
    """
    font_regular, font_bold = _resolver_fontes()
    pdf = _RelatorioPDF(font_regular, font_bold)
    pdf.add_page()

    pdf.set_font(pdf._family, "B", 14)
    pdf.multi_cell(
        0,
        8,
        "M&P Consultoria - Relatório de Risco Trabalhista",
        align="C",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_font(pdf._family, "", 9)
    pdf.multi_cell(
        0,
        5,
        f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        align="C",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(4)

    risco = _as_text(dados_relatorio.get("risco")) or "INCONCLUSIVO"
    score = _as_text(dados_relatorio.get("score"))
    bloco_risco = f"Nível de risco: {risco.upper()}"
    if score:
        bloco_risco = f"{bloco_risco}\n\n{score}"
    pdf._titulo_secao("Nível de Risco e Score")
    pdf._corpo(bloco_risco)

    pdf._titulo_secao("Diagnóstico Detalhado")
    pdf._corpo(_plain_text(_as_text(dados_relatorio.get("diagnostico"))))

    impacto = _as_text(dados_relatorio.get("impacto_financeiro"))
    pdf._titulo_secao("Impacto Financeiro")
    if "**" in impacto or impacto.startswith("* "):
        pdf._corpo(impacto, markdown=True)
    else:
        pdf._corpo(impacto)

    pdf._titulo_secao("Plano de Ação")
    pdf._corpo(_plain_text(_as_text(dados_relatorio.get("acao"))))

    pdf._titulo_secao("Estratégia Jurídica")
    pdf._corpo(_plain_text(_as_text(dados_relatorio.get("estrategia"))))

    pdf._titulo_secao("Base Legal")
    pdf._corpo(_plain_text(_as_text(dados_relatorio.get("base_legal"))))

    pdf.ln(6)
    pdf.set_font(pdf._family, "", 8)
    pdf.multi_cell(
        0,
        4,
        "Documento gerado automaticamente. Não substitui parecer jurídico individualizado.",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    raw = pdf.output()
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return raw.encode("latin-1", errors="replace")
