from datetime import datetime
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _decisao_executiva(score):
    if score >= 80:
        return "NAO PROSSEGUIR", "Exposicao juridica muito elevada para continuidade."
    if score >= 60:
        return "PROSSEGUIR COM CAUTELA", "Prosseguir apenas com mitigacoes e plano de controle."
    return "SEGURO PARA PROSSEGUIR", "Cenario com risco controlado para continuidade."


def _risco_visual(risco):
    risco_up = str(risco or "N/A").upper()
    mapa = {
        "ALTO": ("ALTO", colors.HexColor("#b91c1c")),
        "MÉDIO": ("MEDIO", colors.HexColor("#d97706")),
        "MEDIO": ("MEDIO", colors.HexColor("#d97706")),
        "BAIXO": ("BAIXO", colors.HexColor("#15803d")),
    }
    return mapa.get(risco_up, ("N/A", colors.HexColor("#334155")))


def gerar_pdf_parecer(empresa_nome, parecer, resultado):
    file_name = f"parecer_{datetime.now().timestamp()}.pdf"
    file_path = os.path.join(os.getcwd(), file_name)

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
    )

    styles = getSampleStyleSheet()

    titulo_capa = ParagraphStyle(
        "TituloCapa",
        parent=styles["Title"],
        fontSize=26,
        leading=30,
        textColor=colors.white,
        alignment=0,
    )
    subtitulo_capa = ParagraphStyle(
        "SubtituloCapa",
        parent=styles["Normal"],
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#dbeafe"),
    )
    secao = ParagraphStyle(
        "Secao",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=6,
        spaceAfter=8,
    )
    normal = ParagraphStyle(
        "NormalCustom",
        parent=styles["Normal"],
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#1f2937"),
    )
    destaque = ParagraphStyle(
        "DestaqueValor",
        parent=styles["Normal"],
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#0f172a"),
    )
    pequeno = ParagraphStyle(
        "Pequeno",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
    )

    story = []

    risco_raw = parecer.get("risco", "N/A")
    risco_label, risco_color = _risco_visual(risco_raw)
    score = _to_int(resultado.get("score"), 0)
    nivel = str(resultado.get("nivel", "N/A"))
    probabilidade = _to_int(resultado.get("probabilidade"), 0)
    impacto = _to_float(parecer.get("impacto_financeiro", 0), 0)
    decisao_titulo, decisao_desc = _decisao_executiva(score)

    capa = Table(
        [[
            Paragraph("DP-IA", pequeno),
            Paragraph("Relatorio Executivo de Risco Trabalhista", titulo_capa),
            Paragraph(
                f"Empresa: <b>{empresa_nome}</b><br/>Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                subtitulo_capa,
            ),
        ]],
        colWidths=[doc.width],
    )
    capa.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                ("LEFTPADDING", (0, 0), (-1, -1), 20),
                ("RIGHTPADDING", (0, 0), (-1, -1), 20),
                ("TOPPADDING", (0, 0), (-1, -1), 22),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 24),
            ]
        )
    )
    story.append(capa)
    story.append(Spacer(1, 18))

    story.append(Paragraph("Resumo Executivo", secao))
    story.append(
        Paragraph(
            "Este documento consolida o panorama de risco trabalhista, a recomendacao executiva "
            "e os principais impactos para suporte a tomada de decisao do RH e da lideranca.",
            normal,
        )
    )
    story.append(Spacer(1, 14))

    kpi_table = Table(
        [[
            Paragraph(f"<b>Score</b><br/><font size='15'>{score}/100</font>", normal),
            Paragraph(f"<b>Risco</b><br/><font size='15' color='{risco_color.hexval()}'>{risco_label}</font>", normal),
            Paragraph(f"<b>Probabilidade</b><br/><font size='15'>{probabilidade}%</font>", normal),
            Paragraph(f"<b>Nivel</b><br/><font size='15'>{nivel}</font>", normal),
        ]],
        colWidths=[doc.width / 4.0] * 4,
    )
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(kpi_table)
    story.append(Spacer(1, 16))

    decisao_box = Table(
        [[
            Paragraph(
                f"<font size='8'>DECISAO EXECUTIVA</font><br/><font size='16'><b>{decisao_titulo}</b></font><br/>{decisao_desc}",
                ParagraphStyle(
                    "DecisaoStyle",
                    parent=normal,
                    textColor=colors.white,
                    leading=16,
                ),
            )
        ]],
        colWidths=[doc.width],
    )
    decisao_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1d4ed8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#1e3a8a")),
            ]
        )
    )
    story.append(decisao_box)
    story.append(Spacer(1, 16))

    story.append(Paragraph("Analise do Caso", secao))
    story.append(Paragraph(str(parecer.get("diagnostico", "-")), normal))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Fundamentacao Juridica", secao))
    story.append(Paragraph(str(parecer.get("fundamentacao", "-")), normal))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Impactos Trabalhistas", secao))
    story.append(Paragraph(str(parecer.get("impactos", "-")), normal))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Impacto Financeiro Estimado", secao))
    story.append(Paragraph(f"<b>R$ {impacto:,.2f}</b>", destaque))
    story.append(
        Paragraph(
            "Estimativa baseada nos dados informados, com potencial reflexo em FGTS, ferias + 1/3, "
            "13o salario, DSR e demais verbas aplicaveis.",
            pequeno,
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("Orientacao Estrategica", secao))
    story.append(Paragraph(str(parecer.get("recomendacao", "-")), normal))

    story.append(PageBreak())
    story.append(Paragraph("Conclusao Executiva", secao))
    story.append(
        Paragraph(
            "A recomendacao acima deve orientar a decisao do RH, priorizando reducao de exposicao "
            "juridica e protecao financeira da operacao.",
            normal,
        )
    )
    story.append(Spacer(1, 22))
    story.append(Paragraph("DP-IA | Relatorio estilo consultoria", pequeno))
    story.append(
        Paragraph(
            "Documento informativo para apoio a decisao. Nao substitui parecer juridico formal.",
            styles["Italic"],
        )
    )

    doc.build(story)
    return file_path
