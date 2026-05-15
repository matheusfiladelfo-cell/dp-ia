"""
Extração assistida por LLM de fatos trabalhistas a partir de texto de documento.
Tratar sempre como sugestão — conferência humana obrigatória.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ia_client import client

CHAVES_JSON = (
    "nome_empregado",
    "data_admissao",
    "data_demissao",
    "valor_salario",
    "tipo_contrato",
    "motivo_reclamacao",
    "evidencias_mencionadas",
)

LABELS_PT = {
    "nome_empregado": "Nome do empregado",
    "data_admissao": "Data de admissão",
    "data_demissao": "Data de demissão",
    "valor_salario": "Salário mencionado",
    "tipo_contrato": "Tipo de vínculo / contrato",
    "motivo_reclamacao": "Motivo da reclamação (resumo)",
    "evidencias_mencionadas": "Evidências / provas citadas",
}

MAX_CHARS_EXTRACAO = 32_000


PROMPT_EXTRACAO_FATOS = """Você é um assistente de análise jurídica especializado em direito do trabalho brasileiro.

Sua ÚNICA tarefa é ler o texto abaixo e extrair os seguintes campos, quando houver indício claro no documento.
Se um campo não estiver presente ou for ambíguo, retorne exatamente a string "Não encontrado" (para campos de texto) ou lista vazia [] (apenas para evidencias_mencionadas).

Para valor_salario, use formato brasileiro quando houver valor (ex.: "R$ 2.800,00" ou "2800").
Se houver data_admissao e data_demissao válidas, calcule também tempo_empresa_meses como número inteiro (meses de vínculo).

NÃO invente dados. NÃO complete lacunas com suposições.
As evidências devem ser lista de strings curtas descrevendo provas ou documentos citados no texto.

IMPORTANTE: responda APENAS com um único objeto JSON válido, sem markdown, sem texto antes ou depois.

Texto do documento:
\"\"\"
{texto}
\"\"\"

JSON obrigatório (todas as chaves devem existir):
{{
  "nome_empregado": "...",
  "data_admissao": "...",
  "data_demissao": "...",
  "valor_salario": "...",
  "tipo_contrato": "...",
  "motivo_reclamacao": "...",
  "evidencias_mencionadas": [],
  "tempo_empresa_meses": null
}}

