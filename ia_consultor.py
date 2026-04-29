from ia_client import client
from ia_validator import validar_parecer
import json
import os


def _to_text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _is_litigio_trabalhista(contexto, dados):
    corpus = " ".join(
        [
            _to_text(contexto).lower(),
            _to_text(dados.get("tipo_caso")).lower(),
            _to_text(dados.get("tipo_rescisao")).lower(),
            _to_text(dados.get("texto_caso")).lower(),
            _to_text(dados.get("pedido")).lower(),
            _to_text(dados.get("valor_pedido")).lower(),
            _to_text(dados.get("valor_causa")).lower(),
        ]
    )
    sinais = [
        "processo",
        "advogado",
        "acao judicial",
        "ação judicial",
        "reclamatória",
        "reclamatoria",
        "audiência",
        "audiencia",
        "acordo",
        "pedido em dinheiro",
        "valor da causa",
        "indenização",
        "indenizacao",
        "condenação",
        "condenacao",
    ]
    return any(s in corpus for s in sinais)


def _parse_float(value):
    try:
        if value is None:
            return None
        text = str(value).strip().lower()
        if not text:
            return None
        text = text.replace("r$", "").replace(" ", "")
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", ".")
        return float(text)
    except Exception:
        return None


def _checklist_evidencias_litigio(contexto, dados):
    corpus = " ".join(
        [
            _to_text(contexto).lower(),
            _to_text(dados).lower(),
        ]
    )
    mapa = {
        "peticao_inicial": ["petição inicial", "peticao inicial", "inicial"],
        "calculos": ["cálculo", "calculo", "memória de cálculo", "memoria de calculo", "planilha"],
        "documentos": ["documento", "documentação", "documentacao", "contrato", "email", "e-mail"],
        "ponto": ["cartão de ponto", "cartao de ponto", "espelho de ponto", "ponto eletrônico", "ponto eletronico"],
        "recibos": ["recibo", "holerite", "comprovante de pagamento"],
        "testemunhas": ["testemunha", "testemunhas", "depoimento"],
    }
    checklist = {}
    for item, termos in mapa.items():
        checklist[item] = any(t in corpus for t in termos)
    return checklist


def _inferir_confianca_litigio(lacunas, checklist):
    presentes = sum(1 for ok in checklist.values() if ok)
    faltantes = len(checklist) - presentes
    if len(lacunas) >= 2 or faltantes >= 4:
        return "baixo"
    if len(lacunas) == 1 or faltantes >= 2:
        return "medio"
    return "alto"


def _faixa_sem_base():
    return "Dados insuficientes para estimar acordo com segurança."


def _estimar_faixa_financeira_litigio(dados, checklist, baixa_confianca=False):
    pedido = _parse_float(dados.get("valor_pedido"))
    if pedido is None:
        pedido = _parse_float(dados.get("valor_causa"))

    acordo = _parse_float(dados.get("valor_acordo"))
    if acordo is None:
        acordo = _parse_float(dados.get("acordo"))

    salario = _parse_float(dados.get("salario"))
    if salario is None:
        salario = _parse_float(dados.get("salario_base"))
    meses = _parse_float(dados.get("tempo_empresa_meses"))

    if acordo and acordo > 0:
        return {
            "min": round(acordo * 0.85, 2),
            "max": round(acordo * 1.15, 2),
            "mensagem": "Faixa preliminar baseada em referência de acordo informado.",
        }

    if pedido and pedido > 0:
        tem_base_forte = checklist.get("peticao_inicial") and checklist.get("calculos")
        if tem_base_forte and not baixa_confianca:
            faixa_min = pedido * 0.45
            faixa_max = pedido * 0.90
        else:
            faixa_min = pedido * 0.30
            faixa_max = pedido * 0.70
        return {
            "min": round(faixa_min, 2),
            "max": round(faixa_max, 2),
            "mensagem": "Faixa preliminar baseada no valor pedido, sujeita a memória de cálculos.",
        }

    if salario and salario > 0:
        meses_ref = meses if meses and meses > 0 else 6
        base = salario * max(3, min(meses_ref, 12))
        return {
            "min": round(base * 0.60, 2),
            "max": round(base * 1.20, 2),
            "mensagem": "Faixa inicial estimada por salário e tempo, dependente de cálculos detalhados.",
        }

    return {
        "min": 8000.00,
        "max": 25000.00,
        "mensagem": "Faixa inicial conservadora sem base completa, dependente de cálculos e documentos.",
    }


def _proporcionalidade_litigio(dados):
    salario = _parse_float(dados.get("salario"))
    if salario is None:
        salario = _parse_float(dados.get("salario_base"))
    meses = _parse_float(dados.get("tempo_empresa_meses"))
    pedido = _parse_float(dados.get("valor_pedido"))
    if pedido is None:
        pedido = _parse_float(dados.get("valor_causa"))

    if salario is None or meses is None or pedido is None or salario <= 0 or meses <= 0:
        return {
            "status": "insuficiente",
            "mensagem": "Sem base mínima para cheque de proporcionalidade (salário, tempo e pedido).",
            "ratio_pedido_folha": None,
        }

    massa_salarial = salario * meses
    ratio = pedido / max(1.0, massa_salarial)
    if ratio >= 2.5:
        status = "alto"
    elif ratio >= 1.0:
        status = "moderado"
    else:
        status = "baixo"
    return {
        "status": status,
        "mensagem": (
            f"Pedido total representa {ratio:.2f}x a massa salarial estimada do período "
            f"(salário x tempo de empresa)."
        ),
        "ratio_pedido_folha": ratio,
    }


