from motor_rescisao_profissional import analisar_rescisao_profissional
import re
from motor_afastamento import (
    classificar_beneficio,
    calcular_responsabilidade_pagamento,
    verificar_estabilidade_acidentaria,
    verificar_demissao_durante_afastamento,
    verificar_prazo_cat
)


def _normalizar_texto(dados):
    if isinstance(dados, dict):
        # Usa apenas valores para evitar falso positivo por nomes de chaves (ex.: "gestante": False).
        valores = [str(v) for v in dados.values() if v not in [None, "", [], {}]]
        return " ".join(valores).lower()
    return str(dados).lower()


def _detectar_lacunas_criticas(dados):
    lacunas = []
    texto = _normalizar_texto(dados)

    if len(texto.split()) < 10:
        lacunas.append("relato_curto")
    if not any(p in texto for p in ["quando", "data", "semana", "mês", "mes", "dia"]):
        lacunas.append("sem_referencia_temporal")
    if not any(p in texto for p in ["gestor", "empresa", "colaborador", "funcionário", "funcionario"]):
        lacunas.append("sem_envolvidos_claros")

    return lacunas


def _detectar_hard_rule_juridica(texto):
    # Estado 100% local por execução para evitar qualquer vazamento entre casos.
    texto = str(texto or "").lower()
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
    termos_horas_extras = ["hora extra todo dia", "horas extras", "jornada excessiva", "sem ponto"]
    termos_pedido_demissao = ["pedido de demissão", "pedido de demissao", "pediu a conta", "pediu demissao"]
    termos_quitacao = ["paguei tudo", "recibos", "documentos", "quitação total", "quitacao total"]
    termos_fgts_atraso = ["sem fgts", "fgts atrasado", "fgts em atraso", "fgts não recolhido", "fgts nao recolhido"]
    termos_pj_subordinado = ["contrato pj", "pj", "pessoa jurídica", "pessoa juridica"]
    termos_subordinacao = ["batia ponto", "subordinação", "subordinacao", "chefe direto", "ordens diretas"]
    termos_terceirizado = ["terceirizado", "terceirizada"]
    termos_ferias_vencidas = ["férias vencidas", "ferias vencidas", "férias não pagas", "ferias nao pagas"]
    termos_acao_judicial = ["ação judicial", "acao judicial", "entrou na justiça", "entrou na justica", "processo trabalhista"]
    termos_peticao = ["petição inicial", "peticao inicial", "inicial", "documento da ação", "documento da acao"]
    termos_banco_horas_sem_assinatura = ["banco de horas sem assinatura", "banco de horas sem assinar", "banco de horas não assinado", "banco de horas nao assinado"]
    termos_salario_picado = ["salário picado", "salario picado", "pagamento picado", "pago picado", "salario pago picado"]
    termos_recorrencia = ["vários meses", "varios meses", "recorrente", "todo mês", "todo mes", "sempre"]
    termos_pagamento_por_fora = ["paguei por fora", "pagamento por fora", "por fora varios meses", "por fora vários meses"]
    termos_jornada_sem_folga = ["domingo sem folga", "trabalhava domingo sem folga", "sem folga semanal"]
    termos_assedio_indicios = ["humilhava", "humilha", "constrangimento", "assédio", "assedio", "gerente humilhava"]

    gestante_dispensada = any(t in texto for t in termos_gestante) and any(t in texto for t in termos_desligamento)
    verbas_nao_pagas = any(t in texto for t in termos_verbas_nao_pagas)
    justa_causa_sem_prova = "justa causa" in texto and any(t in texto for t in termos_sem_prova)
    acidente_sem_cat = any(t in texto for t in termos_acidente) and any(t in texto for t in termos_sem_cat)
    assedio_com_provas = any(t in texto for t in termos_assedio) and any(t in texto for t in termos_provas_assedio)
    horas_extras_habituais = any(t in texto for t in termos_horas_extras)
    horas_extras_contexto_alto = ("hora extra todo dia" in texto and "sem ponto" in texto) or ("jornada excessiva" in texto and "sem ponto" in texto)
    pedido_demissao_quitado = any(t in texto for t in termos_pedido_demissao) and any(t in texto for t in termos_quitacao)
    fgts_em_atraso = any(t in texto for t in termos_fgts_atraso) and ("6 meses" in texto or "7 meses" in texto or "8 meses" in texto or "9 meses" in texto or "1 ano" in texto or "12 meses" in texto)
    pj_com_subordinacao = any(t in texto for t in termos_pj_subordinado) and any(t in texto for t in termos_subordinacao)
    terceirizado_subordinado = any(t in texto for t in termos_terceirizado) and any(t in texto for t in termos_subordinacao)
    ferias_vencidas_nao_pagas = any(t in texto for t in termos_ferias_vencidas)
    rescisao_atrasada_10d = ("rescisao atrasou" in texto or "rescisão atrasou" in texto or "atraso rescisao" in texto or "atraso rescisão" in texto) and any(
        token in texto for token in ["11 dias", "12 dias", "13 dias", "14 dias", "15 dias", "20 dias", "30 dias"]
    )
    acao_judicial_sem_peticao = any(t in texto for t in termos_acao_judicial) and not any(t in texto for t in termos_peticao)
    banco_horas_sem_assinatura = any(t in texto for t in termos_banco_horas_sem_assinatura)
    salario_picado_recorrente = any(t in texto for t in termos_salario_picado) and (
        any(t in texto for t in termos_recorrencia) or "salario pago picado" in texto
    )
    pagamento_por_fora_recorrente = any(t in texto for t in termos_pagamento_por_fora)
    jornada_sem_folga = any(t in texto for t in termos_jornada_sem_folga)
    assedio_indicios = any(t in texto for t in termos_assedio_indicios)

    return {
        "gestante_dispensada": gestante_dispensada,
        "verbas_nao_pagas": verbas_nao_pagas,
        "justa_causa_sem_prova": justa_causa_sem_prova,
        "acidente_sem_cat": acidente_sem_cat,
        "assedio_com_provas": assedio_com_provas,
        "horas_extras_habituais": horas_extras_habituais,
        "horas_extras_contexto_alto": horas_extras_contexto_alto,
        "pedido_demissao_quitado": pedido_demissao_quitado,
        "fgts_em_atraso": fgts_em_atraso,
        "pj_com_subordinacao": pj_com_subordinacao,
        "terceirizado_subordinado": terceirizado_subordinado,
        "ferias_vencidas_nao_pagas": ferias_vencidas_nao_pagas,
        "rescisao_atrasada_10d": rescisao_atrasada_10d,
        "acao_judicial_sem_peticao": acao_judicial_sem_peticao,
        "banco_horas_sem_assinatura": banco_horas_sem_assinatura,
        "salario_picado_recorrente": salario_picado_recorrente,
        "pagamento_por_fora_recorrente": pagamento_por_fora_recorrente,
        "jornada_sem_folga": jornada_sem_folga,
        "assedio_indicios": assedio_indicios,
    }


