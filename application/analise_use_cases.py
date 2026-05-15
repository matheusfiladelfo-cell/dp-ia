import json

from analisador_caso import analisar_texto_usuario
from banco import incrementar_uso, obter_historico_empresa, salvar_analise
from application.score_engine_v2 import executar_score_engine_v2
from fluxo_consulta import executar_fluxo_consulta
from ia_client import client
from ia_consultor import gerar_parecer_juridico
from motor_consultor import analisar_caso
from score_engine import calcular_score, tipo_efetivo_para_score


def _risco_rank(label):
    mapa = {
        "BAIXO": 0,
        "INCONCLUSIVO": 0,
        "MÉDIO": 1,
        "MEDIO": 1,
        "MÉDIO-ALTO": 2,
        "MEDIO-ALTO": 2,
        "ALTO": 3,
    }
    return mapa.get(str(label or "").upper(), 0)


def executar_analise_e_score(texto_usuario):
    dados = analisar_texto_usuario(texto_usuario)

    resultado = analisar_caso(
        dados.get("tipo_caso"),
        dados,
    )

    impacto_temp = resultado.get("impacto", 0)

    if dados.get("tipo_risco") in ["assedio_moral", "acidente_trabalho"]:
        resultado["risco"] = "ALTO"

    tipo_para_score = tipo_efetivo_para_score(dados)

    # Regra de negocio mantida para nao alterar comportamento.
    if dados.get("tipo_caso") == "pedido_demissao":
        tipo_para_score = "pedido_demissao"
        resultado["risco"] = "BAIXO"

    if dados.get("tipo_risco") in ["assedio_moral", "acidente_trabalho"]:
        resultado["risco"] = "ALTO"

    score_data = calcular_score(
        {
            "risco": resultado.get("risco", "BAIXO"),
            "impacto": impacto_temp,
            "tem_prova": dados.get("tem_prova", False),
            "testemunha": dados.get("testemunha", False),
            "reincidente": dados.get("reincidente", False),
            "tipo": tipo_para_score,
            "texto": texto_usuario,
            "descricao": texto_usuario,
            "tempo_empresa_meses": dados.get("tempo_empresa_meses") or 0,
        }
    )

    # Camada de proteção: nunca reduzir risco do motor, apenas elevar quando o score
    # (com hard rules/ancoragem jurídica) indicar nível mais crítico.
    if _risco_rank(score_data.get("nivel")) > _risco_rank(resultado.get("risco")):
        resultado["risco"] = score_data.get("nivel")

    return {
        "dados": dados,
        "resultado": resultado,
        "score": score_data["score"],
        "probabilidade": score_data["probabilidade_condenacao"],
        "nivel": score_data["nivel"],
        "motivos": score_data["motivos"],
    }


def gerar_parecer_e_salvar_analise(
    texto_usuario,
    usuario_id,
    empresa_id,
    dados,
    resultado,
    score,
    probabilidade,
    nivel,
    motivos,
):
    parecer = gerar_parecer_juridico(
        contexto=texto_usuario,
        dados=dados,
        resultado=resultado,
        score=score,
        probabilidade=probabilidade,
    )

    incrementar_uso(usuario_id)

    salvar_analise(
        empresa_id,
        dados.get("tipo_caso"),
        parecer.get("risco"),
        resultado.get("pontuacao"),
        dados,
        {
            **resultado,
            "score": score,
            "probabilidade": probabilidade,
            "nivel": nivel,
            "motivos": motivos,
        },
        parecer,
        criado_por_usuario_id=usuario_id,
    )

    return parecer