def _strategy_band(checklist, confianca, proporcao_status):
    docs_base = checklist.get("documentos") or checklist.get("peticao_inicial")
    prova_robusta = docs_base and checklist.get("calculos") and (checklist.get("ponto") or checklist.get("recibos"))
    if confianca == "baixo":
        return "negociar após documentos"
    if prova_robusta and proporcao_status in {"alto", "moderado"}:
        return "negociar cedo"
    if prova_robusta and checklist.get("testemunhas"):
        return "defender até audiência"
    if docs_base:
        return "contestar"
    return "negociar após documentos"


def _score_to_confianca_label(score):
    if score >= 0.75:
        return "alta"
    if score >= 0.45:
        return "media"
    return "baixa"


def _sinais_robustez_juridica(contexto, dados):
    corpus = " ".join(
        [
            _to_text(contexto).lower(),
            _to_text(dados).lower(),
        ]
    )

    return {
        "estabilidade_gestante": any(
            t in corpus for t in ["gestante", "grávida", "gravida", "gestacao", "gestação"]
        ) and any(t in corpus for t in ["demit", "dispensa", "rescis"]),
        "acidente_com_prova_documental": any(
            t in corpus for t in ["acidente", "cat", "atestado", "laudo", "cid", "afastamento"]
        ) and any(t in corpus for t in ["document", "laudo", "atestado", "cat"]),
        "verbas_rescisorias_nao_pagas": any(
            t in corpus for t in ["verbas rescis", "rescisórias", "rescisorias", "nao pag", "não pag", "atraso"]
        ),
        "vinculo_sem_registro_robusto": (
            any(t in corpus for t in ["sem registro", "sem carteira", "ctps", "vínculo", "vinculo"])
            and any(t in corpus for t in ["mensagens", "testemunh", "comprovante", "pix", "transfer"])
        ),
        "horas_extras_documentadas": (
            any(t in corpus for t in ["hora extra", "horas extras", "jornada", "banco de horas"])
            and any(t in corpus for t in ["cartao de ponto", "cartão de ponto", "espelho", "registro", "planilha"])
        ),
    }


def _classificar_forca_juridica(sinais):
    hits = [k for k, ok in sinais.items() if ok]
    if hits:
        return "forte", hits
    return "normal", []


def _motivo_confianca(label, dados_ratio, prova_ratio, clareza_score, consistencia_score):
    motivos = []
    if dados_ratio < 0.5:
        motivos.append("dados incompletos")
    elif dados_ratio >= 0.75:
        motivos.append("dados suficientes")

    if prova_ratio < 0.4:
        motivos.append("faltam documentos")
    elif prova_ratio >= 0.7:
        motivos.append("prova robusta")

    if clareza_score >= 0.65:
        motivos.append("contexto claro")
    else:
        motivos.append("contexto pouco claro")

    if consistencia_score >= 0.7:
        motivos.append("risco coerente")
    elif consistencia_score < 0.5:
        motivos.append("risco ainda instável")

    base = ", ".join(motivos) if motivos else "base técnica limitada"
    if label == "alta":
        return f"Confianca alta: {base}."
    if label == "media":
        return f"Confianca media: {base}."
    return f"Confianca baixa: {base}."