def _extrair_tempo_meses(texto):
    match = re.search(r"(\d+)\s*(mes|meses)", texto or "")
    if not match:
        return 0
    try:
        return int(match.group(1))
    except ValueError:
        return 0


def _aplicar_hard_rule_resultado(resultado, texto, lacunas, dados):
    if not isinstance(resultado, dict):
        return resultado

    hard_rule = _detectar_hard_rule_juridica(texto)
    alertas = resultado.get("alertas") if isinstance(resultado.get("alertas"), list) else []
    tempo_meses = int(dados.get("tempo_empresa_meses") or 0)
    if tempo_meses <= 0:
        tempo_meses = _extrair_tempo_meses(texto)

    if hard_rule["pedido_demissao_quitado"]:
        resultado["risco"] = "BAIXO"
        resultado["pontuacao"] = min(int(resultado.get("pontuacao", 0) or 0), 35)
        resultado["racional_decisao"] = "Hard rule 10E: pedido de demissão com quitação total bloqueia regras críticas e limita risco a BAIXO."
        alertas.append({"tipo": "HARD RULE • PEDIDO DEMISSÃO QUITADO", "nivel": "BAIXO", "mensagem": "Quitação integral documentada reduz previsibilidade condenatória.", "lacunas": lacunas})
    elif hard_rule["gestante_dispensada"]:
        resultado["risco"] = "ALTO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 85)
        resultado["racional_decisao"] = "Hard rule 10C: gestante dispensada impõe risco ALTO com score mínimo 85."
        alertas.append({"tipo": "HARD RULE • GESTANTE DISPENSADA", "nivel": "ALTO", "mensagem": "Alta previsibilidade condenatória: estabilidade gestante.", "lacunas": lacunas})
    elif hard_rule["verbas_nao_pagas"]:
        resultado["risco"] = "ALTO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 82)
        resultado["racional_decisao"] = "Hard rule 10C: verbas rescisórias não pagas impõem risco ALTO com score mínimo 82."
        alertas.append({"tipo": "HARD RULE • VERBAS NÃO PAGAS", "nivel": "ALTO", "mensagem": "Não quitação rescisória com alto risco de condenação.", "lacunas": lacunas})
    elif hard_rule["justa_causa_sem_prova"]:
        resultado["risco"] = "ALTO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 80)
        resultado["racional_decisao"] = "Hard rule 10C: justa causa sem prova robusta impõe risco ALTO com score mínimo 80."
        alertas.append({"tipo": "HARD RULE • JUSTA CAUSA SEM PROVA", "nivel": "ALTO", "mensagem": "Sem prova/documento/testemunha para sustentar justa causa.", "lacunas": lacunas})
    elif any(t in texto for t in ["sem carteira", "sem registro", "trabalhou sem registrar"]) and tempo_meses >= 3:
        resultado["risco"] = "ALTO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 78)
        resultado["racional_decisao"] = "Hard rule 10C: vínculo sem registro por 3+ meses impõe risco ALTO com score mínimo 78."
        alertas.append({"tipo": "HARD RULE • SEM REGISTRO", "nivel": "ALTO", "mensagem": "Trabalho sem registro por período relevante.", "lacunas": lacunas})
    elif hard_rule["acidente_sem_cat"]:
        resultado["risco"] = "ALTO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 84)
        resultado["racional_decisao"] = "Hard rule 10C: acidente de trabalho sem CAT impõe risco ALTO com score mínimo 84."
        alertas.append({"tipo": "HARD RULE • ACIDENTE SEM CAT", "nivel": "ALTO", "mensagem": "Ausência de CAT em acidente de trabalho.", "lacunas": lacunas})
    elif hard_rule["assedio_com_provas"]:
        resultado["risco"] = "ALTO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 83)
        resultado["racional_decisao"] = "Hard rule 10C: assédio com provas (prints/áudio/testemunha) impõe risco ALTO com score mínimo 83."
        alertas.append({"tipo": "HARD RULE • ASSÉDIO COM PROVAS", "nivel": "ALTO", "mensagem": "Conjunto probatório robusto para assédio.", "lacunas": lacunas})
    elif hard_rule["horas_extras_habituais"]:
        risco_hora = "ALTO" if hard_rule["horas_extras_contexto_alto"] else "MÉDIO"
        resultado["risco"] = risco_hora
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 72)
        resultado["racional_decisao"] = "Hard rule 10C: horas extras habituais sem controle elevam o risco para MÉDIO/ALTO com score mínimo 72."
        alertas.append({"tipo": "HARD RULE • HORAS EXTRAS HABITUAIS", "nivel": risco_hora, "mensagem": "Jornada excessiva sem controle formal de ponto.", "lacunas": lacunas})
    elif hard_rule["pj_com_subordinacao"]:
        resultado["risco"] = "ALTO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 80)
        resultado["racional_decisao"] = "Hard rule 10E: PJ com subordinação/ponto impõe risco ALTO."
        alertas.append({"tipo": "HARD RULE • PJ SUBORDINADO", "nivel": "ALTO", "mensagem": "Indicativos de vínculo empregatício em contrato PJ.", "lacunas": lacunas})
    elif hard_rule["terceirizado_subordinado"]:
        resultado["risco"] = "ALTO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 80)
        resultado["racional_decisao"] = "Hard rule 10E: terceirizado com subordinação direta impõe risco ALTO."
        alertas.append({"tipo": "HARD RULE • TERCEIRIZADO SUBORDINADO", "nivel": "ALTO", "mensagem": "Subordinação direta eleva risco de vínculo/solidariedade.", "lacunas": lacunas})
    elif hard_rule["fgts_em_atraso"]:
        resultado["risco"] = "MÉDIO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 60)
        resultado["racional_decisao"] = "Hard rule 10E: FGTS em atraso superior a 6 meses impõe risco MÉDIO."
        alertas.append({"tipo": "HARD RULE • FGTS EM ATRASO", "nivel": "MÉDIO", "mensagem": "Atraso prolongado de FGTS com passivo relevante.", "lacunas": lacunas})
    elif hard_rule["ferias_vencidas_nao_pagas"]:
        resultado["risco"] = "MÉDIO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 58)
        resultado["racional_decisao"] = "Hard rule 10E: férias vencidas não pagas impõem risco MÉDIO."
        alertas.append({"tipo": "HARD RULE • FÉRIAS VENCIDAS", "nivel": "MÉDIO", "mensagem": "Inadimplemento de férias vencidas gera passivo previsível.", "lacunas": lacunas})
    elif hard_rule["rescisao_atrasada_10d"]:
        resultado["risco"] = "MÉDIO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 57)
        resultado["racional_decisao"] = "Hard rule 10E: rescisão atrasada acima de 10 dias impõe risco MÉDIO."
        alertas.append({"tipo": "HARD RULE • RESCISÃO ATRASADA", "nivel": "MÉDIO", "mensagem": "Atraso rescisório relevante em dias.", "lacunas": lacunas})
    elif hard_rule["acao_judicial_sem_peticao"]:
        resultado["risco"] = "MÉDIO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 56)
        resultado["racional_decisao"] = "Hard rule 10E: ação judicial sem petição inicial disponível impõe risco MÉDIO."
        alertas.append({"tipo": "HARD RULE • AÇÃO SEM PETIÇÃO", "nivel": "MÉDIO", "mensagem": "Sem petição inicial, risco deve ser tratado com prudência média.", "lacunas": lacunas})
    elif hard_rule["banco_horas_sem_assinatura"]:
        resultado["risco"] = "MÉDIO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 58)
        resultado["racional_decisao"] = "Hard rule 10E: banco de horas sem assinatura impõe risco MÉDIO."
        alertas.append({"tipo": "HARD RULE • BANCO HORAS SEM ASSINATURA", "nivel": "MÉDIO", "mensagem": "Controle de jornada sem formalização válida.", "lacunas": lacunas})
    elif hard_rule["salario_picado_recorrente"]:
        resultado["risco"] = "MÉDIO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 57)
        resultado["racional_decisao"] = "Hard rule 10E: salário picado recorrente impõe risco MÉDIO."
        alertas.append({"tipo": "HARD RULE • SALÁRIO PICADO RECORRENTE", "nivel": "MÉDIO", "mensagem": "Fracionamento recorrente de salário com risco trabalhista.", "lacunas": lacunas})
    elif hard_rule["pagamento_por_fora_recorrente"]:
        resultado["risco"] = "MÉDIO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 58)
        resultado["racional_decisao"] = "Hard rule 10F: pagamento por fora recorrente impõe risco MÉDIO."
        alertas.append({"tipo": "HARD RULE • PAGAMENTO POR FORA", "nivel": "MÉDIO", "mensagem": "Pagamentos por fora recorrentes elevam passivo trabalhista.", "lacunas": lacunas})
    elif hard_rule["jornada_sem_folga"]:
        resultado["risco"] = "MÉDIO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 55)
        resultado["racional_decisao"] = "Hard rule 10F: jornada sem folga regular impõe risco MÉDIO."
        alertas.append({"tipo": "HARD RULE • JORNADA SEM FOLGA", "nivel": "MÉDIO", "mensagem": "Indícios de jornada irregular sem descanso semanal.", "lacunas": lacunas})
    elif hard_rule["assedio_indicios"]:
        resultado["risco"] = "MÉDIO"
        resultado["pontuacao"] = max(int(resultado.get("pontuacao", 0) or 0), 55)
        resultado["racional_decisao"] = "Hard rule 10F: indícios consistentes de assédio impõem risco MÉDIO."
        alertas.append({"tipo": "HARD RULE • ASSÉDIO INDÍCIOS", "nivel": "MÉDIO", "mensagem": "Relato com sinais de humilhação/assédio no ambiente de trabalho.", "lacunas": lacunas})

    resultado["alertas"] = alertas
    return resultado


