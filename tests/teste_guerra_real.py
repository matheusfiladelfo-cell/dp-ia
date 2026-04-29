import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from analisador_caso import analisar_texto_usuario
from ia_consultor import gerar_parecer_juridico
from motor_consultor import analisar_caso
from score_engine import calcular_score, tipo_efetivo_para_score


RISK_RANK = {
    "BAIXO": 1,
    "MÉDIO": 2,
    "MEDIO": 2,
    "MÉDIO-ALTO": 3,
    "MEDIO-ALTO": 3,
    "ALTO": 4,
    "INCONCLUSIVO": 0,
}


def _build_cases():
    base_cases = [
        {"entrada": "mandei embora gravida e nao paguei nada", "expected_min_risk": "ALTO", "expected_min_score": 85, "tag": "gestante_dispensada"},
        {"entrada": "funcionario trabalhou 2 anos sem carteira", "expected_min_risk": "ALTO", "expected_min_score": 78, "tag": "sem_registro"},
        {"entrada": "dei justa causa mas nao tenho prova", "expected_min_risk": "ALTO", "expected_min_score": 80, "tag": "justa_causa_sem_prova"},
        {"entrada": "ela pediu a conta e paguei tudo certo com recibos", "expected_max_risk": "BAIXO", "expected_max_score": 35, "tag": "pedido_demissao_quitado"},
        {"entrada": "ex funcionario pediu 100 mil de horas extras", "expected_min_risk": "MÉDIO", "expected_min_score": 55, "tag": "horas_extras"},
        {"entrada": "acidente no trabalho e nao fiz CAT", "expected_min_risk": "ALTO", "expected_min_score": 84, "tag": "acidente_sem_cat"},
        {"entrada": "assedio com prints e testemunha", "expected_min_risk": "ALTO", "expected_min_score": 83, "tag": "assedio_com_provas"},
        {"entrada": "paguei por fora varios meses", "expected_min_risk": "MÉDIO", "expected_min_score": 55, "tag": "pagamento_irregular"},
        {"entrada": "funcionario sumiu e quer direitos", "expected_min_risk": "BAIXO", "expected_min_score": 15, "tag": "ambiguo"},
        {"entrada": "rescisao atrasou 20 dias", "expected_min_risk": "MÉDIO", "expected_min_score": 42, "tag": "rescisao_atrasada"},
        {"entrada": "funcionaria entrou na justiça pedindo 70 mil", "expected_min_risk": "MÉDIO", "expected_min_score": 55, "tag": "litigio"},
        {"entrada": "acordo de 30 mil vale a pena?", "expected_min_risk": "BAIXO", "expected_min_score": 20, "tag": "consulta_preventiva"},
        {"entrada": "trabalhava domingo sem folga", "expected_min_risk": "MÉDIO", "expected_min_score": 50, "tag": "jornada"},
        {"entrada": "banco de horas sem assinatura", "expected_min_risk": "MÉDIO", "expected_min_score": 50, "tag": "jornada"},
        {"entrada": "gerente humilhava empregado", "expected_min_risk": "MÉDIO", "expected_min_score": 55, "tag": "assedio"},
        {"entrada": "salario pago picado", "expected_min_risk": "MÉDIO", "expected_min_score": 50, "tag": "pagamento_irregular"},
        {"entrada": "sem FGTS 1 ano", "expected_min_risk": "MÉDIO", "expected_min_score": 55, "tag": "fgts"},
        {"entrada": "contrato PJ mas batia ponto", "expected_min_risk": "MÉDIO", "expected_min_score": 55, "tag": "pejotizacao"},
        {"entrada": "terceirizado com subordinação direta", "expected_min_risk": "MÉDIO", "expected_min_score": 55, "tag": "terceirizacao"},
        {"entrada": "férias vencidas não pagas", "expected_min_risk": "MÉDIO", "expected_min_score": 55, "tag": "ferias"},
    ]
    extra_cases = [
        {"entrada": "dispensei uma gestante no oitavo mes e sem acerto", "expected_min_risk": "ALTO", "expected_min_score": 85, "tag": "gestante_dispensada"},
        {"entrada": "trabalhou sem registro por 6 meses e agora cobrou direitos", "expected_min_risk": "ALTO", "expected_min_score": 78, "tag": "sem_registro"},
        {"entrada": "apliquei justa causa sem documentos e sem testemunhas", "expected_min_risk": "ALTO", "expected_min_score": 80, "tag": "justa_causa_sem_prova"},
        {"entrada": "pedido de demissao com quitacao total e todos recibos assinados", "expected_max_risk": "BAIXO", "expected_max_score": 35, "tag": "pedido_demissao_quitado"},
        {"entrada": "houve acidente de trabalho e a empresa nao abriu CAT", "expected_min_risk": "ALTO", "expected_min_score": 84, "tag": "acidente_sem_cat"},
        {"entrada": "assedio no setor com audio, prints e testemunha presencial", "expected_min_risk": "ALTO", "expected_min_score": 83, "tag": "assedio_com_provas"},
        {"entrada": "hora extra todo dia e jornada excessiva sem ponto", "expected_min_risk": "MÉDIO", "expected_min_score": 72, "tag": "horas_extras"},
        {"entrada": "nao paguei rescisao e ficou sem acerto", "expected_min_risk": "ALTO", "expected_min_score": 82, "tag": "verbas_nao_pagas"},
        {"entrada": "demissao sem justa causa com pagamento completo no prazo", "expected_min_risk": "BAIXO", "expected_min_score": 20, "tag": "rescisao_regular"},
        {"entrada": "funcionario pediu para sair, paguei tudo e entreguei documentos", "expected_max_risk": "BAIXO", "expected_max_score": 35, "tag": "pedido_demissao_quitado"},
    ]
    return base_cases + extra_cases