def gerar_relatorio_final(conversa):
    dados = analisar_texto_usuario(conversa)
    fluxo = executar_fluxo_consulta(conversa)

    dados["fluxo_consulta"] = fluxo
    dados["tipo_caso"] = dados.get("tipo_caso") or fluxo.get("tipo_caso")
    dados["tipo_risco"] = dados.get("tipo_risco") or fluxo.get("tipo_risco")
    dados["gravidade"] = dados.get("gravidade") or fluxo.get("gravidade")

    resultado = {
        "risco": fluxo.get("risco", "INCONCLUSIVO"),
        "pontuacao": int(fluxo.get("pontuacao") or 0),
        "racional_decisao": fluxo.get("racional_risco") or "",
        "perguntas_objetivas": fluxo.get("perguntas_objetivas") or [],
    }

    tipo_para_score = tipo_efetivo_para_score(dados)
    score_data = calcular_score(
        {
            "risco": resultado.get("risco", "INCONCLUSIVO"),
            "impacto": 0,
            "tem_prova": dados.get("tem_prova", False),
            "testemunha": dados.get("testemunha", False),
            "reincidente": dados.get("reincidente", False),
            "tipo": tipo_para_score,
            "texto": conversa,
            "descricao": conversa,
            "tempo_empresa_meses": dados.get("tempo_empresa_meses") or 0,
        }
    )

    parecer = gerar_parecer_juridico(
        contexto=conversa,
        dados=dados,
        resultado=resultado,
        score=score_data["score"],
        probabilidade=score_data["probabilidade_condenacao"],
    )

    return {
        "dados": dados,
        "resultado": resultado,
        "score": score_data["score"],
        "probabilidade": score_data["probabilidade_condenacao"],
        "nivel": score_data["nivel"],
        "motivos": score_data["motivos"],
        "parecer": parecer,
    }


def _json_from_text(raw):
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
        return {}
    return {}


def _normalizar_nivel_risco(label):
    risco = str(label or "").upper().replace("MEDIO", "MÉDIO")
    if "ALTO" in risco:
        return "ALTO"
    if "MÉDIO" in risco:
        return "MÉDIO"
    if "BAIXO" in risco:
        return "BAIXO"
    return "INCONCLUSIVO"


def _gerar_base_legal_simplificada(fluxo):
    tema = str(fluxo.get("tipo_risco") or fluxo.get("tipo_caso") or "").lower()
    base = ["CLT - verbas rescisórias e obrigações contratuais"]
    if "gestante" in tema:
        base.append("Estabilidade gestante")
    if "jornada" in tema or "hora" in tema:
        base.append("CLT - jornada de trabalho e horas extras")
    if "fgts" in tema:
        base.append("FGTS - recolhimento e regularidade mensal")
    if "assedio" in tema:
        base.append("Proteção à dignidade no ambiente de trabalho")
    if "acidente" in tema:
        base.append("Saúde e segurança do trabalho")
    return base[:3]


def _gerar_checklist_plano(plano_acao):
    texto = str(plano_acao or "").strip()
    itens = []
    if texto:
        partes = [p.strip(" -.;") for p in texto.replace("\n", ". ").split(".")]
        itens = [p for p in partes if len(p) > 10][:4]
    if not itens:
        itens = [
            "Levantar histórico do funcionário e cronologia dos fatos.",
            "Revisar documentos, recibos e comunicações internas.",
            "Evitar decisão imediata sem validação jurídica completa.",
            "Preparar estratégia de defesa e mitigação com responsáveis definidos.",
        ]
    return itens


def _simulacao_decisao_por_risco(nivel_risco):
    if nivel_risco == "ALTO":
        return {
            "se_demitir_agora": "ALTO",
            "se_regularizar_antes": "MÉDIO",
            "se_negociar_acordo": "BAIXO/MÉDIO",
        }
    if nivel_risco == "MÉDIO":
        return {
            "se_demitir_agora": "MÉDIO/ALTO",
            "se_regularizar_antes": "MÉDIO",
            "se_negociar_acordo": "BAIXO/MÉDIO",
        }
    if nivel_risco == "BAIXO":
        return {
            "se_demitir_agora": "MÉDIO",
            "se_regularizar_antes": "BAIXO",
            "se_negociar_acordo": "BAIXO",
        }
    return {
        "se_demitir_agora": "INCONCLUSIVO",
        "se_regularizar_antes": "INCONCLUSIVO",
        "se_negociar_acordo": "INCONCLUSIVO",
    }


def _gerar_proximos_passos_recomendados(nivel_risco):
    passos_base = [
        "Revisar documentos críticos do caso em até 48h.",
        "Evitar demissão ou medida irreversível até validação jurídica completa.",
        "Levantar histórico do funcionário e cronologia dos fatos em até 72h.",
        "Definir estratégia com RH e jurídico e responsáveis internos em até 5 dias.",
    ]
    if nivel_risco == "ALTO":
        return passos_base + ["Apresentar plano de mitigação para diretoria em até 7 dias."]
    if nivel_risco == "MÉDIO":
        return passos_base
    if nivel_risco == "BAIXO":
        return passos_base[:3] + ["Implementar ajuste preventivo de processo interno em até 7 dias."]
    return passos_base