def _coletar_evidencias_assedio(texto):
    fortes = [
        "humilha",
        "assédio",
        "assedio",
        "constrangimento",
        "dano moral",
        "xing",
        "ofensiv",
        "mensagens",
    ]
    moderadas = ["gritou", "ofensa", "exposição", "exposicao", "ridicular", "recorrent", "semanas"]
    e_fortes = [p for p in fortes if p in texto]
    e_moderadas = [p for p in moderadas if p in texto]
    return e_fortes, e_moderadas


def _coletar_evidencias_acidente(texto):
    fortes = ["acidente", "queda", "lesão", "lesao", "cid m54", "m54", "ocupacional"]
    moderadas = ["afastado", "atestado", "cat", "machucou", "ergonom"]
    e_fortes = [p for p in fortes if p in texto]
    e_moderadas = [p for p in moderadas if p in texto]
    return e_fortes, e_moderadas


def _coletar_mitigadores(texto):
    mitigadores = [
        "sem testemunh",
        "sem mensagens",
        "sem prova",
        "não comprov",
        "nao comprov",
        "isolad",
        "leve",
        "pontual",
    ]
    return [m for m in mitigadores if m in texto]


def _matriz_assedio(tipo_risco, texto, lacunas):
    e_fortes, e_moderadas = _coletar_evidencias_assedio(texto)
    mitigadores = _coletar_mitigadores(texto)

    if tipo_risco == "assedio_moral" and (len(e_fortes) >= 2 or (e_fortes and e_moderadas)) and not mitigadores:
        return {
            "risco": "ALTO",
            "pontuacao": 85,
            "racional": "Assédio com evidências robustas e contexto consistente.",
            "evidencias": e_fortes + e_moderadas,
        }

    if tipo_risco == "assedio_moral" and (e_fortes or e_moderadas):
        if len(lacunas) >= 2:
            return {
                "risco": "INCONCLUSIVO",
                "pontuacao": 35,
                "racional": "Há indícios de assédio, porém faltam dados críticos para conclusão segura.",
                "evidencias": e_fortes + e_moderadas,
            }
        return {
            "risco": "MÉDIO",
            "pontuacao": 55,
            "racional": "Indícios de assédio presentes, sem robustez suficiente para ALTO.",
            "evidencias": e_fortes + e_moderadas + mitigadores,
        }

    return None