def _rank(risk):
    return RISK_RANK.get(str(risk or "").upper(), 0)


def _extract_hard_rule(resultado, score_data):
    alertas = resultado.get("alertas") if isinstance(resultado.get("alertas"), list) else []
    for alerta in alertas:
        tipo = str(alerta.get("tipo", ""))
        if "HARD RULE" in tipo:
            return tipo
    motivos = score_data.get("motivos") if isinstance(score_data.get("motivos"), list) else []
    for motivo in motivos:
        fator = str(motivo.get("fator", ""))
        if "Hard rule 10" in fator:
            return fator
    return "-"


def _is_case_ok(case, risco, score):
    score = int(score or 0)
    risco_rank = _rank(risco)

    if "expected_min_risk" in case:
        if risco_rank < _rank(case["expected_min_risk"]):
            return False
    if "expected_min_score" in case:
        if score < int(case["expected_min_score"]):
            return False
    if "expected_max_risk" in case:
        if risco_rank > _rank(case["expected_max_risk"]):
            return False
    if "expected_max_score" in case:
        if score > int(case["expected_max_score"]):
            return False
    return True


def run():
    cases = _build_cases()
    total_ok = 0
    total_alerta = 0
    run_llm_eval = os.getenv("RUN_LLM_EVAL", "0") == "1"

    print("=" * 86)
    print("BATERIA ETAPA 10D - TESTE DE GUERRA REAL (30 CASOS)")
    print("=" * 86)

    for idx, case in enumerate(cases, start=1):
        entrada = case["entrada"]
        dados = analisar_texto_usuario(entrada)
        resultado = analisar_caso(dados.get("tipo_caso"), dados)

        resultado = dict(resultado)
        if dados.get("tipo_risco") in ["assedio_moral", "acidente_trabalho"]:
            resultado["risco"] = "ALTO"
        tipo_para_score = tipo_efetivo_para_score(dados)
        if dados.get("tipo_caso") == "pedido_demissao":
            tipo_para_score = "pedido_demissao"
            resultado["risco"] = "BAIXO"
        if dados.get("tipo_risco") in ["assedio_moral", "acidente_trabalho"]:
            resultado["risco"] = "ALTO"
        score_data = calcular_score(
            {
                "risco": resultado.get("risco", "BAIXO"),
                "impacto": resultado.get("impacto", 0),
                "tem_prova": dados.get("tem_prova", False),
                "testemunha": dados.get("testemunha", False),
                "reincidente": dados.get("reincidente", False),
                "tipo": tipo_para_score,
                "texto": entrada,
                "descricao": entrada,
                "tempo_empresa_meses": dados.get("tempo_empresa_meses", 0),
            }
        )

        score = score_data.get("score", 0)
        prob = score_data.get("probabilidade_condenacao", 0)
        risco = score_data.get("nivel", resultado.get("risco", "N/A"))
        hard_rule = _extract_hard_rule(resultado, score_data)

        if run_llm_eval:
            parecer = gerar_parecer_juridico(
                contexto=entrada,
                dados=dados,
                resultado=resultado,
                score=score,
                probabilidade=prob,
            )
        else:
            parecer = {
                "veredito_estrategico": {
                    "resumo_executivo_1_linha": f"Risco {risco}; score {score}; probabilidade {prob}%; ação orientada por hard rules."
                }
            }
        resumo = (
            (parecer.get("veredito_estrategico") or {}).get("resumo_executivo_1_linha")
            or "Sem resumo executivo disponível."
        )

        ok = _is_case_ok(case, risco, score)
        status = "OK" if ok else "ALERTA"
        if ok:
            total_ok += 1
        else:
            total_alerta += 1

        print(f"\n[{idx:02d}] {status}")
        print(f"entrada: {entrada}")
        print(f"risco: {risco}")
        print(f"score: {score}")
        print(f"probabilidade: {prob}%")
        print(f"veredito_estrategico.resumo_executivo_1_linha: {resumo}")
        print(f"hard_rule_acionada: {hard_rule}")

    total = len(cases)
    coerencia = (total_ok / total * 100.0) if total else 0.0

    print("\n" + "=" * 86)
    print(f"Total OK: {total_ok}")
    print(f"Total ALERTA: {total_alerta}")
    print(f"Taxa de coerência %: {coerencia:.2f}")
    print("=" * 86)


if __name__ == "__main__":
    run()