def _avaliar_confiabilidade_blocos(contexto, dados, resultado, parecer, lacunas):
    checklist = _checklist_evidencias_litigio(contexto, dados)
    itens_prova = len(checklist) or 1
    prova_ratio = sum(1 for v in checklist.values() if v) / itens_prova
    sinais_robustez = _sinais_robustez_juridica(contexto, dados)
    forca_juridica, hits_robustos = _classificar_forca_juridica(sinais_robustez)

    campos_relevantes = [
        "tipo_caso",
        "tipo_rescisao",
        "tempo_empresa_meses",
        "dias_afastamento",
        "valor_pedido",
        "valor_causa",
        "salario",
        "salario_base",
    ]
    dados_presentes = sum(1 for c in campos_relevantes if dados.get(c) not in [None, "", []])
    dados_ratio = dados_presentes / len(campos_relevantes)

    texto_ctx = _to_text(contexto).strip()
    racional = _to_text(resultado.get("racional_decisao")).strip()
    clareza_score = 0.3
    if len(texto_ctx) >= 120:
        clareza_score += 0.35
    if racional:
        clareza_score += 0.35
    clareza_score = min(1.0, clareza_score)

    risco = str(resultado.get("risco", "")).upper()
    pontuacao = _parse_float(resultado.get("pontuacao"))
    consistencia = 0.55
    if risco in {"BAIXO", "MÉDIO", "MEDIO", "ALTO", "INCONCLUSIVO"}:
        consistencia += 0.2
    if pontuacao is not None and 0 <= pontuacao <= 100:
        consistencia += 0.15
    if len(lacunas) >= 2:
        consistencia -= 0.2
    consistencia = max(0.0, min(1.0, consistencia))

    # Diferencia ausência de anexo complementar de fragilidade jurídica material.
    score_decisao = (dados_ratio * 0.30) + (prova_ratio * 0.20) + (clareza_score * 0.15) + (consistencia * 0.35)
    score_assistente = (dados_ratio * 0.20) + (prova_ratio * 0.35) + (clareza_score * 0.20) + (consistencia * 0.25)
    score_acao = (dados_ratio * 0.35) + (prova_ratio * 0.10) + (clareza_score * 0.25) + (consistencia * 0.30)

    if forca_juridica == "forte":
        score_decisao = min(1.0, score_decisao + 0.25)
        score_assistente = min(1.0, score_assistente + 0.20)
        score_acao = min(1.0, score_acao + 0.20)

    label_decisao = _score_to_confianca_label(score_decisao)
    label_assistente = _score_to_confianca_label(score_assistente)
    label_acao = _score_to_confianca_label(score_acao)

    # BAIXA apenas quando o caso for realmente ambíguo.
    caso_ambiguo = (
        forca_juridica != "forte"
        and consistencia < 0.45
        and dados_ratio < 0.40
        and prova_ratio < 0.35
    )

    # Regra automática para casos clássicos de alta previsibilidade jurídica.
    # Se faltar detalhe relevante, reduz para MEDIA, nunca BAIXA.
    if forca_juridica == "forte":
        detalhe_relevante_faltante = len(lacunas) >= 2 or clareza_score < 0.50
        if detalhe_relevante_faltante:
            label_decisao = "media"
            label_assistente = "media"
            label_acao = "media"
        else:
            label_decisao = "alta"
            label_assistente = "alta"
            label_acao = "alta"
    elif not caso_ambiguo:
        # Fora de caso clássico, sem ambiguidade real: piso em MEDIA.
        if label_decisao == "baixa":
            label_decisao = "media"
        if label_assistente == "baixa":
            label_assistente = "media"
        if label_acao == "baixa":
            label_acao = "media"

    motivo_decisao = _motivo_confianca(label_decisao, dados_ratio, prova_ratio, clareza_score, consistencia)
    motivo_assistente = _motivo_confianca(label_assistente, dados_ratio, prova_ratio, clareza_score, consistencia)
    motivo_acao = _motivo_confianca(label_acao, dados_ratio, prova_ratio, clareza_score, consistencia)
    if hits_robustos:
        descricao = ", ".join(h.replace("_", " ") for h in hits_robustos)
        complemento = (
            f"Robustez juridica material identificada ({descricao}); "
            "ausencia de documento complementar nao reduz automaticamente a previsibilidade."
        )
        motivo_decisao = f"{motivo_decisao} {complemento}"
        motivo_assistente = f"{motivo_assistente} {complemento}"
        motivo_acao = f"{motivo_acao} {complemento}"
    elif caso_ambiguo:
        complemento = (
            "Cenario com baixa consistencia juridica e base probatoria limitada, mantendo confianca baixa."
        )
        motivo_decisao = f"{motivo_decisao} {complemento}"
        motivo_assistente = f"{motivo_assistente} {complemento}"
        motivo_acao = f"{motivo_acao} {complemento}"

    return {
        "decisao_empresarial_confianca": label_decisao,
        "assistente_juridico_confianca": label_assistente,
        "proxima_acao_confianca": label_acao,
        "motivo_decisao_empresarial_confianca": motivo_decisao,
        "motivo_assistente_juridico_confianca": motivo_assistente,
        "motivo_proxima_acao_confianca": motivo_acao,
    }


def _normalizar_parecer_litigio(parecer, dados):
    # Mantém compatibilidade com o app atual e garante os 5 blocos do modo litígio.
    if not str(parecer.get("exposicao_juridica_provavel", "")).strip():
        parecer["exposicao_juridica_provavel"] = (
            "Exposição moderada/alta conforme fatos narrados e grau de prova disponível."
        )
    if not isinstance(parecer.get("pontos_dependentes_prova"), list):
        parecer["pontos_dependentes_prova"] = [
            "Nexo entre conduta e dano alegado.",
            "Documentos e testemunhos sobre os fatos centrais.",
        ]
    if not str(parecer.get("fragilidade_pedido_contrario", "")).strip():
        parecer["fragilidade_pedido_contrario"] = (
            "Pedido contrário enfraquece sem prova robusta de dano, habitualidade ou nexo."
        )
    if not str(parecer.get("faixa_provavel_acordo", "")).strip():
        parecer["faixa_provavel_acordo"] = "Faixa estimada depende do pedido e da força da prova."
    if not str(parecer.get("estrategia_recomendada", "")).strip():
        parecer["estrategia_recomendada"] = (
            "Priorizar defesa por fatos comprováveis, reduzir temas frágeis e negociar com teto definido."
        )

    if "diagnostico" not in parecer or not str(parecer.get("diagnostico", "")).strip():
        parecer["diagnostico"] = parecer["exposicao_juridica_provavel"]
    if "tese_risco" not in parecer or not str(parecer.get("tese_risco", "")).strip():
        parecer["tese_risco"] = parecer["exposicao_juridica_provavel"]
    if "tese_defesa" not in parecer or not str(parecer.get("tese_defesa", "")).strip():
        parecer["tese_defesa"] = parecer["fragilidade_pedido_contrario"]
    if "recomendacao" not in parecer or not str(parecer.get("recomendacao", "")).strip():
        parecer["recomendacao"] = parecer["estrategia_recomendada"]

    lacunas = _detectar_lacunas_dados(dados)
    if "pedido_complemento" not in parecer or not str(parecer.get("pedido_complemento", "")).strip():
        parecer["pedido_complemento"] = (
            "Informe valor do pedido, provas documentais e lista de testemunhas para calibrar risco e acordo."
            if lacunas
            else ""
        )
    return parecer