tempo_empresa_meses: inteiro (ex.: 52) ou null se não for possível calcular pelas datas.
"""


def _parse_json_resposta_llm(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if "```" in text:
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else parts[0]
        text = text.replace("json", "", 1).strip()
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _eh_nao_encontrado(valor: Any) -> bool:
    if valor is None:
        return True
    if isinstance(valor, list):
        return len(valor) == 0
    s = str(valor).strip().lower()
    return not s or s in {"não encontrado", "nao encontrado", "n/a", "na", "null", "none", "-"}


def _normalizar_fatos_brutos(data: dict[str, Any]) -> dict[str, Any]:
    """Preenche chaves esperadas; não corrige conteúdo da IA."""
    out: dict[str, Any] = {}
    for chave in CHAVES_JSON:
        v = data.get(chave)
        if chave == "evidencias_mencionadas":
            if isinstance(v, list):
                out[chave] = [str(x).strip() for x in v if str(x).strip()]
            elif isinstance(v, str) and not _eh_nao_encontrado(v):
                out[chave] = [s.strip() for s in re.split(r"[;\n]", v) if s.strip()]
            else:
                out[chave] = []
        else:
            if v is None or (isinstance(v, str) and not v.strip()):
                out[chave] = "Não encontrado"
            else:
                out[chave] = str(v).strip()
    return out


def analisar_fatos_documento(texto_documento: str) -> dict[str, Any]:
    """
    Chama a LLM para extrair fatos estruturados.
    Em falha de API ou JSON inválido, retorna dicionário vazio.
    """
    trecho = (texto_documento or "").strip()
    if not trecho:
        return {}

    if len(trecho) > MAX_CHARS_EXTRACAO:
        trecho = trecho[:MAX_CHARS_EXTRACAO].rstrip() + "\n\n[... texto truncado para extração ...]"

    prompt = PROMPT_EXTRACAO_FATOS.format(texto=trecho)

    try:
        resposta = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            timeout=45,
        )
        bruto = _parse_json_resposta_llm(getattr(resposta, "output_text", "") or "")
        if not bruto:
            return {}
        return _normalizar_fatos_brutos(bruto)
    except Exception:
        return {}


def formatar_fatos_para_contexto_llm(fatos: dict[str, Any]) -> str:
    """Bloco legível para prompts subsequentes (chat / relatório)."""
    if not fatos:
        return ""
    linhas = [
        "[Fatos extraídos automaticamente pela IA a partir do documento — conferir nas fontes originais.]",
    ]
    for chave in CHAVES_JSON:
        rotulo = LABELS_PT.get(chave, chave)
        valor = fatos.get(chave)
        if chave == "evidencias_mencionadas" and isinstance(valor, list):
            if not valor:
                linhas.append(f"- {rotulo}: Não encontrado")
            else:
                linhas.append(f"- {rotulo}: " + "; ".join(valor))
        else:
            linhas.append(f"- {rotulo}: {valor}")
    return "\n".join(linhas)


def _parse_salario_para_float(valor_bruto: Any) -> float | None:
    from application.parsing_br import parse_moeda_br

    if _eh_nao_encontrado(valor_bruto):
        return None
    return parse_moeda_br(valor_bruto)


def aplicar_fatos_documento_na_sessao(sessao: Any, fatos: dict[str, Any]) -> None:
    """
    Consolida fatos na memória de sessão para contexto do LLM e uso futuro pelo fluxo_consulta,
    sem sobrescrever dados já informados pelo usuário no chat quando possível.
    """
    if not fatos:
        return

    sessao.atualizar_dados({"extracao_documento_ia": fatos})

    if not _eh_nao_encontrado(fatos.get("nome_empregado")):
        sessao.atualizar_dados({"nome_empregado_documento_ia": fatos["nome_empregado"]})

    if not _eh_nao_encontrado(fatos.get("data_admissao")):
        sessao.atualizar_dados({"data_admissao_documento_ia": fatos["data_admissao"]})

    if not _eh_nao_encontrado(fatos.get("data_demissao")):
        sessao.atualizar_dados({"data_demissao_documento_ia": fatos["data_demissao"]})

    if not _eh_nao_encontrado(fatos.get("valor_salario")):
        sessao.atualizar_dados({"valor_salario_documento_ia": str(fatos["valor_salario"])})

    parsed_sal = _parse_salario_para_float(fatos.get("valor_salario"))
    if parsed_sal is not None:
        atual = sessao.obter_dados().get("salario")
        if atual is None or atual == "":
            sessao.atualizar_dados({"salario": parsed_sal})

    tempo_m = fatos.get("tempo_empresa_meses")
    if tempo_m is not None and not _eh_nao_encontrado(tempo_m):
        try:
            meses_ia = int(float(str(tempo_m).strip().replace(",", ".")))
            if meses_ia > 0:
                atual_m = sessao.obter_dados().get("tempo_empresa_meses")
                if atual_m is None or atual_m == "" or atual_m == 0:
                    sessao.atualizar_dados({"tempo_empresa_meses": meses_ia})
        except (TypeError, ValueError):
            pass

    if not _eh_nao_encontrado(fatos.get("tipo_contrato")):
        sessao.atualizar_dados({"tipo_contrato_documento_ia": fatos["tipo_contrato"]})
        tc = str(fatos["tipo_contrato"]).upper()
        atual_tc = sessao.obter_dados().get("tipo_caso")
        if atual_tc is None or atual_tc == "":
            if "PJ" in tc or "MEI" in tc or "AUTÔNOM" in tc or "AUTONOM" in tc:
                sessao.atualizar_dados({"tipo_caso": "terceirizacao"})
            elif "CLT" in tc or "EFETIV" in tc or "TEMPORÁR" in tc or "TEMPORAR" in tc:
                sessao.atualizar_dados({"tipo_caso": "duvida_geral"})

    if not _eh_nao_encontrado(fatos.get("motivo_reclamacao")):
        sessao.atualizar_dados({"motivo_reclamacao_documento_ia": fatos["motivo_reclamacao"]})

    ev = fatos.get("evidencias_mencionadas")
    if isinstance(ev, list) and ev:
        sessao.atualizar_dados({"evidencias_documento_ia": "; ".join(ev)})