def gerar_relatorio_consultoria(
    conversa, empresa_id=None, criado_por_usuario_id=None, analise_id_stub_fatos=None
):
    fluxo = executar_fluxo_consulta(conversa)
    prompt = f"""
Você é consultor trabalhista executivo para empresas.
Responda APENAS JSON válido com os 5 campos obrigatórios.

Regras obrigatórias:
- Linguagem executiva, clara e específica (sem texto genérico).
- Sempre indicar ação prática no plano de ação.
- Nunca afirmar "risco zero", "sem risco" ou equivalentes.
- Sempre priorizar proteção jurídica e financeira da empresa.

Contexto da conversa:
\"\"\"{conversa}\"\"\"

Sinais e triagem prévia:
{json.dumps(fluxo, ensure_ascii=False)}

JSON obrigatório:
{{
  "diagnostico": "...",
  "risco_juridico": "...",
  "impacto_financeiro": "...",
  "plano_acao": "...",
  "estrategia": "..."
}}
"""
    payload = {}
    try:
        resposta = client.responses.create(
            model="gpt-4.1",
            input=prompt,
            timeout=25,
        )
        payload = _json_from_text(getattr(resposta, "output_text", ""))
    except Exception:
        payload = {}

    diagnostico = str(payload.get("diagnostico") or fluxo.get("racional_risco") or "Caso com potencial passivo trabalhista que exige validação documental imediata.").strip()
    risco_juridico = str(payload.get("risco_juridico") or f"Classificação preliminar: {fluxo.get('risco', 'INCONCLUSIVO')}. Há possibilidade de questionamento judicial e necessidade de estratégia defensiva.").strip()
    impacto_financeiro = str(payload.get("impacto_financeiro") or fluxo.get("impacto_financeiro_texto") or "Impacto financeiro depende de salário, tempo de vínculo e verbas discutidas.").strip()
    plano_acao = str(payload.get("plano_acao") or fluxo.get("pedido_complemento") or "Consolidar cronologia, documentos e responsáveis internos hoje para reduzir exposição.").strip()
    estrategia = str(payload.get("estrategia") or "Atuar com postura conservadora: corrigir passivos, preparar defesa documental e negociar apenas com teto definido.").strip()

    if "risco zero" in risco_juridico.lower() or "sem risco" in risco_juridico.lower():
        risco_juridico = "Há risco jurídico potencial e possibilidade de questionamento; recomenda-se mitigação imediata."

    nivel_risco = _normalizar_nivel_risco(fluxo.get("risco"))
    checklist = _gerar_checklist_plano(plano_acao)
    base_legal = _gerar_base_legal_simplificada(fluxo)
    decisao_recomendada = (
        "Evitar decisão imediata até validação completa dos dados e documentos críticos."
        if nivel_risco in {"ALTO", "MÉDIO"}
        else "Prosseguir com cautela, mantendo validação documental e monitoramento jurídico."
    )

    historico_empresa = (
        obter_historico_empresa(empresa_id, criado_por_usuario_id=criado_por_usuario_id)
        if empresa_id
        else {
            "total_ocorrencias": 0,
            "tipos_frequentes": [],
            "riscos_frequentes": [],
            "resumo": "",
        }
    )

    score_engine_v2_payload = {
        "disponivel": False,
        "score_final": None,
        "nivel": None,
        "racional": [],
        "fatos_utilizados": {},
        "pontuacao_bruta": None,
    }
    if analise_id_stub_fatos is not None:
        try:
            score_engine_v2_payload = executar_score_engine_v2(int(analise_id_stub_fatos))
        except Exception:
            score_engine_v2_payload = {
                "disponivel": False,
                "score_final": None,
                "nivel": None,
                "racional": ["Falha ao executar o motor de score v2; tente novamente ou revise os fatos salvos."],
                "fatos_utilizados": {},
                "pontuacao_bruta": None,
            }

    return {
        "diagnostico": diagnostico,
        "risco_juridico": risco_juridico,
        "impacto_financeiro": impacto_financeiro,
        "plano_acao": plano_acao,
        "plano_acao_checklist": checklist,
        "estrategia": estrategia,
        "base_legal_simplificada": base_legal,
        "nivel_risco_visual": nivel_risco,
        "decisao_recomendada": decisao_recomendada,
        "simulacao_decisao": _simulacao_decisao_por_risco(nivel_risco),
        "proximos_passos_recomendados": _gerar_proximos_passos_recomendados(nivel_risco),
        "historico_empresa": historico_empresa,
        "fluxo_consulta": fluxo,
        "score_engine_v2": score_engine_v2_payload,
    }
