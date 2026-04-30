import json
import os
import time
import unicodedata
from functools import lru_cache
from typing import Any, Dict, List

from ia_client import client


_TERMOS_PROIBIDOS_RISCO_ZERO = [
    "sem risco",
    "não há risco",
    "nao ha risco",
    "risco zero",
    "totalmente seguro",
]


_MAPA_TEMAS = {
    "horas extras": ["hora", "extra", "jornada", "ponto"],
    "gestante": ["gravid", "gravida", "grávida", "gestante", "gravidez"],
    "acidente": ["acidente", "cat", "afastamento"],
    "pj": ["pj", "pejotizacao", "pejotização", "prestador"],
    "fgts": ["fgts"],
    "assédio": ["assedio", "assédio", "humilhacao", "humilhação"],
    "demissão": [
        "demitir",
        "demissao",
        "demissão",
        "rescisao",
        "rescisão",
        "dispensa",
        "mandei embora",
        "saiu",
        "desligamento",
        "termino contrato",
    ],
}

_TERMOS_ADERENCIA_DEMISSAO = [
    "verbas",
    "rescisorias",
    "rescisórias",
    "pagamento",
    "encerramento",
    "contrato",
    "direitos",
]

_TERMOS_JURIDICOS_GENERICOS = [
    "trabalhista",
    "juridic",
    "passivo",
    "reclamacao",
    "reclamação",
    "acordo",
    "document",
    "prova",
]


def _normalizar_texto(texto: str) -> str:
    t = str(texto or "").lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn"
    )


def _aplicar_trava_risco_final(texto_usuario: str, risco_atual: str) -> str:
    """
    Trava dura (hard override): só eleva para ALTO em gatilhos críticos.
    Nunca reduz o risco retornado pela IA.
    """
    t = _normalizar_texto(texto_usuario)
    r = str(risco_atual or "INCONCLUSIVO").upper().replace("MEDIO", "MÉDIO")
    if r not in {"BAIXO", "MÉDIO", "MÉDIO-ALTO", "ALTO", "INCONCLUSIVO"}:
        r = "INCONCLUSIVO"

    if any(x in t for x in ["processo", "processar", "advogado"]):
        return "ALTO"
    if any(x in t for x in ["gravida", "gestante", "gravidez"]):
        return "ALTO"
    if "pj" in t and ("todo dia" in t or "fixo" in t):
        return "ALTO"
    if any(x in t for x in ["por fora", "informal", "caixa"]):
        return "ALTO"
    if "justa causa" in t and ("posso" in t or "sem risco" in t):
        return "ALTO"
    if any(x in t for x in ["acidente", "machucou", "queda", "lesao"]):
        return "ALTO"
    return r


def _aplicar_risco_minimo_por_categoria(texto_usuario: str, risco_atual: str) -> str:
    """
    Camada estrutural única de piso de risco por categoria jurídica crítica.
    Nunca reduz risco: apenas eleva quando o texto indica cenário sensível.
    """
    t = _normalizar_texto(texto_usuario)
    risco = str(risco_atual or "INCONCLUSIVO").upper().replace("MEDIO", "MÉDIO")
    ordem = {"INCONCLUSIVO": 0, "BAIXO": 1, "MÉDIO": 2, "ALTO": 3}
    if risco not in ordem:
        risco = "INCONCLUSIVO"

    minimo = risco

    # 1) Assédio/humilhação/constrangimento: piso MÁXIMO conservador (preferência ALTO).
    if any(x in t for x in ["humilhou", "assedio", "constrangimento"]):
        minimo = "ALTO"

    # 2) Horas extras prolongadas/não registradas: piso MÉDIO.
    gatilho_horas = (
        "horas extras" in t
        or ("hora extra" in t and any(x in t for x in ["muito tempo", "sempre fazia"]))
        or ("nao registrei" in t and ("hora" in t or "extra" in t))
    )
    if gatilho_horas and ordem[minimo] < ordem["MÉDIO"]:
        minimo = "MÉDIO"

    # 3) Rescisão sem TRCT/pagamento incompleto: piso MÉDIO.
    gatilho_rescisao = any(
        x in t
        for x in ["nao fiz trct", "rescisao sem pagamento", "nao paguei tudo"]
    )
    if gatilho_rescisao and ordem[minimo] < ordem["MÉDIO"]:
        minimo = "MÉDIO"

    # 4) Gestante: ALTO sem exceção.
    if any(x in t for x in ["gravida", "gestante"]):
        minimo = "ALTO"

    return minimo if ordem[minimo] > ordem[risco] else risco


