"""
ETAPA TESTE GUERRA 100 — bateria de 100 casos trabalhistas (somente leitura do motor).
Não altera app/UI; exporta resultado_100.txt e resultado_100.csv na raiz do repositório.

Regra de qualidade: expectativas e entradas refletem o mundo real; falhas devem levar a
correção do motor, não a “amaciar” o teste.

Execução: python tests/teste_guerra_100.py
Opcional: RUN_LLM_EVAL=1 para veredito via LLM (requer chaves/API conforme projeto).
"""
from __future__ import annotations

import csv
import os
import sys

# Importação do ia_client exige variável definida; offline a IA falha com graça e usa regras.
os.environ.setdefault("OPENAI_API_KEY", "sk-offline-test-guerra100")
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_TXT = os.path.join(ROOT, "resultado_100.txt")
OUT_CSV = os.path.join(ROOT, "resultado_100.csv")

sys.path.insert(0, ROOT)

import analisador_caso  # noqa: E402
import ia_pipeline  # noqa: E402

# Bateria determinística: sem round-trip de IA (regras + classificador fallback).
# Use GUERRA100_FAST_IA=0 para enriquecer com analisar_texto_ia (requer API válida).
if os.getenv("GUERRA100_FAST_IA", "1") == "1":

    def _ia_offline(_texto: str) -> dict:
        return {"erro": "ia_offline_bateria"}

    analisador_caso.analisar_texto_ia = _ia_offline
    ia_pipeline.analisar_texto_ia = _ia_offline

from analisador_caso import analisar_texto_usuario  # noqa: E402
from ia_consultor import gerar_parecer_juridico  # noqa: E402
from motor_consultor import analisar_caso  # noqa: E402
from score_engine import calcular_score, tipo_efetivo_para_score  # noqa: E402

RISK_RANK = {
    "BAIXO": 1,
    "MÉDIO": 2,
    "MEDIO": 2,
    "MÉDIO-ALTO": 3,
    "MEDIO-ALTO": 3,
    "ALTO": 4,
    "INCONCLUSIVO": 0,
}


def _rank(risk: str | None) -> int:
    return RISK_RANK.get(str(risk or "").upper(), 0)


def _extract_hard_rule(resultado: dict, score_data: dict) -> str:
    alertas = resultado.get("alertas") if isinstance(resultado.get("alertas"), list) else []
    for alerta in alertas:
        tipo = str(alerta.get("tipo", ""))
        if "HARD RULE" in tipo.upper():
            return tipo
    motivos = score_data.get("motivos") if isinstance(score_data.get("motivos"), list) else []
    for motivo in reversed(motivos):
        fator = str(motivo.get("fator", ""))
        if "Hard rule" in fator:
            return fator
    return "-"


def _veredito_resumo(parecer: dict) -> str:
    ve = parecer.get("veredito_estrategico") or {}
    linha = ve.get("resumo_executivo_1_linha") or ""
    return str(linha).replace("\n", " ").strip() or "—"


def _is_case_ok(case: dict, nivel: str, score: int) -> tuple[bool, str]:
    score = int(score or 0)
    risco_rank = _rank(nivel)

    if "expected_min_risk" in case:
        need = _rank(case["expected_min_risk"])
        if risco_rank < need:
            return False, f"nivel {nivel!r} abaixo do mínimo {case['expected_min_risk']!r}"
    if "expected_min_score" in case:
        if score < int(case["expected_min_score"]):
            return False, f"score {score} < mínimo {case['expected_min_score']}"
    if "expected_max_risk" in case:
        cap = _rank(case["expected_max_risk"])
        if risco_rank > cap:
            return False, f"nivel {nivel!r} acima do máximo {case['expected_max_risk']!r}"
    if "expected_max_score" in case:
        if score > int(case["expected_max_score"]):
            return False, f"score {score} > máximo {case['expected_max_score']}"
    return True, ""


def _run_pipeline(entrada: str):
    dados = analisar_texto_usuario(entrada)
    resultado = dict(analisar_caso(dados.get("tipo_caso"), dados))

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
            "tempo_empresa_meses": dados.get("tempo_empresa_meses") or 0,
        }
    )
    score = int(score_data.get("score", 0))
    prob = int(score_data.get("probabilidade_condenacao", 0))
    nivel = str(score_data.get("nivel") or resultado.get("risco") or "N/A")
    hard = _extract_hard_rule(resultado, score_data)
    return dados, resultado, score_data, nivel, score, prob, hard