def _matriz_acidente(tipo_risco, texto, lacunas):
    e_fortes, e_moderadas = _coletar_evidencias_acidente(texto)
    mitigadores = _coletar_mitigadores(texto)

    if tipo_risco == "acidente_trabalho" and "cat" in texto and "leve" in texto:
        return {
            "risco": "MÉDIO",
            "pontuacao": 52,
            "racional": "Acidente leve com CAT regular sugere risco moderado e controlável.",
            "evidencias": e_fortes + e_moderadas + ["cat_emitida", "acidente_leve"],
        }

    if tipo_risco == "acidente_trabalho" and len(e_fortes) >= 2 and "leve" not in texto and not mitigadores:
        return {
            "risco": "ALTO",
            "pontuacao": 85,
            "racional": "Acidente com sinais fortes de responsabilidade trabalhista.",
            "evidencias": e_fortes + e_moderadas,
        }

    if tipo_risco == "acidente_trabalho" and (e_fortes or e_moderadas):
        if len(lacunas) >= 2:
            return {
                "risco": "INCONCLUSIVO",
                "pontuacao": 35,
                "racional": "Indícios de acidente sem contexto mínimo para classificar risco alto.",
                "evidencias": e_fortes + e_moderadas,
            }
        return {
            "risco": "MÉDIO",
            "pontuacao": 55,
            "racional": "Existe risco de acidente, com necessidade de validação adicional.",
            "evidencias": e_fortes + e_moderadas + mitigadores,
        }

    return None