def _aplicar_prudencia_litigio(parecer, dados, lacunas, contexto):
    checklist = _checklist_evidencias_litigio(contexto, dados)
    confianca = _inferir_confianca_litigio(lacunas, checklist)
    proporcao = _proporcionalidade_litigio(dados)
    band = _strategy_band(checklist, confianca, proporcao["status"])

    parecer["checklist_evidencias"] = checklist
    parecer["proporcionalidade_pedido"] = proporcao["mensagem"]
    parecer["estrategia_faixa"] = band
    parecer["confianca_conclusao"] = confianca
    parecer["strategy_band"] = band

    if band == "contestar":
        parecer["estrategia_recomendada"] = (
            "Contestar de forma técnica os pedidos sem suporte robusto e exigir prova de cada fato alegado."
        )
    elif band == "negociar cedo":
        parecer["estrategia_recomendada"] = (
            "Negociar cedo com teto definido para reduzir risco processual e custo de litígio."
        )
    elif band == "negociar após documentos":
        parecer["estrategia_recomendada"] = (
            "Segurar proposta até fechar documentos e cálculos mínimos; negociar só após base técnica."
        )
    elif band == "defender até audiência":
        parecer["estrategia_recomendada"] = (
            "Sustentar defesa até audiência, com preparo de prova oral e documental."
        )

    # Confidence gating: sem certeza forte com baixa confiança ou dados insuficientes.
    baixa_confianca = confianca == "baixo" or proporcao["status"] == "insuficiente"
    faixa_fin = _estimar_faixa_financeira_litigio(dados, checklist, baixa_confianca=baixa_confianca)
    parecer["impacto_financeiro_provavel_min"] = faixa_fin["min"]
    parecer["impacto_financeiro_provavel_max"] = faixa_fin["max"]
    parecer["impacto_financeiro"] = round((faixa_fin["min"] + faixa_fin["max"]) / 2, 2)

    if baixa_confianca:
        parecer["exposicao_juridica_provavel"] = (
            "Exposição ainda indeterminada: cenário depende de prova documental, cálculos e delimitação dos pedidos."
        )
        parecer["fragilidade_pedido_contrario"] = (
            "Não é possível afirmar fragilidade relevante sem analisar petição inicial, cálculos e provas mínimas."
        )
        parecer["faixa_provavel_acordo"] = _faixa_sem_base()
        parecer["faixa_provavel_acordo"] += " Use a faixa inicial enquanto os cálculos não forem concluídos."
        parecer["recomendacao"] = (
            "Conclusão prudente: coletar base probatória mínima antes de posição forte sobre mérito ou valor."
        )
        parecer["pedido_complemento"] = (
            "Enviar petição inicial, cálculos detalhados, documentos, controles de ponto, recibos e testemunhas."
        )
    else:
        faixa = str(parecer.get("faixa_provavel_acordo", "")).strip()
        # Nunca inventar faixa numérica sem base mínima de cálculo/documentação.
        base_minima = checklist.get("peticao_inicial") and checklist.get("calculos") and checklist.get("documentos")
        if not base_minima:
            parecer["faixa_provavel_acordo"] = _faixa_sem_base()
            parecer["pedido_complemento"] = (
                "Para estimar acordo: anexar petição inicial, memória de cálculos e documentos centrais."
            )
        elif not faixa:
            parecer["faixa_provavel_acordo"] = (
                "Faixa preliminar possível, condicionada à validação de cálculos e documentos apresentados."
            )
    parecer["observacao_faixa_financeira"] = faixa_fin["mensagem"]
    return parecer


def _detectar_lacunas_dados(dados):
    campos_criticos = [
        "tipo_caso",
        "tipo_rescisao",
        "tempo_empresa_meses",
        "dias_afastamento",
    ]
    lacunas = []
    for campo in campos_criticos:
        if dados.get(campo) in [None, "", []]:
            lacunas.append(campo)
    return lacunas


def _enriquecer_parecer_compat(parecer, dados):
    parecer["parecer_schema_version"] = "2.0-auditoria-ui"

    if "tese_risco" not in parecer or not str(parecer.get("tese_risco", "")).strip():
        parecer["tese_risco"] = "Há potencial de risco jurídico conforme fatos relatados."

    if "tese_defesa" not in parecer or not str(parecer.get("tese_defesa", "")).strip():
        parecer["tese_defesa"] = "A defesa depende de documentação, histórico e medidas preventivas comprováveis."

    if "plano_acao_24h" not in parecer or not isinstance(parecer.get("plano_acao_24h"), list):
        parecer["plano_acao_24h"] = [
            "Consolidar documentos e cronologia do caso.",
            "Validar registros internos com RH e liderança direta.",
        ]

    if "plano_acao_7d" not in parecer or not isinstance(parecer.get("plano_acao_7d"), list):
        parecer["plano_acao_7d"] = [
            "Executar plano de mitigação jurídica para o caso.",
            "Revisar aderência de procedimentos trabalhistas aplicáveis.",
        ]

    if "plano_acao_30d" not in parecer or not isinstance(parecer.get("plano_acao_30d"), list):
        parecer["plano_acao_30d"] = [
            "Implementar prevenção estruturante para reduzir reincidência.",
            "Acompanhar indicadores de risco e conformidade da área.",
        ]

    if "confianca_conclusao" not in parecer:
        parecer["confianca_conclusao"] = "media"

    if "pedido_complemento" not in parecer:
        lacunas = _detectar_lacunas_dados(dados)
        parecer["pedido_complemento"] = (
            "Para maior precisão, complemente: " + ", ".join(lacunas)
            if lacunas
            else ""
        )

    return parecer


