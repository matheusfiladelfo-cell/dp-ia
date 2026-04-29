"""
Comparação automatizada 10 casos — métricas objetivas + rubrica 1–10 por dimensão.
Chamar duas vezes: após stash (2.0) e após stash pop (3.0).
"""
import json
import re
import sys


CASOS = [
    ("demissao_simples", "Mandei a funcionaria embora e paguei tudo, mas nao sei se tem risco."),
    ("justa_causa", "Demitimos por justa causa por abandono de emprego, sem documentos assinados."),
    ("estabilidade_gestante", "Dispensamos colaboradora gestante sem comunicacao adequada sobre gravidez."),
    ("horas_extras", "Equipe faz horas extras frequentes sem controle de ponto adequado."),
    ("fgts_atrasado", "FGTS ficou em atraso por 8 meses em parte do quadro."),
    ("assedio", "Funcionaria relata assedio moral com mensagens e testemunhas."),
    ("acordo_extrajudicial", "Queremos acordo extrajudicial para encerrar risco com ex-empregado, sem valores definidos."),
    ("pedido_demissao", "Funcionario pediu demissao e assinou quitacao de todas as verbas."),
    ("terceirizacao", "Terceirizado recebe ordens diretas do gestor e cumpre horario interno."),
    ("multiplos_riscos", "Demissao sem comprovante completo, horas extras sem ponto e FGTS irregular."),
]


def _tem_r_financiamento_sem_base(texto_impacto: str, texto_usuario: str) -> bool:
    """Heurística: valor em R$ na saída sem salário/tempo/pedido explícitos no relato."""
    t = (texto_usuario or "").lower()
    tem_base = any(
        x in t
        for x in (
            "salario",
            "salário",
            "r$",
            "valor da causa",
            "pedido",
            "meses",
            "anos",
            "tempo de casa",
        )
    )
    if "R$" in (texto_impacto or "") and not tem_base:
        return True
    return False


def _score_dimensoes(analise: dict, parecer: dict, texto: str) -> dict:
    dados = analise["dados"]
    resultado = analise["resultado"]
    perguntas = resultado.get("perguntas_objetivas") or dados.get("perguntas") or []
    pedido = str(parecer.get("pedido_complemento") or "").strip()

    impacto_bloco = str(
        (parecer.get("decisao_empresarial") or {}).get("impacto_financeiro_provavel")
        or parecer.get("impacto_financeiro_texto")
        or ""
    )
    inv_fin = _tem_r_financiamento_sem_base(impacto_bloco, texto)

    # Naturalidade: ausência de templates genéricos repetidos (proxy curto)
    diag = str(parecer.get("diagnostico") or "")
    naturalidade = 7
    if len(diag) > 40 and "Foram identificados indícios" not in diag:
        naturalidade = 8
    if len(perguntas) >= 2:
        naturalidade = min(10, naturalidade + 1)

    # Perguntas
    q_score = min(10, 5 + len(perguntas))

    # Risco coerente (proxy): nível declarado vs pontuação
    risco = str(parecer.get("risco") or resultado.get("risco") or "").upper()
    score = int(analise.get("score") or 0)
    coerencia = 7
    if risco == "ALTO" and score >= 65:
        coerencia = 9
    elif risco == "MÉDIO" and 40 <= score <= 75:
        coerencia = 8
    elif risco == "BAIXO" and score <= 45:
        coerencia = 9
    elif risco == "INCONCLUSIVO":
        coerencia = 8 if score <= 50 else 6

    zero_inv = 10 if not inv_fin else 3

    # Qualidade jurídica (proxy): fundamentação não vazia + racional
    fund = str(parecer.get("fundamentacao") or "")
    racional = str(resultado.get("racional_decisao") or "")
    q_jur = 6
    if len(fund) > 80:
        q_jur += 2
    if len(racional) > 40:
        q_jur += 1
    q_jur = min(10, q_jur)

    # Utilidade empresarial
    util = 7
    if pedido or perguntas:
        util = 8
    if parecer.get("proxima_acao") or parecer.get("recomendacao"):
        util = min(10, util + 1)

    # Confiança transmitida (proxy: inconclusivo pede dados vs afirma forte sem dados)
    conf = 7
    if risco == "INCONCLUSIVO" and perguntas:
        conf = 9
    if inv_fin:
        conf = 4
    if risco == "ALTO" and len(texto) < 80:
        conf = min(conf, 6)

    return {
        "qualidade_juridica": round(q_jur, 1),
        "naturalidade": round(naturalidade, 1),
        "perguntas_complementares": round(q_score, 1),
        "risco_coerente": round(coerencia, 1),
        "zero_invencao_financeira": round(zero_inv, 1),
        "utilidade_empresarial": round(util, 1),
        "confianca_transmitida": round(conf, 1),
        "_meta_inv_financeira_flag": inv_fin,
        "_meta_num_perguntas": len(perguntas),
    }


def main():
    from application.analise_use_cases import executar_analise_e_score
    from ia_consultor import gerar_parecer_juridico

    rows = []
    for nome, texto in CASOS:
        analise = executar_analise_e_score(texto)
        parecer = gerar_parecer_juridico(
            contexto=texto,
            dados=analise["dados"],
            resultado=analise["resultado"],
            score=analise["score"],
            probabilidade=analise["probabilidade"],
        )
        dims = _score_dimensoes(analise, parecer, texto)
        rows.append(
            {
                "caso": nome,
                "risco": parecer.get("risco"),
                "score": analise["score"],
                "dims": dims,
                "perguntas_amostra": (analise["resultado"].get("perguntas_objetivas") or [])[:3],
            }
        )

    keys = [
        "qualidade_juridica",
        "naturalidade",
        "perguntas_complementares",
        "risco_coerente",
        "zero_invencao_financeira",
        "utilidade_empresarial",
        "confianca_transmitida",
    ]
    avg = {k: round(sum(r["dims"][k] for r in rows) / len(rows), 2) for k in keys}

    out = {"avg": avg, "casos": rows}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
