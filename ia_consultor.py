from ia_client import client
import json


def gerar_parecer_juridico(contexto, dados, resultado):

    prompt = f"""
Você é um consultor trabalhista estratégico para RH.

⚠️ ESTILO:
- Linguagem clara (não jurídica complexa)
- Explicativo, mas direto
- Profissional
- Pode usar termos técnicos SIM, mas explicando

⚠️ OBJETIVO:
Gerar um parecer completo e útil para tomada de decisão.

-----------------------------------
DADOS DO CASO
-----------------------------------

Tipo de caso: {dados.get("tipo_caso")}
Tipo de rescisão: {dados.get("tipo_rescisao")}
Tempo de empresa: {dados.get("tempo_empresa_meses")}
Salário: {dados.get("salario")}
Horas extras semanais: {dados.get("horas_extras_semanais")}

-----------------------------------
CONTEXTO
-----------------------------------
{contexto}

-----------------------------------
ANÁLISE DO SISTEMA
-----------------------------------

Risco base: {resultado.get("risco")}
Pontuação: {resultado.get("pontuacao")}

-----------------------------------
INSTRUÇÕES
-----------------------------------

1. Explicar o cenário com clareza
2. Explicar o risco considerando:
   - horas extras habituais
   - reflexos (FGTS, férias, 13º, DSR)
3. Explicar que:
   → o juiz pode reconhecer essas horas
   → pode aplicar o piso da categoria
   → isso aumenta o valor da condenação
4. Considerar:
   - tendência da Justiça do Trabalho (proteção ao empregado)
   - falta de controle de ponto (aumenta risco)
5. Trazer base legal de forma simples:
   - CLT (horas extras e integração)
   - Constituição (proteção ao trabalhador)
   - mencionar entendimento da Justiça do Trabalho

⚠️ IMPORTANTE:
- NÃO ser raso
- NÃO escrever como chatbot
- NÃO dar resposta genérica

-----------------------------------
FORMATO JSON
-----------------------------------

{{
  "diagnostico": "Explicação clara e completa do problema",
  "risco": "BAIXO | MÉDIO | ALTO",
  "motivo_risco": "Explicação detalhada do risco, incluindo impacto financeiro, reflexos, piso da categoria e base legal",
  "o_que_fazer": [
    "Ação prática 1",
    "Ação prática 2",
    "Ação prática 3",
    "Ação prática 4"
  ]
}}
"""

    try:

        resposta = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            timeout=20
        )

        texto = resposta.output_text.strip()

        if "```" in texto:
            partes = texto.split("```")
            texto = partes[1] if len(partes) > 1 else partes[0]

        return json.loads(texto)

    except Exception as e:

        print("ERRO IA:", e)

        return {
            "diagnostico": (
                "Funcionário com horas extras habituais não registradas, "
                "o que pode gerar reflexos na rescisão."
            ),
            "risco": resultado.get("risco", "MÉDIO"),
            "motivo_risco": (
                "Horas extras não pagas podem ser cobradas judicialmente com reflexos em FGTS, "
                "férias, 13º e DSR. A Justiça do Trabalho tende a proteger o empregado e pode aplicar "
                "o piso da categoria, aumentando o valor da condenação."
            ),
            "o_que_fazer": [
                "Revisar jornada e controle de ponto",
                "Calcular horas extras e reflexos",
                "Verificar convenção coletiva",
                "Avaliar acordo preventivo"
            ]
        }