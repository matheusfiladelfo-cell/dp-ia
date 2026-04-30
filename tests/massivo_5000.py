"""
Bateria massiva 5000 cenários (simulação cliente real) — somente medição.

Execução:
  python tests/massivo_5000.py

Motor: DP_IA_MOTOR (default: legacy, rápido). Use openai para rodada online.

Saídas na raiz do repo:
  massivo_5000_report.txt
  massivo_5000_detail.jsonl
"""
from __future__ import annotations

import io
import json
import os
import random
import sys
from collections import Counter
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", "sk-offline-massivo"))

from fluxo_consulta import (  # noqa: E402
    _aplicar_trava_risco_final,
    _extrair_tema_principal,
    _normalizar_texto,
    _texto_resposta_para_validacao,
    _validar_aderencia_resposta,
    executar_fluxo_consulta,
)

REPORT_PATH = os.path.join(ROOT, "massivo_5000_report.txt")
DETAIL_PATH = os.path.join(ROOT, "massivo_5000_detail.jsonl")
TERMOS_ZERO = ["sem risco", "não há risco", "nao ha risco", "risco zero", "totalmente seguro"]


def _payload_texto(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for k, v in payload.items():
        if k == "parecer_executivo" and isinstance(v, dict):
            parts.extend(str(x) for x in v.values())
        elif isinstance(v, (str, int, float)):
            parts.append(str(v))
        elif isinstance(v, list):
            parts.extend(str(x) for x in v)
    return " ".join(parts)


def _tem_risco_zero(payload: dict[str, Any]) -> bool:
    txt = _normalizar_texto(_payload_texto(payload))
    return any(_normalizar_texto(t) in txt for t in TERMOS_ZERO)


def _fora_contexto(texto: str, payload: dict[str, Any]) -> bool:
    tema = _extrair_tema_principal(texto)
    if not tema:
        return False
    return not _validar_aderencia_resposta(tema, _texto_resposta_para_validacao(payload))


def _subestimou(texto: str, payload: dict[str, Any]) -> bool:
    if _aplicar_trava_risco_final(texto, "BAIXO") != "ALTO":
        return False
    return str(payload.get("risco") or "").upper().replace("MEDIO", "MÉDIO") != "ALTO"


def _acao_clara(payload: dict[str, Any]) -> bool:
    pe = payload.get("parecer_executivo") if isinstance(payload.get("parecer_executivo"), dict) else {}
    pa = str(pe.get("proxima_acao_recomendada") or "").strip()
    ped = str(payload.get("pedido_complemento") or "").strip()
    return len(pa) >= 24 or len(ped) >= 40


def _score_cliente(texto: str, payload: dict[str, Any]) -> dict[str, int]:
    resposta = _normalizar_texto(_payload_texto(payload))
    risco = str(payload.get("risco") or "").upper().replace("MEDIO", "MÉDIO")
    critico = _aplicar_trava_risco_final(texto, "BAIXO") == "ALTO"

    entendimento = 2 if not _fora_contexto(texto, payload) else 1
    confianca = 2 if risco in {"MÉDIO", "ALTO", "INCONCLUSIVO"} else 1
    clareza = 2 if len(resposta) >= 140 else 1
    ajuda = 2 if _acao_clara(payload) else 1
    coerencia = 2 if (not critico or risco == "ALTO") else 0
    return {
        "entendimento": entendimento,
        "confianca": confianca,
        "clareza": clareza,
        "ajuda": ajuda,
        "coerencia": coerencia,
    }


def _gerar_5000() -> list[dict[str, Any]]:
    rnd = random.Random(420)
    casos: list[dict[str, Any]] = []

    def pick(arr: list[str]) -> str:
        return arr[rnd.randrange(len(arr))]

    def typo(s: str) -> str:
        if rnd.random() < 0.20:
            s = s.replace("que", "q")
        if rnd.random() < 0.14:
            s = s.replace("não", "nao").replace("ção", "cao")
        if rnd.random() < 0.10:
            s = s + pick([" msm", " urgente", " to perdido", " ajuda"])
        return s

    grupos: list[tuple[str, int, list[str]]] = [
        ("demissao_rescisao", 800, [
            "rescisao ta certa?", "mandei embora e agora?", "dispensa sem trct da ruim?",
            "saiu brigado preciso pagar oq", "desligamento sem aviso complica?",
            "termino contrato e verbas como fica", "posso demitir hoje sem dor de cabeca?",
        ]),
        ("horas_extras", 700, [
            "hora extra nao paguei tudo", "ponto errado faz meses", "jornada estourada todo dia",
            "banco de horas baguncado", "extra no sabado sem registro",
        ]),
        ("fgts_pagamento", 600, [
            "fgts atrasou uns meses", "paguei por fora da problema", "caixa informal aqui",
            "verbas rescisorias parcial", "salario misturado sem holerite",
        ]),
        ("pj_vinculo", 600, [
            "pj todo dia horario fixo", "prestador recebe ordem direta", "contrato pj mas parece clt",
            "valor fixo mensal tipo salario", "pj exclusivo pra empresa",
        ]),
        ("assedio_conflito", 500, [
            "chefe humilhou equipe", "funcionario falou advogado", "ambiente toxico",
            "briga e gritaria setor", "ameaca de processo no whats",
        ]),
        ("acidente", 500, [
            "teve acidente aqui", "queda no deposito", "machucou a mao na maquina",
            "lesao e afastamento curto", "cat nao saiu direito",
        ]),
        ("justa_causa", 400, [
            "justa causa sem prova pode?", "quero justa causa sem risco",
            "sumiu 2 dias justa causa?", "pegou atestado estranho posso cortar?",
        ]),
        ("acordos", 400, [
            "fiz acordo de boca vale?", "acordo pra parcelar verbas pode",
            "acordo sem sindicato da problema?", "quero encerrar contrato por acordo",
        ]),
        ("ambiguo", 300, [
            "acho q ta errado talvez", "nao sei o que fazer", "to confuso com esse caso",
            "sera q da processo?", "talvez nao paguei certo",
        ]),
        ("multi_risco", 300, [
            "pj fixo + fgts atrasado", "acidente e depois demissao", "hora extra + por fora",
            "justa causa sem prova e advogado", "assedio e acordo mal feito",
        ]),
    ]

    for categoria, qtd, base in grupos:
        for _ in range(qtd):
            t = typo(pick(base))
            casos.append({"id": len(casos) + 1, "categoria": categoria, "texto": t})
    if len(casos) > 5000:
        casos = rnd.sample(casos, 5000)
        for i, c in enumerate(casos, 1):
            c["id"] = i
    assert len(casos) == 5000
    return casos


def main() -> None:
    motor = os.environ.get("DP_IA_MOTOR", "legacy").strip().lower()
    if motor not in {"legacy", "openai"}:
        motor = "legacy"

    casos = _gerar_5000()
    n = len(casos)
    stats = Counter()
    notas = Counter()
    riscos = Counter()
    linhas: list[str] = []
    ruins: list[dict[str, Any]] = []
    otimas: list[dict[str, Any]] = []

    for c in casos:
        texto = c["texto"]
        payload = executar_fluxo_consulta(texto, motor=motor)

        fora = _fora_contexto(texto, payload)
        rz = _tem_risco_zero(payload)
        sub = _subestimou(texto, payload)
        acao = _acao_clara(payload)

        cliente = _score_cliente(texto, payload)
        nota = sum(cliente.values())

        risco = str(payload.get("risco") or "INCONCLUSIVO").upper().replace("MEDIO", "MÉDIO")
        riscos[risco] += 1
        notas[nota] += 1

        stats["fora"] += int(fora)
        stats["rz"] += int(rz)
        stats["sub"] += int(sub)
        stats["acao"] += int(acao)
        stats["nota_total"] += nota
        stats["acima8"] += int(nota >= 8)

        row = {
            **c,
            "motor": motor,
            "risco": risco,
            "nota": nota,
            "cliente": cliente,
            "fora_contexto": fora,
            "risco_zero": rz,
            "subestimou": sub,
            "acao_clara": acao,
            "proxima_acao": (
                payload.get("parecer_executivo", {}).get("proxima_acao_recomendada", "")
                if isinstance(payload.get("parecer_executivo"), dict) else ""
            ),
        }
        linhas.append(json.dumps(row, ensure_ascii=False) + "\n")

        if nota <= 6 or fora or rz or sub or not acao:
            ruins.append(row)
        if nota >= 9 and not fora and not rz and not sub and acao:
            otimas.append(row)

    pct = lambda x: 100.0 * x / n
    media = stats["nota_total"] / n
    fora_pct = pct(stats["fora"])
    sub_pct = pct(stats["sub"])
    acao_pct = pct(stats["acao"])
    acima8_pct = pct(stats["acima8"])

    if media >= 8.5 and fora_pct <= 0.2 and sub_pct < 1.0:
        veredito = "PRONTO PARA ESCALA"
    elif media >= 8.0 and sub_pct < 3.0:
        veredito = "AJUSTE LEVE"
    else:
        veredito = "NÃO LIBERAR"

    out: list[str] = []
    out.append("RELATORIO MASSIVO 5000 - M&P Consultoria Trabalhista")
    out.append(f"Motor: {motor}")
    out.append("")
    out.append("1. NOTA MEDIA GERAL")
    out.append(f"Media: {media:.2f}/10")
    out.append("")
    out.append("2. DISTRIBUICAO DAS NOTAS (0-10)")
    for i in range(11):
        out.append(f"  nota_{i}: {notas[i]} ({pct(notas[i]):.2f}%)")
    out.append("")
    out.append("3. METRICAS TECNICAS")
    out.append(f"% fora de contexto: {fora_pct:.2f}%")
    out.append(f"% subestimacao: {sub_pct:.2f}%")
    out.append(f"% acao clara: {acao_pct:.2f}%")
    out.append(f"% respostas >=8: {acima8_pct:.2f}%")
    out.append("")
    out.append("Distribuicao de risco:")
    for k in sorted(riscos.keys()):
        out.append(f"  {k}: {riscos[k]} ({pct(riscos[k]):.2f}%)")
    out.append("")
    out.append("4. PRINCIPAIS FALHAS (TOP 10)")
    for i, r in enumerate(ruins[:10], 1):
        out.append(
            f"{i}. id={r['id']} cat={r['categoria']} nota={r['nota']} "
            f"fora={r['fora_contexto']} rz={r['risco_zero']} sub={r['subestimou']} acao={r['acao_clara']} texto={r['texto']}"
        )
    out.append("")
    out.append("5. EXEMPLOS DE RESPOSTAS RUINS (TOP 5)")
    for i, r in enumerate(ruins[:5], 1):
        out.append(f"{i}. texto={r['texto']} | nota={r['nota']} | risco={r['risco']}")
    out.append("")
    out.append("6. EXEMPLOS DE RESPOSTAS EXCELENTES (TOP 5)")
    for i, r in enumerate(otimas[:5], 1):
        out.append(f"{i}. texto={r['texto']} | nota={r['nota']} | risco={r['risco']}")
    out.append("")
    out.append(f"VEREDITO FINAL: {veredito}")
    out.append("")

    with io.open(DETAIL_PATH, "w", encoding="utf-8") as f:
        f.writelines(linhas)
    with io.open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