def _build_cases() -> list[dict]:
    """100 casos: 20 básicos, 25 médio, 25 alto, 20 litígio, 10 confusos."""

    def B(entrada: str, tag: str, **kw):
        return {"entrada": entrada, "categoria": "basico", "tag": tag, **kw}

    def M(entrada: str, tag: str, **kw):
        return {"entrada": entrada, "categoria": "medio", "tag": tag, **kw}

    def A(entrada: str, tag: str, **kw):
        return {"entrada": entrada, "categoria": "alto", "tag": tag, **kw}

    def L(entrada: str, tag: str, **kw):
        return {"entrada": entrada, "categoria": "litigio", "tag": tag, **kw}

    def C(entrada: str, tag: str, **kw):
        return {"entrada": entrada, "categoria": "confuso", "tag": tag, **kw}

    basico = [
        B(
            "ela pediu a conta e eu paguei tudo certinho com recibos assinados",
            "pedido_quitado",
            expected_max_risk="BAIXO",
            expected_max_score=40,
        ),
        B(
            "pedido de demissao com quitacao total e todos os documentos entregues",
            "pedido_quitado",
            expected_max_risk="BAIXO",
            expected_max_score=40,
        ),
        B(
            "funcionario pediu para sair da empresa recebeu todas as verbas dentro do prazo legal",
            "pedido_limpo",
            expected_max_risk="MÉDIO",
            expected_max_score=55,
        ),
        B(
            "consulta preventiva posso mudar escala sem acordo coletivo ha risco",
            "consulta_preventiva",
            expected_max_risk="MÉDIO",
            expected_max_score=50,
        ),
        B(
            "duvida trabalhista simples sobre ferias proporcionais como calcular",
            "consulta_preventiva",
            expected_max_risk="MÉDIO",
            expected_max_score=55,
        ),
        B(
            "demissao sem justa causa e eu paguei rescisao completa em 5 dias documentado",
            "rescisao_em_dia",
            expected_max_risk="MÉDIO",
            expected_max_score=55,
        ),
        B(
            "empresa quer saber se vale registrar horario variavel em carta",
            "consulta_preventiva",
            expected_max_risk="MÉDIO",
            expected_max_score=52,
        ),
        B(
            "colaborador em experiencia de 40 dias pediu demissao sem pendencias",
            "experiencia_demissao",
            expected_max_risk="MÉDIO",
            expected_max_score=55,
        ),
        B(
            "rescisao indireta nem pensar foi erro digitacao foi rescisao normal paga",
            "baixo_risco_relato",
            expected_max_risk="MÉDIO",
            expected_max_score=58,
        ),
        B(
            "pergunta se adicional noturno incide sobre hora extra rotina admin",
            "consulta_preventiva",
            expected_max_risk="MÉDIO",
            expected_max_score=55,
        ),
        B(
            "apos aviso previo trabalhado funcionario recebeu saldo de salario certo",
            "rotina_boa",
            expected_max_risk="MÉDIO",
            expected_max_score=55,
        ),
        B(
            "empresa tem ponto eletronico regular e folgas da clt cumpridas",
            "rotina_boa",
            expected_max_risk="MÉDIO",
            expected_max_score=52,
        ),
        B(
            "gestor quer saber limite de horas extras mensais para evitar passivo",
            "consulta_preventiva",
            expected_max_risk="MÉDIO",
            expected_max_score=52,
        ),
        B(
            "contrato experiencia encerrado antes do prazo com pagamento das verbas devidas",
            "experiencia_ok",
            expected_max_risk="MÉDIO",
            expected_max_score=55,
        ),
        B(
            "home office voluntario sem reducao salarial registrado em termo",
            "consulta_preventiva",
            expected_max_risk="MÉDIO",
            expected_max_score=55,
        ),
        B(
            "funcionario pediu para sair e devolveu equipamentos sem multa extra",
            "pedido_simples",
            expected_max_risk="MÉDIO",
            expected_max_score=55,
        ),
        B(
            "pergunta sobre intervalo intrajornada de 1 hora para jornada 8 horas",
            "consulta_preventiva",
            expected_max_risk="MÉDIO",
            expected_max_score=52,
        ),
        B(
            "empresa paga 13 salario em duas parcelas corretas todo ano",
            "rotina_boa",
            expected_max_risk="MÉDIO",
            expected_max_score=50,
        ),
        B(
            "sem incidentes trabalhistas no ultimo ano apenas duvida de politica interna",
            "consulta_preventiva",
            expected_max_risk="MÉDIO",
            expected_max_score=48,
        ),
        B(
            "acordo de metas sem desconto salarial duvida de legalidade basica",
            "consulta_preventiva",
            expected_max_risk="MÉDIO",
            expected_max_score=55,
        ),
    ]

    medio = [
        M(
            "banco de horas sem assinatura do sindicato ha 8 meses",
            "banco_horas",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "férias vencidas não pagas funcionario cobra dois periodos",
            "ferias",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "rescisão atrasou 15 dias para pagar verbas rescisorias",
            "rescisao_atrasada",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "paguei por fora varios meses parte do salario em dinheiro",
            "por_fora",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "salario pago picado todo mes em tres transferencias recorrente",
            "salario_picado",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "trabalhava domingo sem folga semanal há meses",
            "domingo",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "funcionario entrou na justiça mas nao mostrei petição inicial ainda",
            "acao_sem_peticao",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "sem fgts 8 meses e funcionario descobriu extrato",
            "fgts",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "hora extra habitual todo dia sem controle de ponto eletronico",
            "he_habitual",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "gerente humilhava empregado na frente de clientes",
            "assedio_indicios",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "contrato pj mas a pessoa batia ponto e recebia ordens diretas do dono",
            "pj_sub",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "empresa terceirizada mas eu dava ordens diretas ao trabalhador todo dia",
            "terceiro_sub",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "banco de horas sem assinatura individual nem coletiva",
            "banco_horas",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "processo trabalhista distribuido sem eu ter petição inicial em maos",
            "litigio_medio",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "acao judicial trabalhista pedindo horas extras ultimos 5 anos",
            "litigio_medio",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "rescisao atrasou 20 dias e nao paguei multa do artigo 477 ainda",
            "rescisao_atrasada",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "pagamento por fora varios meses além do salario oficial",
            "por_fora",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "salario pago picado comprovado em extratos fragmentados",
            "salario_picado",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "domingo sem folga em escala 12 por 36 irregular",
            "domingo",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "humilhação recorrente por mensagens de whatsapp do supervisor",
            "assedio_indicios",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "empresa nao recolheu fgts ha 9 meses sequenciais",
            "fgts",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "trabalhista entrou na justiça cobrando adicional noturno sem eu ver inicial",
            "acao_sem_peticao",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "horas extras sem pagamento ha dois anos relato consistente",
            "he_habitual",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "férias vencidas nao pagas ha tres periodos",
            "ferias",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        M(
            "rescisão atrasou 30 dias para homologar carteira",
            "rescisao_atrasada",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
    ]

    alto = [
        A(
            "mandei embora gravida e nao paguei nada de verbas rescisorias",
            "gestante",
            expected_min_risk="ALTO",
            expected_min_score=80,
        ),
        A(
            "dispensei gestante no sexto mes sem acerto rescisorio",
            "gestante",
            expected_min_risk="ALTO",
            expected_min_score=80,
        ),
        A(
            "funcionario trabalhou 2 anos sem carteira assinada",
            "sem_registro",
            expected_min_risk="ALTO",
            expected_min_score=75,
        ),
        A(
            "14 meses sem registro em carteira e agora quer reconhecimento de vínculo",
            "sem_registro",
            expected_min_risk="ALTO",
            expected_min_score=75,
        ),
        A(
            "apliquei justa causa mas nao tenho prova nem documento nem testemunha",
            "jc_sem_prova",
            expected_min_risk="ALTO",
            expected_min_score=78,
        ),
        A(
            "dei justa causa sem provas robustas e sem testemunhas",
            "jc_sem_prova",
            expected_min_risk="ALTO",
            expected_min_score=78,
        ),
        A(
            "houve acidente de trabalho e a empresa nao abriu CAT",
            "acidente_cat",
            expected_min_risk="ALTO",
            expected_min_score=80,
        ),
        A(
            "acidente no trabalho e nao fiz CAT a tempo",
            "acidente_cat",
            expected_min_risk="ALTO",
            expected_min_score=80,
        ),
        A(
            "assedio moral com prints audio e testemunha presencial",
            "assedio_provado",
            expected_min_risk="ALTO",
            expected_min_score=80,
        ),
        A(
            "assédio no setor com prints e testemunha e mensagens",
            "assedio_provado",
            expected_min_risk="ALTO",
            expected_min_score=80,
        ),
        A(
            "hora extra todo dia com jornada excessiva e sem ponto",
            "he_alto",
            expected_min_risk="MÉDIO",
            expected_min_score=70,
        ),
        A(
            "nao paguei rescisao e ficou sem acerto rescisorio",
            "verbas_np",
            expected_min_risk="ALTO",
            expected_min_score=78,
        ),
        A(
            "verbas rescisórias não pagas ha tres meses desde a demissao",
            "verbas_np",
            expected_min_risk="ALTO",
            expected_min_score=78,
        ),
        A(
            "contrato pj mas batia ponto e tinha chefe direto mandando em tudo",
            "pj_sub",
            expected_min_risk="ALTO",
            expected_min_score=78,
        ),
        A(
            "terceirizado com subordinação direta diaria ao meu gerente",
            "terceiro_sub",
            expected_min_risk="ALTO",
            expected_min_score=78,
        ),
        A(
            "dispensa de gestante sem justa causa e sem pagamento",
            "gestante",
            expected_min_risk="ALTO",
            expected_min_score=80,
        ),
        A(
            "trabalhou sem registrar por 18 meses na construção civil",
            "sem_registro",
            expected_min_risk="ALTO",
            expected_min_score=75,
        ),
        A(
            "justa causa aplicada sem audiencia de defesa e sem provas",
            "jc_sem_prova",
            expected_min_risk="ALTO",
            expected_min_score=78,
        ),
        A(
            "acidente grave sem comunicacao ao orgao e sem CAT",
            "acidente_cat",
            expected_min_risk="ALTO",
            expected_min_score=80,
        ),
        A(
            "assedio com áudio prints e testemunha confirmando humilhação",
            "assedio_provado",
            expected_min_risk="ALTO",
            expected_min_score=80,
        ),
        A(
            "jornada excessiva sem ponto hora extra todo dia durante um ano",
            "he_alto",
            expected_min_risk="MÉDIO",
            expected_min_score=70,
        ),
        A(
            "sem pagar nada quando demiti no impulso e funcionario gravida",
            "gestante",
            expected_min_risk="ALTO",
            expected_min_score=80,
        ),
        A(
            "funcionario sem carteira ha 4 anos projeto continuo",
            "sem_registro",
            expected_min_risk="ALTO",
            expected_min_score=75,
        ),
        A(
            "queda no trabalho machucou coluna empresa nao abriu cat",
            "acidente_cat",
            expected_min_risk="ALTO",
            expected_min_score=80,
        ),
        A(
            "assédio moral provado por pericia psicologica e testemunhas",
            "assedio_provado",
            expected_min_risk="ALTO",
            expected_min_score=78,
        ),
    ]

    litigio = [
        L(
            "reclamacao trabalhista ja distribuida pedindo lusd e horas extras ultimos 5 anos",
            "inicial_distribuida",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "audiencia trabalhista marcada para proxima semana sobre dispensa coletiva",
            "audiencia",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "execucao trabalhista penhorou conta da empresa valor alto",
            "execucao",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "acao judicial trabalhista em segunda instancia contra multa artigo 477",
            "recurso",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "processo trabalhista com laudo pericial ergonômico favoravel ao empregado",
            "pericia",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "conciliacao na justica do trabalho falhou e segue litigio",
            "rito",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "funcionario entrou na justiça pedindo 120 mil entre reflexos e danos",
            "valor_alto",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "acao rescisoria contra justa causa com documentos novos",
            "rito",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "ajuizou reclamação trabalhista apos dispensa coletiva sem negociacao",
            "collectiva",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "mandado de seguranca trabalhista contra multa ministerial",
            "ms",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "acao civil publica ministerio publico do trabalho fiscalizacao",
            "acp",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "cumprimento de sentenca trabalhista com calculo de liquido atualizado",
            "cumprimento",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "embargos à execução trabalhista apresentados pelo departamento juridico",
            "embargos",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "acao judicial pedindo anulação de acordo coletivo especifico",
            "rito",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "processo trabalhista em trt com audiencia virtual gravada",
            "audiencia",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "reclamante entrou na justiça sem eu ter peticao inicial impressa",
            "acao_sem_peticao",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "acao trabalhista coletiva sindicato contra horas extras generalizadas",
            "coletivo",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "liquidação de sentença trabalhista com honorários sucumbenciais",
            "liquidacao",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "impugnacao ao calculo do perito judicial trabalhista",
            "pericia",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
        L(
            "acao judicial trabalhista pedindo estabilidade acidentaria",
            "estabilidade",
            expected_min_risk="MÉDIO",
            expected_min_score=42,
        ),
    ]

    confuso = [
        C(
            "funcionario sumiu do mapa e agora quer direitos mas nao sei quanto tempo trabalhou",
            "ambiguo",
            expected_max_risk="MÉDIO",
            expected_max_score=60,
        ),
        C(
            "pediu demissao mas diz que foi coagido nao tenho prova de nada",
            "ambivalente",
            expected_max_risk="ALTO",
            expected_max_score=92,
        ),
        C(
            "nao sei se foi demissao ou pedido de demissao relato confuso sem datas",
            "incompleto",
            expected_max_risk="MÉDIO",
            expected_max_score=55,
        ),
        C(
            "coisa de trabalho ruim com gestor talvez assedio talvez so estresse",
            "nebuloso",
            expected_max_risk="MÉDIO",
            expected_max_score=62,
        ),
        C(
            "texto muito curto demissao problema",
            "curto",
            expected_max_risk="MÉDIO",
            expected_max_score=55,
        ),
        C(
            "empresa boa mas funcionario chato quer processar por tudo",
            "ruidos",
            expected_max_risk="MÉDIO",
            expected_max_score=58,
        ),
        C(
            "acordo extrajudicial possivel mas juiz nao homologou ainda",
            "fluxo_misto",
            expected_max_risk="MÉDIO",
            expected_max_score=58,
        ),
        C(
            "diz que caiu mas nao fala se foi trabalho ou casa acidente duvidoso",
            "ambiguo_acidente",
            expected_max_risk="MÉDIO",
            expected_max_score=60,
        ),
        C(
            "pediu ferias e pediu demissao no mesmo email ordem confusa",
            "contraditorio",
            expected_max_risk="MÉDIO",
            expected_max_score=58,
        ),
        C(
            "relato enorme sem foco jornada ferias acidente tudo junto sem valores",
            "denso_confuso",
            expected_max_risk="ALTO",
            expected_max_score=92,
        ),
    ]

    out = basico + medio + alto + litigio + confuso
    assert len(out) == 100, len(out)
    return out


def _gerar_sugestoes(
    falhas_por_cat: dict[str, list],
    total_alerta: int,
    n: int,
    erros_por_tag: Counter,
) -> list[str]:
    tips: list[str] = []
    taxa = (total_alerta / n * 100.0) if n else 0.0
    if taxa > 18:
        tips.append(
            f"Taxa de ALERTA elevada ({taxa:.1f}%): revisar expectativas da bateria ou calibrar "
            "classificador de risco / hard rules se os erros forem sistemáticos."
        )
    for cat, items in sorted(falhas_por_cat.items(), key=lambda x: -len(x[1])):
        if len(items) >= 4:
            tips.append(
                f"Categoria '{cat}' concentra {len(items)} alertas: revisar tags mais frequentes nesse bucket."
            )
    for tag, cnt in erros_por_tag.most_common(5):
        if cnt >= 3:
            tips.append(
                f"Tag '{tag}' falhou {cnt} vez(es): validar se o texto do caso ainda dispara a mesma "
                "regra comercial ou se a IA mudou o tipo_risco."
            )
    if not tips:
        tips.append(
            "Nenhuma sugestão automática crítica: manutenção preventiva da bateria a cada release."
        )
    return tips


def main() -> None:
    cases = _build_cases()
    run_llm = os.getenv("RUN_LLM_EVAL", "0") == "1"

    lines: list[str] = []
    rows_csv: list[dict] = []

    total_ok = 0
    total_alerta = 0
    falhas_por_cat: dict[str, list] = defaultdict(list)
    erros_detalhe: list[tuple[int, str, str, str, str, str, int, str]] = []
    erros_por_tag: Counter[str] = Counter()

    lines.append("=" * 88)
    lines.append("ETAPA TESTE GUERRA 100 — bateria trabalhista (validação comercial)")
    lines.append("=" * 88)

    for idx, case in enumerate(cases, start=1):
        entrada = case["entrada"]
        dados, resultado, score_data, nivel, score, prob, hard = _run_pipeline(entrada)

        if run_llm:
            try:
                parecer = gerar_parecer_juridico(
                    contexto=entrada,
                    dados=dados,
                    resultado=resultado,
                    score=score,
                    probabilidade=prob,
                )
            except Exception as exc:  # noqa: BLE001 — relatório de bateria
                parecer = {
                    "veredito_estrategico": {
                        "resumo_executivo_1_linha": f"[LLM erro: {exc}] usar síntese determinística."
                    }
                }
        else:
            parecer = {
                "veredito_estrategico": {
                    "resumo_executivo_1_linha": (
                        f"Nível {nivel}; score {score}; probabilidade {prob}%. "
                        f"Conduta comercial: seguir hard rules e checklist probatório."
                    )
                }
            }

        veredito = _veredito_resumo(parecer)
        ok, motivo = _is_case_ok(case, nivel, score)
        status = "OK" if ok else "ALERTA"

        if ok:
            total_ok += 1
        else:
            total_alerta += 1
            falhas_por_cat[case["categoria"]].append(idx)
            erros_por_tag[case["tag"]] += 1
            erros_detalhe.append(
                (idx, case["categoria"], case["tag"], entrada[:180], motivo, nivel, score, hard)
            )

        block = [
            f"\n[{idx:03d}] {status}  |  categoria={case['categoria']}  |  tag={case['tag']}",
            f"entrada: {entrada}",
            f"risco (nível score): {nivel}",
            f"score: {score}",
            f"probabilidade: {prob}%",
            f"veredito executivo: {veredito}",
            f"hard rule / motor: {hard}",
            f"OK / ALERTA: {status}",
        ]
        lines.extend(block)

        rows_csv.append(
            {
                "numero": idx,
                "categoria": case["categoria"],
                "tag": case["tag"],
                "entrada": entrada,
                "risco": nivel,
                "score": score,
                "probabilidade": prob,
                "veredito_executivo": veredito,
                "hard_rule": hard,
                "status": status,
                "motivo_alerta": motivo if not ok else "",
            }
        )

    n = len(cases)
    taxa_ok = (total_ok / n * 100.0) if n else 0.0

    por_cat: dict[str, dict[str, float | int]] = {}
    for cat in ["basico", "medio", "alto", "litigio", "confuso"]:
        tot_c = sum(1 for c in cases if c["categoria"] == cat)
        ok_c = sum(1 for r in rows_csv if r["categoria"] == cat and r["status"] == "OK")
        por_cat[cat] = {
            "total": tot_c,
            "ok": ok_c,
            "taxa_pct": round((ok_c / tot_c * 100.0), 2) if tot_c else 0.0,
        }

    lines.append("\n" + "=" * 88)
    lines.append("RESUMO GLOBAL")
    lines.append("=" * 88)
    lines.append(f"Total OK: {total_ok}")
    lines.append(f"Total ALERTA: {total_alerta}")
    lines.append(f"Taxa OK %: {taxa_ok:.2f}")

    lines.append("\nTaxa por categoria:")
    for cat, st in por_cat.items():
        lines.append(
            f"  - {cat}: OK {st['ok']}/{st['total']} ({st['taxa_pct']}%)"
        )

    lines.append("\nTop 10 erros (primeiros alertas da execução):")
    for row in erros_detalhe[:10]:
        idx, categoria, tag, entr_snip, motivo, nivel, score, hard = row
        lines.append(
            f"  [{idx:03d}] ({categoria}/{tag}) {motivo} | obtido: {nivel} score={score} | {hard}"
        )
        lines.append(f"      entrada: {entr_snip}...")

    sugestoes = _gerar_sugestoes(falhas_por_cat, total_alerta, n, erros_por_tag)
    lines.append("\nSugestões automáticas:")
    for s in sugestoes:
        lines.append(f"  • {s}")

    lines.append("\n" + "=" * 88)

    texto = "\n".join(lines)

    with open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write(texto)

    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "numero",
                "categoria",
                "tag",
                "entrada",
                "risco",
                "score",
                "probabilidade",
                "veredito_executivo",
                "hard_rule",
                "status",
                "motivo_alerta",
            ],
        )
        w.writeheader()
        w.writerows(rows_csv)

    print(texto)
    print(f"\nExportado: {OUT_TXT}")
    print(f"Exportado: {OUT_CSV}")


if __name__ == "__main__":
    main()
