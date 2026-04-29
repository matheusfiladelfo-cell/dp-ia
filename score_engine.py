# score_engine.py

import re


def tipo_efetivo_para_score(dados):
    """
    Combina classificador (tipo_risco) e regras textuais (tipo_caso).
    Evita que tipo_risco='geral' — típico quando a IA é genérica — silencie
    rescisão, hora extra, etc. detectadas por palavras-chave no analisador.
    """
    if not isinstance(dados, dict):
        return "geral"
    tc = dados.get("tipo_caso")
    tr = str(dados.get("tipo_risco") or "").strip().lower()
    if tc == "pedido_demissao":
        return "pedido_demissao"
    if tr in ("geral", "inconclusivo", ""):
        return tc or tr or "geral"
    return tr or tc or "geral"


def normalizar_risco(risco):
    if isinstance(risco, (int, float)):
        return min(max(float(risco), 0.0), 1.0)

    risco = str(risco or "").strip().upper()
    mapa = {
        "INCONCLUSIVO": 0.40,
        "BAIXO": 0.25,
        "MEDIO": 0.50,
        "MÉDIO": 0.50,
        "MÉDIO-ALTO": 0.65,
        "MEDIO-ALTO": 0.65,
        "ALTO": 0.88,
    }
    return mapa.get(risco, 0.45)


def normalizar_impacto(valor):
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return 0.2

    if valor <= 0:
        return 0.2
    if valor < 5000:
        return 0.3
    if valor < 20000:
        return 0.5
    if valor < 50000:
        return 0.75
    return 1.0


def _peso_tipo_juridico(tipo):
    tipo = str(tipo or "").lower()
    pesos = {
        "geral": 0.35,
        "rescisao": 0.60,
        "afastamento": 0.62,
        "hora_extra": 0.55,
        "conflito_interpessoal": 0.48,
        "assedio_moral": 0.78,
        "acidente_trabalho": 0.75,
        "pedido_demissao": 0.20,
        "rescisao_pedido": 0.20,
    }
    return pesos.get(tipo, 0.50)


def _nivel_por_score(score):
    if score >= 75:
        return "ALTO"
    if score >= 55:
        return "MÉDIO-ALTO"
    if score >= 35:
        return "MÉDIO"
    return "BAIXO"


def _probabilidade_por_score(score):
    # Curva simples e contínua (sem saltos agressivos).
    prob = int(round(8 + (score * 0.82)))
    return max(10, min(prob, 88))


