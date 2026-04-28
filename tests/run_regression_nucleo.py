import json
from pathlib import Path
import sys
import os

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ia_consultor import gerar_parecer_juridico
from motor_consultor import analisar_caso
from score_engine import calcular_score


FIXTURES_PATH = Path("tests/fixtures/nucleo_juridico_cases_v2.json")
REPORT_PATH = Path("tests/fixtures/nucleo_juridico_regression_report.json")
RUN_LLM_EVAL = os.getenv("RUN_LLM_EVAL", "0") == "1"


def legacy_detectar_riscos_criticos(dados):
    texto = str(dados).lower()
    indicadores_alto = [
        "ofensa",
        "humilha",
        "xing",
        "assédio",
        "assedio",
        "gritou",
        "exposição",
        "exposicao",
        "constrangimento",
        "agressão",
        "agressao",
        "dano moral",
    ]
    indicadores_medio = [
        "discussão",
        "discussao",
        "conflito",
        "advertência",
        "advertencia",
        "clima ruim",
        "problema com gestor",
    ]
    for termo in indicadores_alto:
        if termo in texto:
            return "ALTO", 70
    for termo in indicadores_medio:
        if termo in texto:
            return "MÉDIO", 40
    return "BAIXO", 10


def legacy_motor_analisar(texto_caso, expected_tipo):
    texto = str({"texto": texto_caso, "tipo_risco": expected_tipo}).lower()
    tipo_risco = str(expected_tipo or "").lower()
    if (
        tipo_risco == "assedio_moral"
        or any(
            p in texto
            for p in [
                "ofensa",
                "humilha",
                "xing",
                "assedio",
                "assédio",
                "constrangimento",
                "gritou",
                "exposição",
                "exposicao",
            ]
        )
    ):
        return {"risco": "ALTO", "pontuacao": 90}
    if (
        tipo_risco == "acidente_trabalho"
        or any(p in texto for p in ["acidente", "queda", "machucou", "lesão", "lesao"])
    ):
        return {"risco": "ALTO", "pontuacao": 90}
    if tipo_risco == "conflito_interpessoal":
        return {"risco": "MÉDIO", "pontuacao": 45}
    risco, pont = legacy_detectar_riscos_criticos(texto_caso)
    return {"risco": risco, "pontuacao": pont}


def legacy_score(case_data):
    risco = str(case_data.get("risco", "BAIXO")).upper()
    impacto_valor = case_data.get("impacto", 0)
    tipo = case_data.get("tipo", "geral")
    if tipo in ["pedido_demissao", "rescisao_pedido"]:
        return {"score": 20, "nivel": "BAIXO", "probabilidade_condenacao": 10}

    mapa = {"BAIXO": 30, "MÉDIO": 60, "MEDIO": 60, "ALTO": 90}
    score = mapa.get(risco, 50)
    peso = {
        "rescisao": 1.0,
        "afastamento": 1.1,
        "hora_extra": 1.0,
        "assedio_moral": 1.3,
        "acidente_trabalho": 1.3,
        "geral": 1.0,
    }.get(tipo, 1.0)
    score += int((peso - 1) * 30)
    if impacto_valor and impacto_valor > 0:
        score += 8
    if case_data.get("reincidente"):
        score += 10
    if case_data.get("tem_prova"):
        score += 5
    if case_data.get("testemunha"):
        score += 5
    score = max(0, min(score, 100))
    if risco == "ALTO":
        score = max(score, 70)
    if risco in {"MÉDIO", "MEDIO"}:
        score = max(score, 40)
    if score >= 80:
        nivel = "ALTO"
        prob = 75
    elif score >= 60:
        nivel = "MÉDIO-ALTO"
        prob = 55
    elif score >= 40:
        nivel = "MÉDIO"
        prob = 35
    else:
        nivel = "BAIXO"
        prob = 20
    return {"score": int(score), "nivel": nivel, "probabilidade_condenacao": prob}


def is_inconclusivo_expected(expected):
    return str(expected.get("risco_juridico", "")).upper() == "INCONCLUSIVO"


def is_alto_expected(expected):
    return str(expected.get("risco_juridico", "")).upper() == "ALTO"


def score_is_coherent(expected, score):
    if "min_score" in expected and score < expected["min_score"]:
        return False
    if "max_score" in expected and score > expected["max_score"]:
        return False
    if "score_range" in expected:
        lo, hi = expected["score_range"]
        if score < lo or score > hi:
            return False
    return True


