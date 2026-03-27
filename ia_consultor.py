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
📊 INDICADORES
-----------------------------------

Índice de Risco Trabalhista (DP-IA): {score if score else "N/A"}/100  
Probabilidade de condenação: {probabilidade if probabilidade else "N/A"}%

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

Risco calculado pelo sistema: {resultado.get("risco")}
Pontuação interna: {resultado.get("pontuacao")}

-----------------------------------
⚠️ DIRETRIZ PRINCIPAL (CRÍTICO)
-----------------------------------

👉 A análise deve ser baseada na legislação trabalhista e na prática da Justiça do Trabalho

👉 O score NÃO define o risco  
👉 O score apenas reforça a análise

👉 Se houver qualquer divergência:
🔥 PREVALECE A ANÁLISE JURÍDICA

-----------------------------------
⚠️ INSTRUÇÕES OBRIGATÓRIAS
-----------------------------------

A resposta DEVE seguir EXATAMENTE este formato:

### BLOCO 1 — EXPLICAÇÃO SIMPLES
- Explicar o que está acontecendo de forma clara
- Usar linguagem simples
- Explicar o cenário real (não baseado no score)
- Inserir o score ({score}/100) apenas como complemento

### BLOCO 2 — CONSULTORIA PARA RH
- Explicar o risco REAL com base na prática da Justiça do Trabalho
- Explicar chance de condenação ({probabilidade}%)
- Traduzir o score como apoio (não como decisão)
- Dizer claramente o que a empresa deve fazer

### BLOCO 3 — BASE LEGAL
- Fundamentar com CLT (artigos relevantes)
- Constituição Federal
- entendimento da Justiça do Trabalho (jurisprudência)
- Explicar de forma acessível

-----------------------------------
⚠️ PROIBIDO:
-----------------------------------

❌ Basear a conclusão apenas no score  
❌ Dizer "risco baixo" apenas porque o score é baixo  
❌ Ignorar fundamentos jurídicos  
❌ Misturar blocos  
❌ Omitir títulos  

-----------------------------------
📦 FORMATO JSON (OBRIGATÓRIO)
-----------------------------------

{{
  "risco": "BAIXO | MÉDIO | ALTO",

  "diagnostico": "### BLOCO 1 — EXPLICAÇÃO SIMPLES\\nExplicação clara incluindo referência ao score ({score}/100) apenas como apoio",

  "recomendacao": "### BLOCO 2 — CONSULTORIA PARA RH\\nOrientação prática baseada no risco jurídico real, usando o score ({score}/100) e probabilidade ({probabilidade}%) como complemento",

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