def _detectar_hard_rule_juridica(case_data):
    # Estado local para garantir execução limpa por caso.
    texto = str(case_data.get("texto") or case_data.get("descricao") or "").lower()
    termos_gestante = ["gestante", "gravidez", "grávida", "gravida", "gestação", "gestacao"]
    termos_desligamento = ["demissão", "demissao", "desligamento", "mandei embora", "dispensa", "dispensada", "dispensado", "dispensei"]
    termos_verbas_nao_pagas = [
        "não paguei rescisão",
        "nao paguei rescisao",
        "sem pagar nada",
        "sem acerto",
        "verbas não pagas",
        "verbas nao pagas",
        "verbas rescisórias não pagas",
        "verbas rescisorias nao pagas",
    ]
    termos_sem_prova = ["sem prova", "sem documento", "sem testemunha", "nao tenho prova", "não tenho prova"]
    termos_sem_registro = ["sem carteira", "sem registro", "trabalhou sem registrar"]
    termos_acidente = ["acidente", "acidente de trabalho", "machucou", "queda"]
    termos_sem_cat = ["não abriu cat", "nao abriu cat", "sem cat", "nao fiz cat", "não fiz cat"]
    termos_assedio = ["assédio", "assedio"]
    termos_provas_assedio = ["prints", "print", "áudio", "audio", "testemunha"]
    # Evita disparar HE em consultas meramente preventivas ("limite de horas extras").
    termos_horas_extras = [
        "hora extra todo dia",
        "horas extras todo dia",
        "hora extra habitual",
        "horas extras habitual",
        "jornada excessiva",
    ]
    termos_pedido_demissao = ["pedido de demissão", "pedido de demissao", "pediu a conta", "pediu demissao"]
    termos_quitacao = ["paguei tudo", "recibos", "documentos", "quitação total", "quitacao total"]
    termos_fgts_atraso = [
        "sem fgts",
        "fgts atrasado",
        "fgts em atraso",
        "fgts não recolhido",
        "fgts nao recolhido",
        "nao recolheu fgts",
        "não recolheu fgts",
        "nao depositou fgts",
        "não depositou fgts",
    ]
    termos_pj_subordinado = ["contrato pj", "pj", "pessoa jurídica", "pessoa juridica"]
    termos_subordinacao = ["batia ponto", "subordinação", "subordinacao", "chefe direto", "ordens diretas"]
    termos_terceirizado = ["terceirizado", "terceirizada"]
    termos_ferias_vencidas = ["férias vencidas", "ferias vencidas", "férias não pagas", "ferias nao pagas"]
    termos_acao_judicial = [
        "ação judicial",
        "acao judicial",
        "entrou na justiça",
        "entrou na justica",
        "processo trabalhista",
        "mandado de segurança",
        "mandado de seguranca",
        "ação civil",
        "acao civil",
        "cumprimento de sentença",
        "cumprimento de sentenca",
        "ação rescisória",
        "acao rescisoria",
    ]
    # Não usar o token isolado "inicial" (gera falso "tem petição" em relatos que citam
    # "petição inicial" justamente para dizer que não a possuem).
    # Somente indícios de posse/juntada (evita "sem eu ter petição inicial" ser lido como positivo).
    termos_peticao = [
        "tenho a petição inicial",
        "tenho a peticao inicial",
        "tenho petição inicial",
        "tenho peticao inicial",
        "documento da ação em mãos",
        "documento da acao em maos",
        "documento da ação",
        "documento da acao",
        "juntei petição",
        "juntei peticao",
        "petição juntada",
        "peticao juntada",
        "mandei a petição",
        "mandei a peticao",
        "recebi a petição inicial",
        "recebi a peticao inicial",
    ]
    termos_banco_horas_sem_assinatura = ["banco de horas sem assinatura", "banco de horas sem assinar", "banco de horas não assinado", "banco de horas nao assinado"]
    termos_salario_picado = ["salário picado", "salario picado", "pagamento picado", "pago picado", "salario pago picado"]
    termos_recorrencia = ["vários meses", "varios meses", "recorrente", "todo mês", "todo mes", "sempre"]
    termos_pagamento_por_fora = ["paguei por fora", "pagamento por fora", "por fora varios meses", "por fora vários meses"]
    termos_jornada_sem_folga = ["domingo sem folga", "trabalhava domingo sem folga", "sem folga semanal"]
    # Indícios fortes (comportamental). "assedio" isolado fica subordinado a checagem de dúvida/hedge.
    termos_assedio_forte = [
        "humilhava",
        "humilha",
        "constrangimento",
        "gerente humilhava",
    ]
    termos_hedge_assedio = [
        "talvez",
        "será que",
        "sera que",
        "só estresse",
        "so estresse",
        "só stress",
        "so stress",
        "nao sei",
        "não sei",
    ]

    tempo_meses = int(case_data.get("tempo_empresa_meses") or 0)
    if tempo_meses <= 0 and texto:
        match = re.search(r"(\d+)\s*(mes|meses)", texto)
        if match:
            try:
                tempo_meses = int(match.group(1))
            except ValueError:
                tempo_meses = 0

    if not texto:
        return {}

    he_base = any(t in texto for t in termos_horas_extras)
    he_habito = (
        "todo dia" in texto
        or "habitual" in texto
        or "recorrente" in texto
        or "dois anos" in texto
        or "vários meses" in texto
        or "varios meses" in texto
        or "sempre" in texto
    )
    he_controle = (
        "sem ponto" in texto
        or "sem controle de ponto" in texto
        or "sem controle" in texto
        or "sem pagamento" in texto
        or "nao pagas" in texto
        or "não pagas" in texto
    )
    he_composto = ("hora extra" in texto or "horas extras" in texto) and he_habito and he_controle

    horas_extras_contexto_alto = (
        ("hora extra todo dia" in texto and "sem ponto" in texto)
        or ("horas extras todo dia" in texto and "sem ponto" in texto)
        or ("jornada excessiva" in texto and "sem ponto" in texto)
        or he_composto
    )
    return {
        "gestante_dispensada": any(t in texto for t in termos_gestante) and any(t in texto for t in termos_desligamento),
        "verbas_nao_pagas": any(t in texto for t in termos_verbas_nao_pagas),
        "justa_causa_sem_prova": "justa causa" in texto and any(t in texto for t in termos_sem_prova),
        "funcionario_sem_registro": any(t in texto for t in termos_sem_registro) and tempo_meses >= 3,
        "acidente_sem_cat": any(t in texto for t in termos_acidente) and any(t in texto for t in termos_sem_cat),
        "assedio_com_provas": any(t in texto for t in termos_assedio) and any(t in texto for t in termos_provas_assedio),
        "horas_extras_habituais": he_base or he_composto,
        "horas_extras_contexto_alto": horas_extras_contexto_alto,
        "pedido_demissao_quitado": any(t in texto for t in termos_pedido_demissao) and any(t in texto for t in termos_quitacao),
        "fgts_em_atraso": any(t in texto for t in termos_fgts_atraso) and ("6 meses" in texto or "7 meses" in texto or "8 meses" in texto or "9 meses" in texto or "1 ano" in texto or "12 meses" in texto),
        "pj_com_subordinacao": any(t in texto for t in termos_pj_subordinado) and any(t in texto for t in termos_subordinacao),
        "terceirizado_subordinado": any(t in texto for t in termos_terceirizado) and any(t in texto for t in termos_subordinacao),
        "ferias_vencidas_nao_pagas": any(t in texto for t in termos_ferias_vencidas),
        "rescisao_atrasada_10d": ("rescisao atrasou" in texto or "rescisão atrasou" in texto or "atraso rescisao" in texto or "atraso rescisão" in texto) and any(
            token in texto for token in ["11 dias", "12 dias", "13 dias", "14 dias", "15 dias", "20 dias", "30 dias"]
        ),
        "acao_judicial_sem_peticao": any(t in texto for t in termos_acao_judicial) and not any(t in texto for t in termos_peticao),
        "banco_horas_sem_assinatura": any(t in texto for t in termos_banco_horas_sem_assinatura),
        "salario_picado_recorrente": any(t in texto for t in termos_salario_picado) and (
            any(t in texto for t in termos_recorrencia) or "salario pago picado" in texto
        ),
        "pagamento_por_fora_recorrente": any(t in texto for t in termos_pagamento_por_fora),
        "jornada_sem_folga": any(t in texto for t in termos_jornada_sem_folga),
        "assedio_indicios": (
            any(t in texto for t in termos_assedio_forte)
            or (
                ("assedio" in texto or "assédio" in texto)
                and not any(t in texto for t in termos_hedge_assedio)
            )
        ),
    }