def _extrair_tema_principal(texto_usuario: str) -> str | None:
    t = _normalizar_texto(texto_usuario)
    for tema, termos in _MAPA_TEMAS.items():
        for termo in termos:
            if _normalizar_texto(termo) in t:
                return tema
    return None


def _validar_aderencia_resposta(tema: str | None, resposta_texto: str) -> bool:
    if not tema:
        return True
    termos = _MAPA_TEMAS.get(tema) or []
    if not termos:
        return True
    r = _normalizar_texto(resposta_texto)
    if any(_normalizar_texto(termo) in r for termo in termos):
        return True

    # Em demissão/rescisão, aceitar linguagem jurídica equivalente do domínio.
    if tema == "demissão":
        if any(_normalizar_texto(termo) in r for termo in _TERMOS_ADERENCIA_DEMISSAO):
            return True

    # Fallback semântico leve: se houver vocabulário jurídico compatível, não marcar fora de contexto.
    return any(_normalizar_texto(termo) in r for termo in _TERMOS_JURIDICOS_GENERICOS)


def _texto_resposta_para_validacao(payload: Dict[str, Any]) -> str:
    parecer = payload.get("parecer_executivo") if isinstance(payload.get("parecer_executivo"), dict) else {}
    partes = [
        str(payload.get("racional_risco") or ""),
        str(payload.get("pedido_complemento") or ""),
        str(payload.get("impacto_financeiro_texto") or ""),
        str(payload.get("tipo_caso") or ""),
        str(payload.get("tipo_risco") or ""),
        str(parecer.get("diagnostico_inicial") or ""),
        str(parecer.get("risco_juridico") or ""),
        str(parecer.get("proxima_acao_recomendada") or ""),
        str(parecer.get("estrategia_empresarial") or ""),
    ]
    return " ".join(partes).strip()


def _fallback_contexto_por_tema(tema: str | None) -> Dict[str, Any]:
    perguntas_por_tema = {
        "horas extras": [
            "Como é feito o controle de jornada e ponto atualmente?",
            "As horas extras são pagas ou compensadas formalmente?",
            "Há registros de banco de horas e aprovação do colaborador?",
        ],
        "gestante": [
            "A colaboradora estava grávida no momento da dispensa?",
            "Houve comunicação formal da gravidez e documentação médica?",
            "Qual foi o tipo de desligamento e em que data ocorreu?",
        ],
        "acidente": [
            "Houve emissão de CAT e registro formal do acidente?",
            "Existe afastamento médico com laudos e atestados?",
            "Quais medidas internas de segurança foram adotadas no caso?",
        ],
        "pj": [
            "O prestador cumpre horário fixo e recebe ordens diretas?",
            "Há exclusividade e pessoalidade na prestação de serviços?",
            "Existe contrato com escopo e autonomia bem definidos?",
        ],
        "fgts": [
            "O FGTS foi recolhido em todos os meses do vínculo?",
            "Há comprovantes de recolhimento e eventuais regularizações?",
            "Quais colaboradores e períodos podem ter inconsistências?",
        ],
        "assédio": [
            "Há mensagens, testemunhas ou relatos formais do ocorrido?",
            "Existe histórico de queixas anteriores sobre o gestor?",
            "Foi aberta apuração interna com registro formal?",
        ],
        "demissão": [
            "Qual foi o tipo de desligamento realizado?",
            "As verbas rescisórias foram pagas no prazo legal?",
            "Houve assinatura de TRCT e entrega das guias obrigatórias?",
        ],
    }
    perguntas = perguntas_por_tema.get(tema) or [
        "Qual foi o fato principal que gerou o risco trabalhista?",
        "Quais documentos e provas você já possui hoje?",
        "Em que fase está a demanda (preventiva, reclamação ou negociação)?",
    ]
    return {
        "tipo_caso": "duvida_geral",
        "tipo_risco": "geral",
        "gravidade": "media",
        "risco": "INCONCLUSIVO",
        "pontuacao": 45,
        "probabilidade": 45,
        "racional_risco": "Preciso entender melhor o seu caso para te orientar com segurança.",
        "perguntas_objetivas": perguntas[:3],
        "pedido_complemento": " ".join(f"{i + 1}. {q}" for i, q in enumerate(perguntas[:3])),
        "financeiro_com_base": False,
        "impacto_financeiro_texto": "Impacto financeiro depende de salário, tempo de vínculo e verbas discutidas.",
        "parecer_executivo": {
            "diagnostico_inicial": "Preciso entender melhor o seu caso para te orientar com segurança.",
            "risco_juridico": "Há risco potencial, dependente de confirmação de fatos e documentos.",
            "impacto_financeiro": "Impacto financeiro depende de salário, tempo de vínculo e verbas discutidas.",
            "proxima_acao_recomendada": perguntas[0],
            "estrategia_empresarial": "Consolidar informações antes da decisão final.",
        },
    }


