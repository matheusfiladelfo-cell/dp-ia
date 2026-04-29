from analisador_caso import analisar_texto_usuario
from banco import incrementar_uso, salvar_analise
from ia_consultor import gerar_parecer_juridico
from motor_consultor import analisar_caso
from score_engine import calcular_score, tipo_efetivo_para_score


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
    )

    return parecer
