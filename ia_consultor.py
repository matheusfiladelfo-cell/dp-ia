from ia_client import client
from ia_validator import validar_parecer
import json


def gerar_parecer_juridico(
    contexto,
    dados,
    resultado,
    score=None,
    probabilidade=None
):

    prompt = f"""
Você é um consultor trabalhista que orienta profissionais de RH.

⚠️ REGRA CRÍTICA:
A resposta DEVE ser dividida em 3 blocos VISÍVEIS e SEPARADOS.

Se não separar corretamente, a resposta está errada.

-----------------------------------
📊 INDICADORES INTERNOS (NÃO EXIBIR)
-----------------------------------

Score interno: {score if score else "N/A"}/100  
Probabilidade estimada: {probabilidade if probabilidade else "N/A"}%

-----------------------------------
📌 CONTEXTO
-----------------------------------
{contexto}

-----------------------------------
📌 DADOS
-----------------------------------

Tipo de caso: {dados.get("tipo_caso")}
Tipo de rescisão: {dados.get("tipo_rescisao")}
Tempo de empresa: {dados.get("tempo_empresa_meses")}

-----------------------------------
📌 ANÁLISE DO SISTEMA
-----------------------------------

Risco calculado: {resultado.get("risco")}
Pontuação: {resultado.get("pontuacao")}

-----------------------------------
⚠️ DIRETRIZ PRINCIPAL (CRÍTICO)
-----------------------------------

👉 A análise deve ser baseada na legislação trabalhista e na prática da Justiça do Trabalho

👉 NÃO mencionar score, cálculos ou lógica interna  
👉 NÃO explicar como o sistema chegou na conclusão  

👉 A resposta deve parecer uma orientação profissional real, como um consultor de RH experiente

-----------------------------------
⚠️ INSTRUÇÕES OBRIGATÓRIAS
-----------------------------------

A resposta DEVE seguir EXATAMENTE este formato:

### BLOCO 1 — EXPLICAÇÃO SIMPLES
- Explicar o que está acontecendo de forma clara
- Linguagem simples e objetiva
- Sem termos técnicos excessivos

### BLOCO 2 — CONSULTORIA PARA RH
- Explicar o risco real com base na prática da Justiça do Trabalho
- Dizer claramente se há risco de condenação
- Explicar o que pode acontecer juridicamente
- Orientar de forma prática o que a empresa deve fazer

🔥 IMPORTANTE:
- NÃO mencionar score
- NÃO mencionar percentual técnico
- NÃO falar de cálculo ou sistema
- Deve parecer uma orientação profissional real

### BLOCO 3 — BASE LEGAL
- Fundamentar com CLT (artigos relevantes)
- Constituição Federal
- entendimento da Justiça do Trabalho (jurisprudência)
- Explicar de forma acessível

-----------------------------------
⚠️ PROIBIDO:
-----------------------------------

❌ Falar de score  
❌ Falar "score do sistema"  
❌ Falar de cálculo interno  
❌ Misturar blocos  
❌ Omitir títulos  

-----------------------------------
📦 FORMATO JSON (OBRIGATÓRIO)
-----------------------------------

{{
  "risco": "BAIXO | MÉDIO | ALTO",

  "diagnostico": "### BLOCO 1 — EXPLICAÇÃO SIMPLES\\nExplicação clara do cenário",

  "recomendacao": "### BLOCO 2 — CONSULTORIA PARA RH\\nOrientação prática, direta e profissional",

  "fundamentacao": "### BLOCO 3 — BASE LEGAL\\nFundamentação com CLT, Constituição e jurisprudência",

  "impactos": "Explicar FGTS, férias + 1/3, 13º e DSR",

  "impacto_financeiro": número
}}
"""

    try:

        resposta = client.responses.create(
            model="gpt-4.1",
            input=prompt,
            timeout=30
        )

        texto = resposta.output_text.strip()

        return validar_parecer(texto)

    except Exception as e:

        print("ERRO IA:", e)

        return validar_parecer("")