def _normalizar_blocos_executivos(parecer, confiabilidades=None):
    # ETAPA 1: estrutura fixa em 3 blocos sem quebrar campos legados.
    decisao = parecer.get("decisao_empresarial")
    if not isinstance(decisao, dict):
        decisao = {}

    if not str(decisao.get("risco_real", "")).strip():
        decisao["risco_real"] = str(parecer.get("risco", "INCONCLUSIVO")).upper()

    impacto = decisao.get("impacto_financeiro_provavel")
    if not str(impacto if impacto is not None else "").strip():
        impacto_min = parecer.get("impacto_financeiro_provavel_min")
        impacto_max = parecer.get("impacto_financeiro_provavel_max")
        if impacto_min not in [None, ""] and impacto_max not in [None, ""]:
            decisao["impacto_financeiro_provavel"] = (
                f"R$ {float(impacto_min):,.2f} a R$ {float(impacto_max):,.2f}"
            )
        else:
            impacto_legacy = parecer.get("impacto_financeiro")
            if impacto_legacy not in [None, ""]:
                decisao["impacto_financeiro_provavel"] = str(impacto_legacy)
            else:
                decisao["impacto_financeiro_provavel"] = "Depende de prova e memória de cálculo."

    if not str(decisao.get("decisao_recomendada", "")).strip():
        decisao["decisao_recomendada"] = (
            str(parecer.get("recomendacao", "")).strip()
            or "Conduzir decisão com base em prova documental e risco processual."
        )

    assistente = parecer.get("assistente_juridico")
    if not isinstance(assistente, dict):
        assistente = {}

    if not str(assistente.get("base_legal_pratica", "")).strip():
        assistente["base_legal_pratica"] = (
            str(parecer.get("fundamentacao", "")).strip()
            or "Aplicar CLT e jurisprudência consolidada ao fato efetivamente comprovado."
        )

    pontos_prova = assistente.get("pontos_de_prova")
    if not isinstance(pontos_prova, list) or not pontos_prova:
        pontos = parecer.get("pontos_dependentes_prova")
        if isinstance(pontos, list) and pontos:
            assistente["pontos_de_prova"] = pontos
        else:
            assistente["pontos_de_prova"] = [
                "Nexo entre conduta e dano alegado.",
                "Habitualidade, autoria e materialidade dos fatos discutidos.",
            ]

    docs = assistente.get("documentos_necessarios")
    if not isinstance(docs, list) or not docs:
        docs_padrao = [
            "Documentos contratuais e registros internos do caso.",
            "Controles de jornada, recibos e comunicações relevantes.",
        ]
        checklist = parecer.get("checklist_evidencias")
        if isinstance(checklist, dict):
            faltantes = []
            if not checklist.get("peticao_inicial"):
                faltantes.append("Petição inicial")
            if not checklist.get("calculos"):
                faltantes.append("Memória de cálculos")
            if not checklist.get("documentos"):
                faltantes.append("Documentos centrais")
            if not checklist.get("ponto"):
                faltantes.append("Controles de ponto")
            if not checklist.get("recibos"):
                faltantes.append("Recibos/comprovantes")
            if not checklist.get("testemunhas"):
                faltantes.append("Rol de testemunhas")
            assistente["documentos_necessarios"] = faltantes or docs_padrao
        else:
            assistente["documentos_necessarios"] = docs_padrao

    proxima = parecer.get("proxima_acao")
    if not isinstance(proxima, dict):
        proxima = {}

    if not str(proxima.get("hoje", "")).strip():
        proxima["hoje"] = (
            "Fechar cronologia factual e separar provas críticas antes de qualquer posição final."
        )
    if not str(proxima.get("dias_7", "")).strip():
        proxima["dias_7"] = (
            "Concluir análise técnica das provas e definir linha principal de defesa/negociação."
        )
    if not str(proxima.get("dias_30", "")).strip():
        proxima["dias_30"] = (
            "Executar plano jurídico definitivo e revisar política interna para reduzir recorrência."
        )

    parecer["decisao_empresarial"] = decisao
    parecer["assistente_juridico"] = assistente
    parecer["proxima_acao"] = proxima

    confiabilidades = confiabilidades or {}
    parecer["decisao_empresarial_confianca"] = (
        confiabilidades.get("decisao_empresarial_confianca")
        or str(parecer.get("decisao_empresarial_confianca", "")).strip()
        or "media"
    )
    parecer["assistente_juridico_confianca"] = (
        confiabilidades.get("assistente_juridico_confianca")
        or str(parecer.get("assistente_juridico_confianca", "")).strip()
        or "media"
    )
    parecer["proxima_acao_confianca"] = (
        confiabilidades.get("proxima_acao_confianca")
        or str(parecer.get("proxima_acao_confianca", "")).strip()
        or "media"
    )
    parecer["motivo_decisao_empresarial_confianca"] = (
        confiabilidades.get("motivo_decisao_empresarial_confianca")
        or str(parecer.get("motivo_decisao_empresarial_confianca", "")).strip()
        or "Confianca media: base técnica parcialmente completa."
    )
    parecer["motivo_assistente_juridico_confianca"] = (
        confiabilidades.get("motivo_assistente_juridico_confianca")
        or str(parecer.get("motivo_assistente_juridico_confianca", "")).strip()
        or "Confianca media: provas e dados ainda podem melhorar."
    )
    parecer["motivo_proxima_acao_confianca"] = (
        confiabilidades.get("motivo_proxima_acao_confianca")
        or str(parecer.get("motivo_proxima_acao_confianca", "")).strip()
        or "Confianca media: plano viável com ajustes conforme novas evidências."
    )

    parecer["auditoria_interna"] = {
        "decisao_empresarial": {
            "confianca": parecer["decisao_empresarial_confianca"],
            "motivo": parecer["motivo_decisao_empresarial_confianca"],
        },
        "assistente_juridico": {
            "confianca": parecer["assistente_juridico_confianca"],
            "motivo": parecer["motivo_assistente_juridico_confianca"],
        },
        "proxima_acao": {
            "confianca": parecer["proxima_acao_confianca"],
            "motivo": parecer["motivo_proxima_acao_confianca"],
        },
    }
    return parecer