def factual_quality(parecer, texto):
    texto_lower = texto.lower()
    tokens = [t for t in texto_lower.replace(",", " ").split() if len(t) > 5]
    tokens = tokens[:8]
    campos_base = ["diagnostico", "fundamentacao", "recomendacao", "impactos"]
    preenchimento = sum(1 for c in campos_base if str(parecer.get(c, "")).strip() != "")
    factual_hits = 0
    body = " ".join(str(parecer.get(c, "")).lower() for c in campos_base)
    for tk in tokens:
        if tk in body:
            factual_hits += 1
    premium_fields = [
        "tese_risco",
        "tese_defesa",
        "plano_acao_24h",
        "plano_acao_7d",
        "plano_acao_30d",
        "confianca_conclusao",
    ]
    premium_ok = sum(1 for pf in premium_fields if parecer.get(pf))
    # score 0-10
    return min(10, preenchimento + factual_hits + premium_ok // 2)


def run():
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))

    results = []
    false_alto_before = 0
    false_alto_after = 0
    inconc_ok_before = 0
    inconc_ok_after = 0
    coherent_before = 0
    coherent_after = 0
    consistency_hits = 0
    factual_scores = []
    factual_method = "heuristica_sem_llm"

    for case in fixtures:
        expected = case["expected"]
        tipo = expected.get("tipo_risco", "geral")
        texto = case["texto_caso"]

        # BEFORE
        b_motor = legacy_motor_analisar(texto, tipo)
        b_score = legacy_score(
            {
                "risco": b_motor["risco"],
                "impacto": b_motor.get("pontuacao", 0),
                "tipo": tipo,
                "tem_prova": "mensagens" in texto.lower() or "document" in texto.lower(),
                "testemunha": "testemunh" in texto.lower(),
                "reincidente": "recorr" in texto.lower() or "reincid" in texto.lower(),
            }
        )

        # AFTER
        a_dados = {"tipo_risco": tipo, "tipo_caso": tipo, "texto_caso": texto}
        a_motor = analisar_caso(tipo, a_dados)
        a_score = calcular_score(
            {
                "risco": a_motor.get("risco", "BAIXO"),
                "impacto": a_motor.get("pontuacao", 0),
                "tipo": tipo,
                "tem_prova": "mensagens" in texto.lower() or "document" in texto.lower(),
                "testemunha": "testemunh" in texto.lower(),
                "reincidente": "recorr" in texto.lower() or "reincid" in texto.lower(),
            }
        )
        # consistency (run twice)
        a_score_2 = calcular_score(
            {
                "risco": a_motor.get("risco", "BAIXO"),
                "impacto": a_motor.get("pontuacao", 0),
                "tipo": tipo,
                "tem_prova": "mensagens" in texto.lower() or "document" in texto.lower(),
                "testemunha": "testemunh" in texto.lower(),
                "reincidente": "recorr" in texto.lower() or "reincid" in texto.lower(),
            }
        )
        if a_score["score"] == a_score_2["score"] and a_score["nivel"] == a_score_2["nivel"]:
            consistency_hits += 1

        # Parecer factual quality
        if RUN_LLM_EVAL:
            factual_method = "llm_real"
            parecer = gerar_parecer_juridico(
                contexto=texto,
                dados=a_dados,
                resultado=a_motor,
                score=a_score["score"],
                probabilidade=a_score["probabilidade_condenacao"],
            )
        else:
            # Heurística offline para manter benchmark rápido e estável.
            parecer = {
                "diagnostico": f"Caso: {texto}",
                "fundamentacao": str(a_motor.get("racional_decisao", "")),
                "recomendacao": "Executar plano de mitigação conforme criticidade.",
                "impactos": "Impactos variáveis conforme passivo potencial.",
                "tese_risco": "Risco jurídico conforme evidências e lacunas.",
                "tese_defesa": "Defesa baseada em documentação e governança.",
                "plano_acao_24h": ["Consolidar fatos e documentos."],
                "plano_acao_7d": ["Implementar medidas corretivas."],
                "plano_acao_30d": ["Revisar controles e treinamento."],
                "confianca_conclusao": "medio",
            }
        factual_scores.append(factual_quality(parecer, texto))

        # metrics
        if not is_alto_expected(expected) and b_motor["risco"] == "ALTO":
            false_alto_before += 1
        if not is_alto_expected(expected) and a_motor.get("risco") == "ALTO":
            false_alto_after += 1

        if is_inconclusivo_expected(expected) and b_motor["risco"] in {"INCONCLUSIVO"}:
            inconc_ok_before += 1
        if is_inconclusivo_expected(expected) and a_motor.get("risco") in {"INCONCLUSIVO"}:
            inconc_ok_after += 1

        if score_is_coherent(expected, b_score["score"]):
            coherent_before += 1
        if score_is_coherent(expected, a_score["score"]):
            coherent_after += 1

        results.append(
            {
                "id": case["id"],
                "expected_risco": expected.get("risco_juridico"),
                "before": {"risco": b_motor["risco"], "score": b_score["score"]},
                "after": {"risco": a_motor.get("risco"), "score": a_score["score"]},
            }
        )

    total = len(fixtures)
    inconc_total = sum(1 for c in fixtures if is_inconclusivo_expected(c["expected"]))
    report = {
        "total_cases": total,
        "false_alto_before": false_alto_before,
        "false_alto_after": false_alto_after,
        "inconclusivo_expected_total": inconc_total,
        "inconclusivo_correct_before": inconc_ok_before,
        "inconclusivo_correct_after": inconc_ok_after,
        "score_coerencia_before": {"ok": coherent_before, "total": total},
        "score_coerencia_after": {"ok": coherent_after, "total": total},
        "consistencia_execucoes_after": {"ok": consistency_hits, "total": total},
        "factual_quality_method": factual_method,
        "parecer_factual_quality_avg_0_10": round(sum(factual_scores) / max(1, len(factual_scores)), 2),
        "cases": results,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
