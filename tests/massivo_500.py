"""
Bateria massiva 500 cenários — somente medição (não altera código de produção).

Execução:
  python tests/massivo_500.py

Motor: DP_IA_MOTOR (default: legacy, rápido). Use openai para teste completo com API.

Saídas na raiz do repo:
  massivo_500_report.txt
  massivo_500_detail.jsonl
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

_TERMOS_ZERO = [
    "sem risco",
    "não há risco",
    "nao ha risco",
    "risco zero",
    "totalmente seguro",
]

REPORT_PATH = os.path.join(ROOT, "massivo_500_report.txt")
DETAIL_PATH = os.path.join(ROOT, "massivo_500_detail.jsonl")


def _entrada_critica(texto: str) -> bool:
    """Espelha a trava: se mesmo partindo de BAIXO vira ALTO, há gatilho crítico."""
    return _aplicar_trava_risco_final(texto, "BAIXO") == "ALTO"


def _payload_texto_completo(payload: dict[str, Any]) -> str:
    buf: list[str] = []
    for k, v in payload.items():
        if k == "parecer_executivo" and isinstance(v, dict):
            buf.extend(str(x) for x in v.values())
        elif isinstance(v, (str, int, float)):
            buf.append(str(v))
        elif isinstance(v, list):
            buf.extend(str(x) for x in v)
    return " ".join(buf)


def _tem_risco_zero(payload: dict[str, Any]) -> bool:
    blob = _normalizar_texto(_payload_texto_completo(payload))
    return any(_normalizar_texto(t) in blob for t in _TERMOS_ZERO)


def _fora_contexto(texto: str, payload: dict[str, Any]) -> bool:
    tema = _extrair_tema_principal(texto)
    if tema is None:
        return False
    resposta = _texto_resposta_para_validacao(payload)
    return not _validar_aderencia_resposta(tema, resposta)


def _acao_clara(payload: dict[str, Any]) -> bool:
    pe = payload.get("parecer_executivo") if isinstance(payload.get("parecer_executivo"), dict) else {}
    pa = str(pe.get("proxima_acao_recomendada") or "").strip()
    ped = str(payload.get("pedido_complemento") or "").strip()
    rac = str(payload.get("racional_risco") or "").strip()
    if len(pa) >= 28:
        return True
    if len(ped) >= 45 and any(c.isdigit() for c in ped[:12]):
        return True
    if len(rac) >= 80 and "?" in (ped + rac):
        return True
    return False


def _subestimacao(texto: str, payload: dict[str, Any]) -> bool:
    if not _entrada_critica(texto):
        return False
    r = str(payload.get("risco") or "").upper().replace("MEDIO", "MÉDIO")
    return r != "ALTO"


def _classificacao_adequada(texto: str, payload: dict[str, Any]) -> bool:
    r = str(payload.get("risco") or "").upper().replace("MEDIO", "MÉDIO")
    p = int(payload.get("pontuacao") or 0)
    if _entrada_critica(texto) and r != "ALTO":
        return False
    if r == "ALTO" and p < 45:
        return False
    if r == "BAIXO" and p > 72:
        return False
    return True


def _gerar_500() -> list[dict[str, Any]]:
    rnd = random.Random(42)
    casos: list[dict[str, Any]] = []

    def pick(*opts: str) -> str:
        return rnd.choice(opts)

    def typo(s: str) -> str:
        if rnd.random() < 0.12:
            return s.replace("a", "q", 1) if "a" in s else s
        if rnd.random() < 0.08:
            return s + " msm"
        return s

    # —— 100 demissão / rescisão ——
    dem_templates = [
        "to pra {d} o cara do estoque {extra}",
        "{d} sem conversa fiada pq sumiu 3x",
        "rescisao ta paga? {extra}",
        "mandei embora e assinei trct {extra}",
        "empresa pequena {d} fulano sem adv",
        "tenho medo de processo se {d}",
        "func gestante posso {d} hj?",
        "justa causa tem prova? vou {d}",
        "pediram pra sair sozinho rescisao como fica",
        "dispensa coletiva rolou {extra}",
    ]
    extras_dem = [
        "",
        "acho q ta certo",
        "nao sei se fiz certo",
        "talvez eu tenha errado",
        "ta estranho",
    ]
    demissoes = ["demitir", "dispensar", "mandar embora", "largar", "tirar"]
    for i in range(100):
        tpl = typo(dem_templates[i % len(dem_templates)].format(d=pick(*demissoes), extra=pick(*extras_dem)))
        casos.append({"id": len(casos) + 1, "categoria": "demissao_rescisao", "texto": tpl})

    # —— 80 horas extras ——
    he_var = [
        "hora extra nao paga direito",
        "colaborador vira 19h e eu nao registro",
        "banco de horas ta furado",
        "ponto batido errado ha meses",
        "extra fds sem autorizacao escrita",
        "hora extra por fora no pix",
        "jornada estourada todo dia",
        "sem controle de jornada msm",
        "adicional noturno rolando?",
        "fechamento de ponto manual no excel",
    ]
    for i in range(80):
        base = he_var[i % len(he_var)]
        suf = pick("", " acho", " talvez", " n sei", " q droga")
        casos.append({"id": len(casos) + 1, "categoria": "horas_extras", "texto": typo(base + suf)})

    # —— 60 FGTS / pagamento ——
    fg_var = [
        "fgts atrasado uns meses",
        "nao recolhi fgts direito",
        "salario por fora em envelope",
        "caixa informal rodando",
        "informal demais aqui na loja",
        "recolhimento fgts falho desde ano passado",
        "pagamento misturado mei",
        "verbas rescisorias parcial",
        "desconto errado no holerite",
        "empresa pequena fgts sempre foi assim",
    ]
    for i in range(60):
        casos.append({"id": len(casos) + 1, "categoria": "fgts_pagamento", "texto": typo(fg_var[i % len(fg_var)] + pick("", "?", " sla"))})

    # —— 60 PJ / vínculo ——
    pj_var = [
        "pj aqui todo dia fixo igual empregado",
        "prestador mas recebe ordem minha direta",
        "contrato pj mas horario fechado",
        "pejotizado galera da producao",
        "pj sem nota direito",
        "home office pj mas tem reuniao todo dia",
        "pj exclusivo so pra mim",
        "valor fixo mensal pj parece salario",
        "pj veste uniforme e usa cracha",
        "subordinacao total dizendo q e pj",
    ]
    for i in range(60):
        casos.append({"id": len(casos) + 1, "categoria": "pj_vinculo", "texto": typo(pj_var[i % len(pj_var)])})

    # —— 50 assédio / conflito ——
    as_var = [
        "clima pesado setor mulher chorando",
        "chefe humilhou na frente de todo mundo",
        "assedio moral rolendo?",
        "funcionario falou que vai me processar",
        "briga feia reuniao gritaria",
        "ameaca de advogado por whats",
        "ambiente toxico lideranca",
        "comentario pesado repetido",
        "isolamento do funcionario depois de reclamacao",
        "whatsapp da empresa com mensagem feia",
    ]
    for i in range(50):
        casos.append({"id": len(casos) + 1, "categoria": "assedio_conflito", "texto": typo(as_var[i % len(as_var)] + pick("", " ajuda", " urgente"))})

    # —— 50 acidente ——
    ac_var = [
        "teve acidente leve aqui na empresa",
        "queda no deposito funcionario machucou",
        "lesao na mao maquina antiga",
        "corte leve mas sangrou",
        "escorregou no oleo",
        "cat nao comunicamos direito",
        "afastamento medico curto",
        "epi sem usar direito",
        "maquina sem protecao",
        "queda de escada interna",
    ]
    for i in range(50):
        casos.append({"id": len(casos) + 1, "categoria": "acidente", "texto": typo(ac_var[i % len(ac_var)])})

    # —— 50 ambíguos ——
    amb_var = [
        "acho que ta tudo certo mas nao sei",
        "talvez tenha problema sla",
        "nao sei se preciso advogado",
        "empresa pequena essas coisas",
        "funcionario estranho ultimamente",
        "to perdido com RH",
        "sera que da ruim",
        "medo de fiscalizacao mas sem motivo claro",
        "relato confuso varios fatos misturados",
        "nao tenho certeza do que fazer hj",
    ]
    for i in range(50):
        casos.append({"id": len(casos) + 1, "categoria": "ambiguo", "texto": typo(amb_var[i % len(amb_var)])})

    # —— 50 multi risco ——
    multi_var = [
        "pj fixo todo dia + hora extra sem ponto",
        "fgts atrasado e demissao sem trct assinado",
        "gestante e pediram pra sair",
        "acidente leve e depois demissao",
        "por fora no caixa e pj na carta",
        "advogado ja mandou msg e fgts errado",
        "justa causa sem risco posso?",
        "assedio e depois dispensa",
        "hora extra + rescisao briga grossa",
        "informal demais e medo processo",
    ]
    for i in range(50):
        casos.append({"id": len(casos) + 1, "categoria": "multi_risco", "texto": typo(multi_var[i % len(multi_var)])})

    assert len(casos) == 500
    return casos


def main() -> None:
    motor = os.environ.get("DP_IA_MOTOR", "legacy").strip().lower()
    if motor not in {"legacy", "openai"}:
        motor = "legacy"

    casos = _gerar_500()
    stats = Counter()
    risk_dist = Counter()
    falhas: list[dict[str, Any]] = []
    linhas_jsonl: list[str] = []

    for c in casos:
        texto = c["texto"]
        payload = executar_fluxo_consulta(texto, motor=motor)

        fc = _fora_contexto(texto, payload)
        rz = _tem_risco_zero(payload)
        sub = _subestimacao(texto, payload)
        ac = _acao_clara(payload)
        ok_cls = _classificacao_adequada(texto, payload)

        risco = str(payload.get("risco") or "INCONCLUSIVO").upper().replace("MEDIO", "MÉDIO")
        risk_dist[risco] += 1

        stats["fora_contexto_sim"] += int(fc)
        stats["risco_zero_sim"] += int(rz)
        stats["subestimacao_sim"] += int(sub)
        stats["acao_clara_sim"] += int(ac)
        stats["classificacao_ok"] += int(ok_cls)

        correto = not fc and not rz and not sub and ac and ok_cls
        stats["corretos"] += int(correto)

        row = {
            **c,
            "motor": motor,
            "risco": payload.get("risco"),
            "fora_contexto": fc,
            "risco_zero": rz,
            "subestimacao": sub,
            "acao_clara": ac,
            "classificacao_ok": ok_cls,
            "correto": correto,
        }
        linhas_jsonl.append(json.dumps(row, ensure_ascii=False) + "\n")

        if not correto:
            falhas.append(row)

    n = 500
    pct = lambda x: 100.0 * x / n

    fora_pct = pct(stats["fora_contexto_sim"])
    rz_pct = pct(stats["risco_zero_sim"])
    sub_pct = pct(stats["subestimacao_sim"])
    ac_pct = pct(stats["acao_clara_sim"])
    corr_pct = pct(stats["corretos"])

    # Critério do usuário
    aprovado = (
        stats["fora_contexto_sim"] == 0
        and stats["risco_zero_sim"] == 0
        and sub_pct < 2.0
        and ac_pct > 95.0
    )

    lines = []
    lines.append("RELATÓRIO MASSIVO 500 — M&P Consultoria Trabalhista")
    lines.append(f"Motor: {motor}")
    lines.append("")
    lines.append("=== MÉTRICAS ===")
    lines.append(f"Taxa respostas 'corretas' (todas as 5 checagens): {corr_pct:.2f}%")
    lines.append(f"% fora de contexto: {fora_pct:.2f}%")
    lines.append(f"% termos tipo 'risco zero': {rz_pct:.2f}%")
    lines.append(f"% subestimação (entrada crítica sem ALTO): {sub_pct:.2f}%")
    lines.append(f"% com ação clara (heurística): {ac_pct:.2f}%")
    lines.append("")
    lines.append("Distribuição risco (campo payload.risco):")
    for k in sorted(risk_dist.keys()):
        lines.append(f"  {k}: {risk_dist[k]} ({pct(risk_dist[k]):.1f}%)")
    lines.append("")
    lines.append("=== CRITÉRIO DE APROVAÇÃO ===")
    lines.append(f"fora de contexto = 0% -> {'OK' if stats['fora_contexto_sim']==0 else 'FALHOU'}")
    lines.append(f"risco zero = 0% -> {'OK' if stats['risco_zero_sim']==0 else 'FALHOU'}")
    lines.append(f"subestimação < 2% -> {'OK' if sub_pct < 2 else 'FALHOU'} ({sub_pct:.2f}%)")
    lines.append(f"ação clara > 95% -> {'OK' if ac_pct > 95 else 'FALHOU'} ({ac_pct:.2f}%)")
    lines.append("")
    lines.append(f"VEREDITO: {'APROVADO' if aprovado else 'NÃO APROVADO'}")
    lines.append("")
    lines.append("=== TOP FALHAS (até 10 exemplos) ===")
    for i, f in enumerate(falhas[:10], 1):
        lines.append(f"{i}. id={f['id']} cat={f['categoria']} texto={f['texto'][:90]}...")
        lines.append(
            f"   risco={f.get('risco')} "
            f"fora_ctx={f['fora_contexto']} rz={f['risco_zero']} sub={f['subestimacao']} "
            f"acao={f['acao_clara']} cls={f['classificacao_ok']}"
        )

    report = "\n".join(lines) + "\n"
    with io.open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    with io.open(DETAIL_PATH, "w", encoding="utf-8") as f:
        f.writelines(linhas_jsonl)

    print(report)


if __name__ == "__main__":
    if os.path.isfile(DETAIL_PATH):
        os.remove(DETAIL_PATH)
    main()
