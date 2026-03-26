from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

import os
from datetime import datetime


def gerar_pdf_parecer(empresa_nome, parecer, resultado):

    file_name = f"parecer_{datetime.now().timestamp()}.pdf"
    file_path = os.path.join(os.getcwd(), file_name)

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()

    # =========================
    # ESTILOS CUSTOM
    # =========================
    titulo = ParagraphStyle(
        'Titulo',
        fontSize=20,
        spaceAfter=20,
        textColor=colors.black
    )

    subtitulo = ParagraphStyle(
        'Subtitulo',
        fontSize=14,
        spaceAfter=10,
        textColor=colors.HexColor("#333333")
    )

    destaque = ParagraphStyle(
        'Destaque',
        fontSize=26,
        spaceAfter=20,
        textColor=colors.red
    )

    normal = styles["Normal"]

    story = []

    # =========================
    # CAPA PREMIUM
    # =========================
    story.append(Paragraph("DP-IA", titulo))
    story.append(Paragraph("Relatório Executivo de Risco Trabalhista", subtitulo))
    story.append(Spacer(1, 30))

    story.append(Paragraph(f"<b>Empresa:</b> {empresa_nome}", normal))
    story.append(Paragraph(
        f"<b>Data:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        normal
    ))

    story.append(Spacer(1, 50))

    story.append(Paragraph(
        "Este relatório apresenta uma análise estratégica de risco trabalhista, "
        "com base em inteligência artificial aplicada à legislação e prática da Justiça do Trabalho.",
        normal
    ))

    story.append(PageBreak())

    # =========================
    # RISCO (DESTAQUE FORTE)
    # =========================
    risco = parecer.get("risco", "N/A")

    cor = {
        "ALTO": colors.red,
        "MÉDIO": colors.orange,
        "BAIXO": colors.green
    }.get(risco, colors.black)

    story.append(Paragraph("Nível de Risco Identificado", subtitulo))

    story.append(Paragraph(
        f"<font color='{cor.hexval()}'><b>{risco}</b></font>",
        destaque
    ))

    story.append(Spacer(1, 20))

    # =========================
    # DIAGNÓSTICO
    # =========================
    story.append(Paragraph("Diagnóstico da Situação", subtitulo))
    story.append(Paragraph(parecer.get("diagnostico", ""), normal))

    story.append(Spacer(1, 20))

    # =========================
    # FUNDAMENTAÇÃO
    # =========================
    story.append(Paragraph("Fundamentação do Risco", subtitulo))
    story.append(Paragraph(parecer.get("motivo_risco", ""), normal))

    story.append(Spacer(1, 20))

    # =========================
    # IMPACTO FINANCEIRO
    # =========================
    impacto = parecer.get("impacto_financeiro", 0)

    story.append(Paragraph("Impacto Financeiro Estimado", subtitulo))

    story.append(Paragraph(
        f"<b>R$ {impacto:,.2f}</b>",
        ParagraphStyle(
            'Impacto',
            fontSize=22,
            textColor=colors.HexColor("#000000"),
            spaceAfter=20
        )
    ))

    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "O valor acima representa uma estimativa baseada em práticas recorrentes da Justiça do Trabalho, "
        "incluindo reflexos em férias, 13º salário, FGTS e demais verbas.",
        normal
    ))

    story.append(Spacer(1, 25))

    # =========================
    # RECOMENDAÇÕES
    # =========================
    story.append(Paragraph("Plano de Ação Recomendado", subtitulo))

    for acao in parecer.get("o_que_fazer", []):
        story.append(Paragraph(f"• {acao}", normal))
        story.append(Spacer(1, 5))

    story.append(Spacer(1, 30))

    # =========================
    # CONCLUSÃO
    # =========================
    story.append(Paragraph("Conclusão Estratégica", subtitulo))

    story.append(Paragraph(
        "A adoção imediata das medidas recomendadas é essencial para mitigação do risco trabalhista "
        "e prevenção de passivo judicial.",
        normal
    ))

    story.append(Spacer(1, 40))

    # =========================
    # ASSINATURA
    # =========================
    story.append(Paragraph(
        "DP-IA — Inteligência Aplicada à Gestão Trabalhista",
        normal
    ))

    story.append(Paragraph(
        "Matheus Filadelfo Pires da Costa",
        normal
    ))

    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Este documento possui caráter informativo e não substitui parecer jurídico formal.",
        styles["Italic"]
    ))

    doc.build(story)

    return file_path