def _fallback_contextual(texto, lacunas):
    indicadores_medio = [
        "discussão", "discussao", "conflito",
        "advertência", "advertencia",
        "clima ruim", "problema com gestor",
    ]
    # Evita classificar como médio quando o texto negar explicitamente conflito.
    if "sem conflito" in texto:
        pass
    elif any(t in texto for t in indicadores_medio):
        return "MÉDIO", 45, "Conflito contextual detectado sem gravidade crítica."

    if any(t in texto for t in ["hora extra", "horas extras", "banco de horas", "reincid", "recorr", "acumula", "similares"]):
        return "MÉDIO", 50, "Sinais de risco trabalhista recorrente ou de jornada exigem atenção."

    if any(t in texto for t in ["prazo", "duvida", "dúvida", "confirmar"]):
        return "BAIXO", 20, "Consulta preventiva com baixa materialidade de risco no relato atual."

    if len(lacunas) >= 2:
        return "INCONCLUSIVO", 30, "Dados insuficientes para classificação jurídica segura."

    return "BAIXO", 15, "Sem sinais críticos consistentes no relato atual."


def analisar_caso(tipo_caso, dados):
    texto = _normalizar_texto(dados)
    tipo_risco = str(dados.get("tipo_risco", "")).lower()
    lacunas = _detectar_lacunas_criticas(dados)

    if tipo_risco == "inconclusivo":
        return _aplicar_hard_rule_resultado({
            "tipo": "Dúvida trabalhista",
            "risco": "INCONCLUSIVO",
            "pontuacao": 30,
            "alertas": [
                {
                    "tipo": "INFORMAÇÃO INSUFICIENTE",
                    "nivel": "INCONCLUSIVO",
                    "mensagem": "Dados críticos ausentes para classificação jurídica segura.",
                    "lacunas": lacunas,
                }
            ],
            "racional_decisao": "Classificação inconclusiva por falta de dados essenciais.",
        }, texto, lacunas, dados)

    matriz_assedio = _matriz_assedio(tipo_risco, texto, lacunas)
    if matriz_assedio:
        return _aplicar_hard_rule_resultado({
            "tipo": "Assédio moral",
            "risco": matriz_assedio["risco"],
            "pontuacao": matriz_assedio["pontuacao"],
            "alertas": [{
                "tipo": "ASSÉDIO",
                "nivel": matriz_assedio["risco"],
                "mensagem": matriz_assedio["racional"],
                "evidencias": matriz_assedio["evidencias"],
                "lacunas": lacunas,
            }],
            "racional_decisao": matriz_assedio["racional"],
        }, texto, lacunas, dados)

    matriz_acidente = _matriz_acidente(tipo_risco, texto, lacunas)
    if matriz_acidente:
        return _aplicar_hard_rule_resultado({
            "tipo": "Acidente de trabalho",
            "risco": matriz_acidente["risco"],
            "pontuacao": matriz_acidente["pontuacao"],
            "alertas": [{
                "tipo": "ACIDENTE",
                "nivel": matriz_acidente["risco"],
                "mensagem": matriz_acidente["racional"],
                "evidencias": matriz_acidente["evidencias"],
                "lacunas": lacunas,
            }],
            "racional_decisao": matriz_acidente["racional"],
        }, texto, lacunas, dados)

    if tipo_risco == "conflito_interpessoal":
        return _aplicar_hard_rule_resultado({
            "tipo": "Conflito interpessoal",
            "risco": "MÉDIO",
            "pontuacao": 45,
            "alertas": [{
                "tipo": "CONFLITO",
                "nivel": "MÉDIO",
                "mensagem": "Situação pode evoluir para risco trabalhista",
                "lacunas": lacunas,
            }],
            "racional_decisao": "Conflito identificado sem elementos de gravidade extrema.",
        }, texto, lacunas, dados)

    if tipo_caso == "rescisao":
        texto_rescisao = texto
        gestante_flag = dados.get("gestante", False) or any(t in texto_rescisao for t in ["gestante", "grávida", "gravida", "gestação", "gestacao"])
        cipa_flag = dados.get("cipa", False) or any(t in texto_rescisao for t in ["cipa", "cipeiro"])
        dirigente_flag = dados.get("dirigente_sindical", False) or "dirigente sindical" in texto_rescisao
        retorno_inss_flag = (
            dados.get("retorno_inss", False)
            or "retorno do inss" in texto_rescisao
            or "voltou do inss" in texto_rescisao
            or "retornou do inss" in texto_rescisao
        )
        beneficio_b91_flag = dados.get("acidente_trabalho", False) or "b91" in texto_rescisao

        prova_documental = any(t in texto_rescisao for t in ["document", "registro", "assinatura", "e-mail", "email"])
        if any(t in texto_rescisao for t in ["sem dossie", "sem dossiê", "sem documentação", "sem document", "ausência de prova", "ausencia de prova"]):
            prova_documental = False
        falta_grave = any(t in texto_rescisao for t in ["falta grave", "482", "justa causa"])
        advertencias = 1 if any(t in texto_rescisao for t in ["advert", "suspens"]) else 0
        suspensoes = 1 if "suspens" in texto_rescisao else 0
        prazo_irregular = any(t in texto_rescisao for t in ["fora do prazo", "atraso", "pagamento atrasado"])

        tipo_rescisao = dados.get("tipo_rescisao") or "demissao_sem_justa_causa"
        if "sem justa causa" in texto_rescisao:
            tipo_rescisao = "demissao_sem_justa_causa"
        elif "justa causa" in texto_rescisao:
            tipo_rescisao = "Justa Causa"

        dados_basicos = {
            "tipo_rescisao": tipo_rescisao,
            "gestante": gestante_flag,
            "cipa": cipa_flag,
            "dirigente_sindical": dirigente_flag,
            "estabilidade_cct": False,
            "advertencias": advertencias,
            "suspensoes": suspensoes,
            "prova_documental": prova_documental,
            "falta_grave": falta_grave,
            "beneficio_b91": beneficio_b91_flag,
            "afastamento_recente": retorno_inss_flag,
            "cid_sensivel": False,
            "aviso_previo_aplicado": True,
            "documentacao_ok": prova_documental,
            "prazo_pagamento_irregular": prazo_irregular,
        }

        analise = analisar_rescisao_profissional(dados_basicos)

        retorno = {
            "tipo": "Rescisão",
            "risco": analise["risco_final"],
            "pontuacao": analise["pontuacao_total"],
            "alertas": analise["alertas"],
            "tipo_rescisao": dados_basicos["tipo_rescisao"],
            "tempo_empresa_meses": dados.get("tempo_empresa_meses"),
            "racional_decisao": "Risco de rescisão calculado por matriz jurídica profissional.",
        }
        # Regra calibrada: justa causa sem prova documental tende a risco alto de reversão.
        if dados_basicos["tipo_rescisao"] == "Justa Causa" and not dados_basicos["prova_documental"]:
            retorno["risco"] = "ALTO"
            retorno["pontuacao"] = max(retorno.get("pontuacao", 0), 82)
            retorno["alertas"].append(
                {
                    "tipo": "JUSTA CAUSA SEM PROVA",
                    "nivel": "ALTO",
                    "mensagem": "Dispensa por justa causa sem robustez documental apresenta alto risco de reversão.",
                    "lacunas": lacunas,
                }
            )
            retorno["racional_decisao"] = "Justa causa sem prova robusta: risco alto de reversão judicial."
        return _aplicar_hard_rule_resultado(retorno, texto, lacunas, dados)

    elif tipo_caso in ["afastamento", "acidente_trabalho", "atestado"]:
        dias = dados.get("dias_afastamento") or 15

        pagamento = calcular_responsabilidade_pagamento(dias)
        tipo_beneficio = classificar_beneficio("a_servico")

        alertas = []

        alerta_estabilidade = verificar_estabilidade_acidentaria(
            tipo_beneficio, None, None
        )
        if alerta_estabilidade:
            alertas.append(alerta_estabilidade)

        alerta_demissao = verificar_demissao_durante_afastamento(
            dias, None
        )
        if alerta_demissao:
            alertas.append(alerta_demissao)

        alerta_cat = verificar_prazo_cat(
            None, None, "a_servico"
        )
        if alerta_cat:
            alertas.append(alerta_cat)

        if any(t in texto for t in ["m54", "doença ocupacional", "doenca ocupacional", "ergonom"]):
            alertas.append(
                {
                    "nivel": "ALTO",
                    "motivo": "Indicativos de possível doença ocupacional com exposição jurídica relevante.",
                    "base_legal": "Art. 20 Lei 8.213/91",
                    "recomendacao": "Avaliar nexo causal e medidas preventivas imediatas.",
                }
            )
        elif "cat" in texto and "leve" in texto:
            alertas.append(
                {
                    "nivel": "MÉDIO",
                    "motivo": "Acidente leve com CAT regular ainda requer monitoramento jurídico preventivo.",
                    "base_legal": "Art. 22 Lei 8.213/91",
                    "recomendacao": "Manter documentação e acompanhamento ocupacional.",
                }
            )

        risco = "BAIXO"

        for alerta in alertas:
            if alerta["nivel"] == "ALTO":
                risco = "ALTO"
                break
            elif alerta["nivel"] == "MÉDIO":
                risco = "MÉDIO"

        pontuacao = {
            "ALTO": 85,
            "MÉDIO": 50,
            "BAIXO": 10
        }[risco]

        return _aplicar_hard_rule_resultado({
            "tipo": "Afastamento",
            "dias_afastamento": dias,
            "empresa_paga": pagamento["empresa_paga"],
            "inss_paga": pagamento["inss_paga"],
            "beneficio": tipo_beneficio,
            "risco": risco,
            "pontuacao": pontuacao,
            "alertas": alertas,
            "racional_decisao": "Risco definido por eventos de estabilidade, demissão e conformidade CAT.",
        }, texto, lacunas, dados)

    risco_detectado, pontuacao, racional = _fallback_contextual(texto, lacunas)

    return _aplicar_hard_rule_resultado({
        "tipo": "Dúvida trabalhista",
        "risco": risco_detectado,
        "pontuacao": pontuacao,
        "alertas": [
            {
                "tipo": "ANÁLISE CONTEXTUAL",
                "nivel": risco_detectado,
                "mensagem": racional,
                "lacunas": lacunas,
            }
        ],
        "racional_decisao": racional,
    }, texto, lacunas, dados)