def _normalizar_veredito_estrategico(parecer):
    veredito = parecer.get("veredito_estrategico")
    if not isinstance(veredito, dict):
        veredito = {}

    strategy_band = str(parecer.get("strategy_band", "")).lower()
    risco = str(parecer.get("risco", "")).upper()
    confianca = str(parecer.get("confianca_conclusao", "medio")).lower()
    faixa_txt = str(
        parecer.get("faixa_provavel_acordo")
        or parecer.get("decisao_empresarial", {}).get("impacto_financeiro_provavel", "")
    ).strip()

    if not str(veredito.get("aceitar_acordo_agora", "")).strip():
        if "negociar cedo" in strategy_band:
            veredito["aceitar_acordo_agora"] = "sim"
        elif "defender até audiência" in strategy_band or risco == "BAIXO":
            veredito["aceitar_acordo_agora"] = "nao"
        else:
            veredito["aceitar_acordo_agora"] = "depende"

    if not str(veredito.get("contestar_inicialmente", "")).strip():
        veredito["contestar_inicialmente"] = (
            "sim" if strategy_band in {"contestar", "defender até audiência"} else "nao"
        )

    if not str(veredito.get("faixa_acordo_sugerida", "")).strip():
        veredito["faixa_acordo_sugerida"] = (
            faixa_txt or "Faixa inicial depende de cálculos e documentos essenciais."
        )

    if not str(veredito.get("urgencia", "")).strip():
        if risco == "ALTO":
            veredito["urgencia"] = "alta"
        elif risco in {"MÉDIO", "MEDIO"} or confianca == "baixo":
            veredito["urgencia"] = "media"
        else:
            veredito["urgencia"] = "baixa"

    if not str(veredito.get("principal_proximo_passo", "")).strip():
        veredito["principal_proximo_passo"] = (
            str(parecer.get("proxima_acao", {}).get("hoje", "")).strip()
            or "Fechar documentos críticos e definir tese principal de condução do caso."
        )

    if not str(veredito.get("resumo_executivo_1_linha", "")).strip():
        veredito["resumo_executivo_1_linha"] = (
            f"Risco {risco or 'N/A'}; acordo agora: {veredito['aceitar_acordo_agora']}; "
            f"urgência {veredito['urgencia']}."
        )

    parecer["veredito_estrategico"] = veredito
    return parecer


def _parecer_fast_from_fluxo(contexto, dados, resultado, score, probabilidade):
    fluxo = dados.get("fluxo_consulta") if isinstance(dados, dict) else {}
    if not isinstance(fluxo, dict):
        return None

    executivo = fluxo.get("parecer_executivo") if isinstance(fluxo.get("parecer_executivo"), dict) else {}
    perguntas = fluxo.get("perguntas_objetivas") or resultado.get("perguntas_objetivas") or []
    pedido = fluxo.get("pedido_complemento") or (
        "Para análise precisa, preciso confirmar: " + " ".join(f"{i + 1}. {q}" for i, q in enumerate(perguntas))
        if perguntas else ""
    )
    impacto_txt = fluxo.get("impacto_financeiro_texto") or "Impacto financeiro depende de salário, tempo de vínculo e verbas discutidas."
    risco = str(resultado.get("risco") or fluxo.get("risco") or "INCONCLUSIVO").upper()

    return {
        "parecer_schema_version": "2.0-auditoria-ui",
        "risco": risco,
        "diagnostico": executivo.get("diagnostico_inicial") or "Diagnóstico inicial baseado no relato informado.",
        "fundamentacao": executivo.get("risco_juridico") or resultado.get("racional_decisao") or "Risco depende da confirmação de fatos e provas.",
        "impactos": executivo.get("risco_juridico") or "Impactos variam conforme prova documental e histórico contratual.",
        "impacto_financeiro": 0,
        "impacto_financeiro_provavel_min": None,
        "impacto_financeiro_provavel_max": None,
        "observacao_faixa_financeira": impacto_txt,
        "recomendacao": executivo.get("estrategia_empresarial") or "Consolidar documentação para decisão empresarial segura.",
        "pedido_complemento": pedido,
        "decisao_empresarial": {
            "risco_real": risco,
            "impacto_financeiro_provavel": impacto_txt,
            "decisao_recomendada": executivo.get("estrategia_empresarial") or "Definir estratégia após fechamento dos dados críticos.",
        },
        "proxima_acao": {
            "hoje": executivo.get("proxima_acao_recomendada") or (perguntas[0] if perguntas else "Consolidar fatos e documentos."),
            "dias_7": "Concluir coleta de evidências e validar exposição real.",
            "dias_30": "Executar plano jurídico final com governança interna.",
        },
        "confianca_conclusao": "medio",
    }