def hard_rules_from_texto(texto: str) -> dict:
    """Detecção de hard rules a partir de texto puro (motor e classificador reutilizam)."""
    return _detectar_hard_rule_juridica(
        {"texto": texto, "descricao": texto, "tempo_empresa_meses": 0}
    )


def calcular_score(case_data):
    motivos = []

    risco = case_data.get("risco", "BAIXO")
    impacto_valor = case_data.get("impacto", 0)
    tipo = case_data.get("tipo", "geral")

    # Compatibilidade com regra de negócio existente.
    if tipo in ["pedido_demissao", "rescisao_pedido"]:
        return {
            "score": 20,
            "probabilidade_condenacao": 10,
            "nivel": "BAIXO",
            "motivos": [
                {
                    "fator": "Pedido de demissão sem indícios de irregularidade",
                    "impacto": -30,
                }
            ],
            "score_juridico": 20,
            "score_financeiro": 10,
            "score_incerteza": 0,
            "breakdown": {
                "juridico": 20,
                "financeiro": 10,
                "incerteza": 0,
            },
        }

    risco_base = normalizar_risco(risco)
    impacto_norm = normalizar_impacto(impacto_valor)
    peso_tipo = _peso_tipo_juridico(tipo)

    # 1) Eixo jurídico (0-75) calibrado para refletir gravidade legal.
    score_juridico = int(round((risco_base * 0.70 + peso_tipo * 0.30) * 75))
    motivos.append(
        {
            "fator": "Risco jurídico base",
            "impacto": score_juridico,
        }
    )

    # 2) Eixo financeiro (0-15)
    score_financeiro = int(round(impacto_norm * 15))
    motivos.append(
        {
            "fator": "Exposição financeira estimada",
            "impacto": score_financeiro,
        }
    )

    # 3) Qualidade de evidência/contexto (+/- 20)
    ajuste_evidencia = 0
    if case_data.get("reincidente"):
        ajuste_evidencia += 8
        motivos.append({"fator": "Reincidência", "impacto": 6})

    if case_data.get("tem_prova"):
        ajuste_evidencia += 5
        motivos.append({"fator": "Prova identificada", "impacto": 4})

    if case_data.get("testemunha"):
        ajuste_evidencia += 4
        motivos.append({"fator": "Testemunha potencial", "impacto": 4})

    # 4) Componente de incerteza (penalidade)
    score_incerteza = 0
    if str(risco).upper() == "INCONCLUSIVO":
        score_incerteza -= 10
        motivos.append(
            {
                "fator": "Dados insuficientes para conclusão segura",
                "impacto": -12,
            }
        )

    # Penalidade leve quando não há reforço de prova.
    if not case_data.get("tem_prova") and not case_data.get("testemunha"):
        score_incerteza -= 3
        motivos.append(
            {
                "fator": "Baixa robustez de evidências",
                "impacto": -4,
            }
        )

    score_total = score_juridico + score_financeiro + ajuste_evidencia + score_incerteza
    score_total = max(0, min(int(score_total), 100))
    if score_total < 20:
        score_total = 20

    # Calibração: ALTO deve refletir criticidade jurídica sem piso excessivo.
    risco_up = str(risco).upper()
    if risco_up == "ALTO" and score_total < 75:
        score_total = 75
    if risco_up in {"MÉDIO", "MEDIO"} and score_total < 42:
        score_total = 42
    if risco_up == "INCONCLUSIVO" and score_total > 45:
        score_total = 45

    nivel = _nivel_por_score(score_total)
    prob = _probabilidade_por_score(score_total)

    hard_rule = _detectar_hard_rule_juridica(case_data)
    if hard_rule:
        if hard_rule.get("pedido_demissao_quitado"):
            score_total = min(score_total, 35)
            prob = min(prob, 35)
            nivel = "BAIXO"
            motivos.append({"fator": "Hard rule 10E: pedido de demissão com quitação total (bloqueio crítico)", "impacto": -20})
        elif hard_rule.get("gestante_dispensada"):
            score_total = max(score_total, 85)
            prob = max(prob, 85)
            nivel = "ALTO"
            motivos.append({"fator": "Hard rule 10C: gestante dispensada", "impacto": 85})
        elif hard_rule.get("verbas_nao_pagas"):
            score_total = max(score_total, 82)
            prob = max(prob, _probabilidade_por_score(82))
            nivel = "ALTO"
            motivos.append({"fator": "Hard rule 10C: verbas rescisórias não pagas", "impacto": 82})
        elif hard_rule.get("justa_causa_sem_prova"):
            score_total = max(score_total, 80)
            prob = max(prob, _probabilidade_por_score(80))
            nivel = "ALTO"
            motivos.append({"fator": "Hard rule 10C: justa causa sem prova", "impacto": 80})
        elif hard_rule.get("funcionario_sem_registro"):
            score_total = max(score_total, 78)
            prob = max(prob, _probabilidade_por_score(78))
            nivel = "ALTO"
            motivos.append({"fator": "Hard rule 10C: funcionário sem registro por 3+ meses", "impacto": 78})
        elif hard_rule.get("acidente_sem_cat"):
            score_total = max(score_total, 84)
            prob = max(prob, _probabilidade_por_score(84))
            nivel = "ALTO"
            motivos.append({"fator": "Hard rule 10C: acidente de trabalho sem CAT", "impacto": 84})
        elif hard_rule.get("assedio_com_provas"):
            score_total = max(score_total, 83)
            prob = max(prob, _probabilidade_por_score(83))
            nivel = "ALTO"
            motivos.append({"fator": "Hard rule 10C: assédio com provas robustas", "impacto": 83})
        elif hard_rule.get("horas_extras_habituais"):
            score_total = max(score_total, 72)
            prob = max(prob, _probabilidade_por_score(72))
            nivel = "ALTO" if hard_rule.get("horas_extras_contexto_alto") else "MÉDIO"
            motivos.append({"fator": "Hard rule 10C: horas extras habituais sem controle", "impacto": 72})
        elif hard_rule.get("pj_com_subordinacao"):
            score_total = max(score_total, 80)
            prob = max(prob, _probabilidade_por_score(80))
            nivel = "ALTO"
            motivos.append({"fator": "Hard rule 10E: PJ com subordinação/ponto", "impacto": 80})
        elif hard_rule.get("terceirizado_subordinado"):
            score_total = max(score_total, 80)
            prob = max(prob, _probabilidade_por_score(80))
            nivel = "ALTO"
            motivos.append({"fator": "Hard rule 10E: terceirizado subordinado", "impacto": 80})
        elif hard_rule.get("fgts_em_atraso"):
            score_total = max(score_total, 60)
            prob = max(prob, _probabilidade_por_score(60))
            nivel = "MÉDIO"
            motivos.append({"fator": "Hard rule 10E: FGTS em atraso > 6 meses", "impacto": 60})
        elif hard_rule.get("ferias_vencidas_nao_pagas"):
            score_total = max(score_total, 58)
            prob = max(prob, _probabilidade_por_score(58))
            nivel = "MÉDIO"
            motivos.append({"fator": "Hard rule 10E: férias vencidas não pagas", "impacto": 58})
        elif hard_rule.get("rescisao_atrasada_10d"):
            score_total = max(score_total, 57)
            prob = max(prob, _probabilidade_por_score(57))
            nivel = "MÉDIO"
            motivos.append({"fator": "Hard rule 10E: rescisão atrasada > 10 dias", "impacto": 57})
        elif hard_rule.get("acao_judicial_sem_peticao"):
            score_total = max(score_total, 56)
            prob = max(prob, _probabilidade_por_score(56))
            nivel = "MÉDIO"
            motivos.append({"fator": "Hard rule 10E: ação judicial sem petição", "impacto": 56})
        elif hard_rule.get("banco_horas_sem_assinatura"):
            score_total = max(score_total, 58)
            prob = max(prob, _probabilidade_por_score(58))
            nivel = "MÉDIO"
            motivos.append({"fator": "Hard rule 10E: banco de horas sem assinatura", "impacto": 58})
        elif hard_rule.get("salario_picado_recorrente"):
            score_total = max(score_total, 57)
            prob = max(prob, _probabilidade_por_score(57))
            nivel = "MÉDIO"
            motivos.append({"fator": "Hard rule 10E: salário picado recorrente", "impacto": 57})
        elif hard_rule.get("pagamento_por_fora_recorrente"):
            score_total = max(score_total, 58)
            prob = max(prob, _probabilidade_por_score(58))
            nivel = "MÉDIO"
            motivos.append({"fator": "Hard rule 10F: pagamento por fora recorrente", "impacto": 58})
        elif hard_rule.get("jornada_sem_folga"):
            score_total = max(score_total, 55)
            prob = max(prob, _probabilidade_por_score(55))
            nivel = "MÉDIO"
            motivos.append({"fator": "Hard rule 10F: jornada sem folga", "impacto": 55})
        elif hard_rule.get("assedio_indicios"):
            score_total = max(score_total, 55)
            prob = max(prob, _probabilidade_por_score(55))
            nivel = "MÉDIO"
            motivos.append({"fator": "Hard rule 10F: assédio com indícios consistentes", "impacto": 55})

    return {
        "score": score_total,
        "probabilidade_condenacao": prob,
        "nivel": nivel,
        "motivos": motivos,
        # Campos extras para auditoria (compatíveis, não quebram app atual).
        "score_juridico": score_juridico,
        "score_financeiro": score_financeiro,
        "score_incerteza": score_incerteza,
        "breakdown": {
            "juridico": score_juridico,
            "financeiro": score_financeiro,
            "incerteza": score_incerteza,
        },
    }
