import json
import os
import time
from functools import lru_cache
from typing import Any, Dict, List

from ia_client import client


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


@lru_cache(maxsize=256)
def _executar_fluxo_consulta_cached(motor_name: str, texto_usuario: str) -> Dict[str, Any]:
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

    payload = dict(_executar_fluxo_consulta_cached(motor_name, texto_usuario))

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

    _ensure_perguntas_rescisao(payload, texto_usuario)
    if payload["risco"] == "INCONCLUSIVO" and not payload["perguntas_objetivas"]:
        payload["perguntas_objetivas"] = [
            "A dispensa foi sem justa causa ou por justa causa?",
            "Houve assinatura do TRCT?",
            "Qual era o tempo de casa?",
            "O FGTS estava regular?",
        ]
    return payload