def _garantir_bloco_acao_executiva(payload: Dict[str, Any], texto_usuario: str, tema: str | None) -> Dict[str, Any]:
    """
    Garante padrão executivo com ação prática.
    Não altera arquitetura: apenas complementa campos textuais finais.
    """
    out = dict(payload or {})
    parecer = out.get("parecer_executivo") if isinstance(out.get("parecer_executivo"), dict) else {}
    parecer = dict(parecer)

    acoes_por_tema = {
        "horas extras": "Próxima ação recomendada: revisar controle de ponto, mapear horas extras pendentes e iniciar regularização imediata.",
        "gestante": "Próxima ação recomendada: evitar demissão imediata, revisar documentos da estabilidade e validar estratégia jurídica antes de qualquer medida.",
        "acidente": "Próxima ação recomendada: levantar documentos do acidente, conferir CAT e regularizar imediatamente eventuais falhas formais.",
        "pj": "Próxima ação recomendada: revisar contrato e rotina do prestador, reduzir subordinação direta e estruturar regularização trabalhista.",
        "fgts": "Próxima ação recomendada: auditar recolhimentos de FGTS por período e executar plano de regularização com comprovação documental.",
        "assédio": "Próxima ação recomendada: abrir apuração interna formal, preservar evidências e adotar medida preventiva sobre a liderança envolvida.",
        "demissão": "Próxima ação recomendada: revisar TRCT, guias e comprovantes antes de nova decisão de desligamento.",
        None: "Próxima ação recomendada: consolidar documentos e fatos principais antes da decisão final.",
    }
    acao = acoes_por_tema.get(tema, acoes_por_tema[None])

    risco = str(out.get("risco") or "INCONCLUSIVO")
    consequencia = "possível questionamento trabalhista com impacto financeiro e operacional."
    complemento = f"Risco identificado: {risco}. Consequência possível: {consequencia} {acao}"

    racional = str(out.get("racional_risco") or "").strip()
    if len(racional) < 60 or "depende" in _normalizar_texto(racional):
        out["racional_risco"] = complemento

    pedido = str(out.get("pedido_complemento") or "").strip()
    if len(pedido) < 40:
        out["pedido_complemento"] = f"{pedido} {acao}".strip()
    elif "próxima ação recomendada" not in _normalizar_texto(pedido):
        out["pedido_complemento"] = f"{pedido} {acao}"

    # Campo obrigatório do padrão executivo.
    parecer["proxima_acao_recomendada"] = acao

    estrategia = str(parecer.get("estrategia_empresarial") or "").strip()
    if len(estrategia) < 35:
        parecer["estrategia_empresarial"] = f"{estrategia} {acao}".strip()

    diag = str(parecer.get("diagnostico_inicial") or "").strip()
    if len(diag) < 35:
        parecer["diagnostico_inicial"] = f"Risco identificado: {risco}. {acao}"

    risco_jur = str(parecer.get("risco_juridico") or "").strip()
    if len(risco_jur) < 35:
        parecer["risco_juridico"] = f"Há possibilidade de questionamento judicial. {acao}"

    out["parecer_executivo"] = parecer
    return out


