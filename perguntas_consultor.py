def gerar_perguntas(dados):

    perguntas = []

    tipo_caso = dados.get("tipo_caso")

    # =====================================================
    # RESCISÃO
    # =====================================================

    if tipo_caso == "rescisao":

        if dados.get("tipo_rescisao") is None:
            perguntas.append({
                "pergunta": "A rescisão foi com ou sem justa causa?",
                "motivo": "O tipo de rescisão altera diretamente o risco jurídico.",
                "impacto": "ALTO"
            })

        if dados.get("gestante") is None:
            perguntas.append({
                "pergunta": "Existe possibilidade da funcionária estar gestante?",
                "motivo": "Estabilidade gestante pode tornar a demissão nula.",
                "impacto": "ALTO"
            })

        if dados.get("cipa") is None:
            perguntas.append({
                "pergunta": "O funcionário faz parte da CIPA?",
                "motivo": "Membros da CIPA possuem estabilidade.",
                "impacto": "ALTO"
            })

        if dados.get("retorno_inss") is None:
            perguntas.append({
                "pergunta": "O funcionário retornou recentemente do INSS?",
                "motivo": "Pode haver estabilidade provisória.",
                "impacto": "ALTO"
            })

        if dados.get("tempo_empresa_meses") is None:
            perguntas.append({
                "pergunta": "Qual é o tempo de empresa?",
                "motivo": "Impacta verbas e risco trabalhista.",
                "impacto": "MÉDIO"
            })

    # =====================================================
    # AFASTAMENTO
    # =====================================================

    elif tipo_caso in ["afastamento", "acidente_trabalho"]:

        if dados.get("dias_afastamento") is None:
            perguntas.append({
                "pergunta": "Quantos dias de afastamento foram indicados?",
                "motivo": "Define responsabilidade de pagamento entre empresa e INSS.",
                "impacto": "ALTO"
            })

        if dados.get("acidente_trabalho") is None:
            perguntas.append({
                "pergunta": "O afastamento é decorrente de acidente de trabalho ou doença comum?",
                "motivo": "Isso altera o tipo de benefício e estabilidade.",
                "impacto": "ALTO"
            })

    return perguntas