def gerar_parecer_juridico(
    contexto,
    dados,
    resultado,
    score=None,
    probabilidade=None
):
    usar_fast = str(os.getenv("DP_IA_FAST_PARECER", "1")).strip().lower() not in {"0", "false", "no"}
    if usar_fast and isinstance(dados, dict) and dados.get("fluxo_consulta"):
        lacunas = _detectar_lacunas_dados(dados)
        parecer = _parecer_fast_from_fluxo(contexto, dados, resultado, score, probabilidade)
        if parecer:
            confiabilidades = _avaliar_confiabilidade_blocos(contexto, dados, resultado, parecer, lacunas)
            parecer = _normalizar_blocos_executivos(parecer, confiabilidades)
            parecer = _normalizar_veredito_estrategico(parecer)
            return _enriquecer_parecer_compat(parecer, dados)

    lacunas = _detectar_lacunas_dados(dados)
    lacunas_txt = ", ".join(lacunas) if lacunas else "nenhuma lacuna crítica identificada"
    modo_litigio = _is_litigio_trabalhista(contexto, dados)

    if modo_litigio:
        checklist = _checklist_evidencias_litigio(contexto, dados)
        checklist_txt = json.dumps(checklist, ensure_ascii=False)
        proporcao = _proporcionalidade_litigio(dados)
        prompt = f"""
Você é consultor jurídico trabalhista experiente em contencioso.
Responda de forma direta, sem juridiquês desnecessário e sem floreio.
Use raciocínio jurídico real sobre chance de êxito, prova, risco e acordo.

Indicadores internos (não exibir no texto final):
- Score interno: {score if score else "N/A"}/100
- Probabilidade estimada: {probabilidade if probabilidade else "N/A"}%

CONTEXTO:
{contexto}

DADOS:
- Tipo de caso: {dados.get("tipo_caso")}
- Tipo de rescisão: {dados.get("tipo_rescisao")}
- Tempo de empresa: {dados.get("tempo_empresa_meses")}
- Dias de afastamento: {dados.get("dias_afastamento")}
- Lacunas detectadas: {lacunas_txt}
- Checklist de evidências (true/false): {checklist_txt}
- Proporcionalidade salário+tempo+pedido: {proporcao["mensagem"]}

ANÁLISE DO NÚCLEO:
- Risco calculado: {resultado.get("risco")}
- Pontuação: {resultado.get("pontuacao")}
- Racional: {resultado.get("racional_decisao")}

INSTRUÇÕES OBRIGATÓRIAS:
1) Traga exatamente os 5 blocos abaixo.
2) Aponte o que depende de prova e o que é frágil no pedido contrário.
3) Se não houver base para estimar valor, explicite isso e peça complemento.
4) Não cite score interno, probabilidade interna nem regras do sistema.
5) Sem frases genéricas.
6) Se confiança estiver baixa ou faltarem evidências críticas, não dê conclusão forte.
7) Nunca invente faixa numérica de acordo sem base mínima: petição inicial + cálculos + documentos.
8) Escolha uma strategy_band: contestar | negociar cedo | negociar após documentos | defender até audiência.

SAÍDA JSON OBRIGATÓRIA:
{{
  "parecer_schema_version": "2.0-auditoria-ui",
  "decisao_empresarial": {{
    "risco_real": "Risco objetivo e direto",
    "impacto_financeiro_provavel": "Faixa provável ou condição de insuficiência de base",
    "decisao_recomendada": "Decisão empresarial prática"
  }},
  "assistente_juridico": {{
    "base_legal_pratica": "Base legal aplicada ao caso, sem juridiquês excessivo",
    "pontos_de_prova": ["Ponto 1", "Ponto 2"],
    "documentos_necessarios": ["Doc 1", "Doc 2"]
  }},
  "proxima_acao": {{
    "hoje": "Ação imediata",
    "dias_7": "Ação em 7 dias",
    "dias_30": "Ação em 30 dias"
  }},
  "decisao_empresarial_confianca": "alta|media|baixa",
  "assistente_juridico_confianca": "alta|media|baixa",
  "proxima_acao_confianca": "alta|media|baixa",
  "motivo_decisao_empresarial_confianca": "Motivo simples da confiança",
  "motivo_assistente_juridico_confianca": "Motivo simples da confiança",
  "motivo_proxima_acao_confianca": "Motivo simples da confiança",
  "auditoria_interna": {{
    "decisao_empresarial": {{"confianca": "alta|media|baixa", "motivo": "texto simples"}},
    "assistente_juridico": {{"confianca": "alta|media|baixa", "motivo": "texto simples"}},
    "proxima_acao": {{"confianca": "alta|media|baixa", "motivo": "texto simples"}}
  }},
  "veredito_estrategico": {{
    "aceitar_acordo_agora": "sim|nao|depende",
    "contestar_inicialmente": "sim|nao",
    "faixa_acordo_sugerida": "Faixa sugerida em linguagem direta",
    "urgencia": "baixa|media|alta",
    "principal_proximo_passo": "Próxima ação principal",
    "resumo_executivo_1_linha": "Resumo objetivo em uma linha"
  }},
  "risco": "BAIXO | MÉDIO | ALTO | INCONCLUSIVO",
  "exposicao_juridica_provavel": "Análise objetiva da exposição da empresa",
  "pontos_dependentes_prova": ["Ponto 1", "Ponto 2"],
  "fragilidade_pedido_contrario": "Onde o pedido contrário tende a enfraquecer",
  "faixa_provavel_acordo": "Faixa em R$ (mínimo - máximo) com premissas, ou 'dados insuficientes'",
  "estrategia_recomendada": "Estratégia prática de condução e negociação",
  "strategy_band": "contestar | negociar cedo | negociar após documentos | defender até audiência",
  "checklist_evidencias": {{
    "peticao_inicial": true,
    "calculos": false,
    "documentos": true,
    "ponto": false,
    "recibos": false,
    "testemunhas": false
  }},
  "proporcionalidade_pedido": "Comparação objetiva entre salário, tempo e pedido total",
  "fundamentacao": "Base legal objetiva e curta",
  "recomendacao": "Síntese executiva em 2-3 linhas",
  "confianca_conclusao": "alto|medio|baixo",
  "pedido_complemento": "Dados faltantes para refinar tese e faixa de acordo"
}}
"""
    else:
        prompt = f"""
Você é um consultor trabalhista premium para liderança de RH.
Seu parecer deve ser factual, objetivo e acionável.
Sem juridiquês excessivo. Sem respostas genéricas.

Indicadores internos (não exibir no texto final):
- Score interno: {score if score else "N/A"}/100
- Probabilidade estimada: {probabilidade if probabilidade else "N/A"}%

-----------------------------------
📌 CONTEXTO
-----------------------------------
{contexto}

-----------------------------------
📌 DADOS
-----------------------------------

Tipo de caso: {dados.get("tipo_caso")}
Tipo de rescisão: {dados.get("tipo_rescisao")}
Tempo de empresa: {dados.get("tempo_empresa_meses")}
Dias de afastamento: {dados.get("dias_afastamento")}
Lacunas detectadas: {lacunas_txt}

-----------------------------------
📌 ANÁLISE DO NÚCLEO
-----------------------------------

Risco calculado: {resultado.get("risco")}
Pontuação: {resultado.get("pontuacao")}
Racional: {resultado.get("racional_decisao")}

-----------------------------------
⚠️ DIRETRIZES CRÍTICAS
-----------------------------------

1) Cite fatos concretos do caso (não seja genérico).
2) Traga duas leituras: tese de risco e tese de defesa.
3) Monte plano de ação objetivo em 24h, 7d e 30d.
4) Informe nível de confiança da conclusão: alto|medio|baixo.
5) Se faltar informação crítica, peça complemento de forma direta.
6) Não mencionar score interno, percentual técnico ou lógica do sistema.

-----------------------------------
📦 SAÍDA JSON OBRIGATÓRIA
-----------------------------------

{{
  "parecer_schema_version": "2.0-auditoria-ui",
  "decisao_empresarial": {{
    "risco_real": "Risco objetivo e direto",
    "impacto_financeiro_provavel": "Impacto financeiro provável em linguagem prática",
    "decisao_recomendada": "Decisão empresarial prática"
  }},
  "assistente_juridico": {{
    "base_legal_pratica": "Base legal aplicada ao caso sem juridiquês excessivo",
    "pontos_de_prova": ["Ponto 1", "Ponto 2"],
    "documentos_necessarios": ["Doc 1", "Doc 2"]
  }},
  "proxima_acao": {{
    "hoje": "Ação imediata",
    "dias_7": "Ação em 7 dias",
    "dias_30": "Ação em 30 dias"
  }},
  "decisao_empresarial_confianca": "alta|media|baixa",
  "assistente_juridico_confianca": "alta|media|baixa",
  "proxima_acao_confianca": "alta|media|baixa",
  "motivo_decisao_empresarial_confianca": "Motivo simples da confiança",
  "motivo_assistente_juridico_confianca": "Motivo simples da confiança",
  "motivo_proxima_acao_confianca": "Motivo simples da confiança",
  "auditoria_interna": {{
    "decisao_empresarial": {{"confianca": "alta|media|baixa", "motivo": "texto simples"}},
    "assistente_juridico": {{"confianca": "alta|media|baixa", "motivo": "texto simples"}},
    "proxima_acao": {{"confianca": "alta|media|baixa", "motivo": "texto simples"}}
  }},
  "veredito_estrategico": {{
    "aceitar_acordo_agora": "sim|nao|depende",
    "contestar_inicialmente": "sim|nao",
    "faixa_acordo_sugerida": "Faixa sugerida em linguagem direta",
    "urgencia": "baixa|media|alta",
    "principal_proximo_passo": "Próxima ação principal",
    "resumo_executivo_1_linha": "Resumo objetivo em uma linha"
  }},
  "risco": "BAIXO | MÉDIO | ALTO",
  "diagnostico": "Diagnóstico factual com fatos específicos do caso",
  "tese_risco": "Leitura jurídica de risco para a empresa",
  "tese_defesa": "Leitura jurídica de defesa viável para a empresa",
  "fundamentacao": "Base legal objetiva (CLT, CF, jurisprudência aplicável)",
  "impactos": "Impactos trabalhistas prováveis e cenários",
  "impacto_financeiro": número,
  "recomendacao": "Síntese executiva de orientação",
  "plano_acao_24h": ["..."],
  "plano_acao_7d": ["..."],
  "plano_acao_30d": ["..."],
  "confianca_conclusao": "alto|medio|baixo",
  "pedido_complemento": "Pergunta objetiva pedindo dados faltantes, se necessário"
}}
"""

    try:

        resposta = client.responses.create(
            model="gpt-4.1",
            input=prompt,
            timeout=30
        )

        texto = resposta.output_text.strip()
        parecer = validar_parecer(texto)
        if modo_litigio:
            parecer = _normalizar_parecer_litigio(parecer, dados)
            parecer = _aplicar_prudencia_litigio(parecer, dados, lacunas, contexto)
        confiabilidades = _avaliar_confiabilidade_blocos(contexto, dados, resultado, parecer, lacunas)
        parecer = _normalizar_blocos_executivos(parecer, confiabilidades)
        parecer = _normalizar_veredito_estrategico(parecer)
        return _enriquecer_parecer_compat(parecer, dados)

    except Exception as e:
        print("ERRO IA:", e)
        parecer = validar_parecer("")
        confiabilidades = _avaliar_confiabilidade_blocos(contexto, dados, resultado, parecer, lacunas)
        parecer = _normalizar_blocos_executivos(parecer, confiabilidades)
        parecer = _normalizar_veredito_estrategico(parecer)
        return _enriquecer_parecer_compat(parecer, dados)