def _sanitizar_linguagem_risco_zero(valor: Any) -> Any:
    """
    Evita afirmações absolutas de ausência de risco.
    Mantém estrutura e só ajusta linguagem textual.
    """
    if isinstance(valor, dict):
        return {k: _sanitizar_linguagem_risco_zero(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_sanitizar_linguagem_risco_zero(v) for v in valor]
    if not isinstance(valor, str):
        return valor

    texto = valor
    substituicoes = {
        "sem risco": "com risco reduzido, sujeito a questionamento",
        "não há risco": "há risco reduzido, com possibilidade de questionamento",
        "nao ha risco": "ha risco reduzido, com possibilidade de questionamento",
        "risco zero": "risco reduzido",
        "totalmente seguro": "relativamente seguro, dependendo de fatores",
    }
    for origem, destino in substituicoes.items():
        texto = texto.replace(origem, destino)
        texto = texto.replace(origem.capitalize(), destino.capitalize())
        texto = texto.replace(origem.upper(), destino.upper())
    return texto


def _json_from_text(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    if "```" in text:
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else parts[0]
        text = text.replace("json", "", 1).strip()
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {}


def _fallback_secondary_rules(texto: str) -> Dict[str, Any]:
    t = (texto or "").lower()
    perguntas: List[str] = []
    if "justa causa" not in t and "sem justa causa" not in t:
        perguntas.append("A dispensa foi sem justa causa ou por justa causa?")
    if "trct" not in t:
        perguntas.append("Houve assinatura do TRCT e quitação das verbas rescisórias?")
    if "fgts" not in t:
        perguntas.append("O FGTS estava regular durante o vínculo?")

    risco = "BAIXO"
    racional = "Sem indícios fortes no relato para risco elevado."
    if "gestante" in t and ("demit" in t or "dispens" in t):
        risco, racional = "ALTO", "Há indício de estabilidade gestante com dispensa."
    elif "justa causa" in t and ("sem prova" in t or "sem documento" in t):
        risco, racional = "ALTO", "Justa causa sem robustez documental tende a alto risco."
    elif "horas extras" in t and ("sem ponto" in t or "sem controle" in t):
        risco, racional = "MÉDIO", "Horas extras sem controle de jornada aumentam risco."
    elif "fgts" in t and ("atras" in t or "não recolh" in t or "nao recolh" in t):
        risco, racional = "MÉDIO", "Atraso de FGTS eleva risco trabalhista."

    return {
        "tipo_caso": "rescisao" if ("demit" in t or "dispens" in t) else "duvida_geral",
        "tipo_risco": "geral",
        "gravidade": "alta" if risco == "ALTO" else "media" if risco == "MÉDIO" else "baixa",
        "risco": risco,
        "pontuacao": 80 if risco == "ALTO" else 58 if risco == "MÉDIO" else 30,
        "probabilidade": 82 if risco == "ALTO" else 58 if risco == "MÉDIO" else 28,
        "racional_risco": racional,
        "perguntas_objetivas": perguntas[:5],
        "pedido_complemento": " ".join(f"{i + 1}. {q}" for i, q in enumerate(perguntas[:5])),
        "financeiro_com_base": False,
        "impacto_financeiro_texto": "Impacto financeiro depende de salário, tempo de vínculo e verbas discutidas.",
        "parecer_executivo": {
            "diagnostico_inicial": "Análise preliminar baseada no relato enviado.",
            "risco_juridico": racional,
            "impacto_financeiro": "Impacto financeiro depende de salário, tempo de vínculo e verbas discutidas.",
            "proxima_acao_recomendada": perguntas[0] if perguntas else "Consolidar documentos essenciais do caso.",
            "estrategia_empresarial": "Definir tese após fechamento de fatos e evidências.",
        },
    }


def _is_demissao_generica_quitada(texto: str) -> bool:
    t = (texto or "").lower()
    menciona_demissao = any(k in t for k in ["demit", "dispens", "rescis"])
    menciona_quitacao = any(k in t for k in ["paguei tudo", "quitei verbas", "quitacao", "quitação", "sem reclamação", "sem reclamacao"])
    sem_agravantes = not any(
        k in t
        for k in [
            "gestante",
            "justa causa",
            "sem prova",
            "fgts atras",
            "fgts em atraso",
            "horas extras",
            "assedio",
            "assédio",
            "acidente",
            "terceiriz",
        ]
    )
    return menciona_demissao and menciona_quitacao and sem_agravantes


def _ensure_perguntas_rescisao(payload: Dict[str, Any], texto_usuario: str) -> None:
    if payload.get("perguntas_objetivas"):
        return
    t = (texto_usuario or "").lower()
    if any(k in t for k in ["demit", "dispens", "rescis"]):
        payload["perguntas_objetivas"] = [
            "A dispensa foi sem justa causa ou por justa causa?",
            "Houve assinatura do TRCT e entrega das guias rescisórias?",
            "Qual era o tempo de casa do colaborador?",
            "O FGTS estava regular durante o vínculo?",
        ]


def _build_prompt_curto(texto_usuario: str) -> str:
    return f"""
Você é consultor trabalhista empresarial. Responda APENAS JSON válido.
Não invente dados. Se faltar base financeira use exatamente:
"Impacto financeiro depende de salário, tempo de vínculo e verbas discutidas."

REGRAS DE CLASSIFICAÇÃO (OBRIGATÓRIAS):
1) Em caso de dúvida, NÃO classifique como BAIXO.
2) Qualquer sinal de irregularidade => risco mínimo MÉDIO.
3) Se houver múltiplos riscos no mesmo relato => risco ALTO.
4) Riscos comuns trabalhistas (hora extra, FGTS, PJ/pejotização, banco de horas, assédio, acidente, verbas rescisórias) NÃO podem sair como BAIXO.
5) Se houver conflito, ameaça, advogado, processo, denúncia, litígio iminente ou linguagem de tensão => aumentar risco ao menos um nível.
6) Priorize proteção da empresa e postura defensiva; não beneficie a dúvida.
7) Só use BAIXO quando o relato indicar claramente regularidade e ausência de indícios de passivo.
8) Mantenha perguntas objetivas para reduzir incerteza, sem omitir risco preliminar.
9) NUNCA afirme ausência total de risco trabalhista. Mesmo em cenários seguros, sempre considerar possibilidade de questionamento judicial.
10) É proibido usar expressões: "sem risco", "não há risco", "risco zero", "totalmente seguro". Prefira: "risco baixo", "risco reduzido", "depende de fatores", "pode haver questionamento".
11) Se houver qualquer um destes sinais: horas extras não pagas, pagamento por fora, vínculo PJ com rotina fixa, conflito com funcionário, ameaça de processo, dúvida do empresário sobre legalidade => NUNCA classificar como BAIXO; classificar no mínimo como MÉDIO.
12) Se houver ameaça de processo, funcionário "estranho", "brigado" ou "reunindo provas" => classificar como ALTO.
13) Em conflito entre interpretações, escolher a opção mais protetiva para a empresa (evitar otimismo jurídico).
14) Cenários estruturais clássicos de passivo trabalhista devem ser classificados como ALTO (sem reduzir outros casos): vínculo PJ com rotina fixa e/ou subordinação (horário rígido, ordens diretas, exclusividade, todo dia na empresa); pagamento por fora ou informal (inclui \"por fora\", \"coisas por fora\", \"caixa\", valores sem holerite/recibo formal); justa causa aplicada sem base documental clara (ausência de advertências/fatos documentados, só relato oral ou narrativa vaga).
15) Mesmo que o usuário descreva o caso de forma leve ou informal, para os cenários do item 14 considerar risco estrutural elevado — não beneficie a linguagem otimista.
16) Se o item 14 se aplicar, o campo \"risco\" no JSON deve ser exatamente ALTO (não MÉDIO).
17) Pagamento por fora descrito como \"coisas por fora\", \"paguei por fora\", \"no caixa\", \"informal\" em salário ou verbas é cenário estrutural ALTO (item 14), mesmo sem valores ou períodos detalhados.
18) Se citar justa causa e o empresário demonstrar dúvida (\"sem risco\", \"posso\", \"será que\") => ALTO: presumir questão probatória em aberto até documentação robusta.

JSON:
{{
  "tipo_caso": "rescisao|afastamento|jornada|assedio|terceirizacao|duvida_geral",
  "tipo_risco": "geral|assedio_moral|acidente_trabalho|conflito_interpessoal|rescisorio|jornada|terceirizacao",
  "gravidade": "baixa|media|alta",
  "risco": "BAIXO|MÉDIO|ALTO|INCONCLUSIVO",
  "pontuacao": 0,
  "probabilidade": 0,
  "racional_risco": "texto curto",
  "perguntas_objetivas": ["pergunta 1"],
  "pedido_complemento": "texto curto",
  "financeiro_com_base": true,
  "impacto_financeiro_texto": "texto curto",
  "parecer_executivo": {{
    "diagnostico_inicial": "texto curto",
    "risco_juridico": "texto curto",
    "impacto_financeiro": "texto curto",
    "proxima_acao_recomendada": "texto curto",
    "estrategia_empresarial": "texto curto"
  }}
}}

Caso:
\"\"\"{texto_usuario}\"\"\"
"""


def _call_openai_fluxo(prompt: str) -> Dict[str, Any]:
    retries = 2
    for attempt in range(retries + 1):
        try:
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=prompt,
                timeout=12,
                max_output_tokens=450,
            )
            payload = _json_from_text(getattr(response, "output_text", ""))
            if payload:
                return payload
        except Exception:
            if attempt < retries:
                time.sleep(0.3 * (attempt + 1))
                continue
    return {}


# Incrementar quando _build_prompt_curto mudar — invalida LRU cache do fluxo OpenAI.
_PROMPT_FLUXO_VERSION = 5


@lru_cache(maxsize=256)
def _executar_fluxo_consulta_cached(motor_name: str, texto_usuario: str, prompt_version: int) -> Dict[str, Any]:
    if motor_name == "legacy":
        payload = _fallback_secondary_rules(texto_usuario)
    else:
        payload = _call_openai_fluxo(_build_prompt_curto(texto_usuario))
        if not payload:
            payload = _fallback_secondary_rules(texto_usuario)
    return payload


def executar_fluxo_consulta(texto_usuario: str, motor: str | None = None) -> Dict[str, Any]:
    motor_name = (motor or os.getenv("DP_IA_MOTOR", "openai")).strip().lower()
    if motor_name not in {"openai", "legacy"}:
        motor_name = "openai"

    payload = dict(_executar_fluxo_consulta_cached(motor_name, texto_usuario, _PROMPT_FLUXO_VERSION))
    tema = _extrair_tema_principal(texto_usuario)

    if not isinstance(payload.get("perguntas_objetivas"), list):
        payload["perguntas_objetivas"] = []
    payload["perguntas_objetivas"] = [str(x).strip() for x in payload["perguntas_objetivas"] if str(x).strip()][:5]

    payload["pontuacao"] = int(max(0, min(100, int(payload.get("pontuacao") or 0))))
    payload["probabilidade"] = int(max(0, min(100, int(payload.get("probabilidade") or 0))))
    payload["risco"] = str(payload.get("risco") or "INCONCLUSIVO").upper().replace("MEDIO", "MÉDIO")
    if payload["risco"] not in {"BAIXO", "MÉDIO", "ALTO", "INCONCLUSIVO"}:
        payload["risco"] = "INCONCLUSIVO"

    if not bool(payload.get("financeiro_com_base")):
        payload["impacto_financeiro_texto"] = "Impacto financeiro depende de salário, tempo de vínculo e verbas discutidas."

    if _is_demissao_generica_quitada(texto_usuario):
        if payload["risco"] == "MÉDIO":
            payload["risco"] = "INCONCLUSIVO"
        if payload["risco"] == "ALTO":
            payload["risco"] = "INCONCLUSIVO"
        payload["pontuacao"] = min(payload["pontuacao"], 34)
        payload["probabilidade"] = min(payload["probabilidade"], 34)
        payload["racional_risco"] = (
            "Relato genérico de demissão com quitação não indica passivo automático; "
            "é necessário confirmar documentos e prazos para concluir risco."
        )

    # Validação temática entre input e output.
    resposta_texto = _texto_resposta_para_validacao(payload)
    if not _validar_aderencia_resposta(tema, resposta_texto):
        if motor_name == "openai":
            regenerado = _call_openai_fluxo(_build_prompt_curto(texto_usuario))
            if isinstance(regenerado, dict) and regenerado:
                payload = regenerado
                if not isinstance(payload.get("perguntas_objetivas"), list):
                    payload["perguntas_objetivas"] = []
                payload["perguntas_objetivas"] = [
                    str(x).strip() for x in payload["perguntas_objetivas"] if str(x).strip()
                ][:5]
                payload["pontuacao"] = int(max(0, min(100, int(payload.get("pontuacao") or 0))))
                payload["probabilidade"] = int(max(0, min(100, int(payload.get("probabilidade") or 0))))
                payload["risco"] = str(payload.get("risco") or "INCONCLUSIVO").upper().replace("MEDIO", "MÉDIO")
                if payload["risco"] not in {"BAIXO", "MÉDIO", "ALTO", "INCONCLUSIVO"}:
                    payload["risco"] = "INCONCLUSIVO"
                if not bool(payload.get("financeiro_com_base")):
                    payload["impacto_financeiro_texto"] = "Impacto financeiro depende de salário, tempo de vínculo e verbas discutidas."
                resposta_texto = _texto_resposta_para_validacao(payload)
        if not _validar_aderencia_resposta(tema, resposta_texto):
            payload = _fallback_contexto_por_tema(tema)

    _ensure_perguntas_rescisao(payload, texto_usuario)
    if payload["risco"] == "INCONCLUSIVO" and not payload["perguntas_objetivas"]:
        payload["perguntas_objetivas"] = [
            "A dispensa foi sem justa causa ou por justa causa?",
            "Houve assinatura do TRCT?",
            "Qual era o tempo de casa?",
            "O FGTS estava regular?",
        ]
    payload = _garantir_bloco_acao_executiva(payload, texto_usuario, tema)
    payload = _sanitizar_linguagem_risco_zero(payload)

    payload["risco"] = _aplicar_risco_minimo_por_categoria(texto_usuario, payload.get("risco"))
    payload["risco"] = _aplicar_trava_risco_final(texto_usuario, payload.get("risco"))
    if payload["risco"] == "MÉDIO":
        payload["pontuacao"] = max(int(payload.get("pontuacao") or 0), 55)
        payload["probabilidade"] = max(int(payload.get("probabilidade") or 0), 55)
        payload["gravidade"] = payload.get("gravidade") or "media"
    if payload["risco"] == "ALTO":
        payload["pontuacao"] = max(int(payload.get("pontuacao") or 0), 80)
        payload["probabilidade"] = max(int(payload.get("probabilidade") or 0), 75)
        payload["gravidade"] = "alta"

    return payload
