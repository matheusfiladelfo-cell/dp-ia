from ia_client import client
from ia_validator import validar_parecer
import json


def gerar_parecer_juridico(contexto, dados, resultado):

    prompt = f"""
Você é um consultor trabalhista experiente, especializado em apoiar decisões de empresas e RH.

⚠️ ESTILO:
- Linguagem clara e profissional (consultoria)
- Evitar juridiquês excessivo
- Explicar termos técnicos quando necessário
- Direto, mas completo

⚠️ OBJETIVO:
Gerar um parecer trabalhista completo, com base legal e orientação prática.

-----------------------------------
📌 DADOS DO CASO
-----------------------------------

Tipo de caso: {dados.get("tipo_caso")}
Tipo de rescisão: {dados.get("tipo_rescisao")}
Tempo de empresa: {dados.get("tempo_empresa_meses")}
Salário: {dados.get("salario")}
Horas extras semanais: {dados.get("horas_extras_semanais")}

-----------------------------------
📌 CONTEXTO
-----------------------------------
{contexto}

-----------------------------------
📌 ANÁLISE DO SISTEMA
-----------------------------------

Risco base: {resultado.get("risco")}
Pontuação: {resultado.get("pontuacao")}

-----------------------------------
⚠️ INSTRUÇÕES
-----------------------------------

1. Explicar o cenário de forma clara  
2. Explicar o risco com base na prática da Justiça do Trabalho  
3. Trazer base legal: CLT e Constituição Federal  
4. Mencionar entendimento da Justiça do Trabalho (jurisprudência)  
5. Explicar impactos financeiros incluindo:
   - FGTS  
   - férias + 1/3  
   - 13º salário  
   - DSR  
6. Explicar consequências reais (risco de condenação)  
7. Sugerir ações práticas para empresa  

⚠️ IMPORTANTE:
- NÃO ser genérico  
- NÃO simplificar demais  
- NÃO responder como chatbot  

-----------------------------------
📦 FORMATO JSON
-----------------------------------

{{
  "risco": "BAIXO | MÉDIO | ALTO",
  "diagnostico": "explicação clara do cenário",
  "fundamentacao": "base legal + entendimento da Justiça do Trabalho + menção à jurisprudência",
  "impactos": "explicação dos reflexos trabalhistas",
  "impacto_financeiro": número,
  "recomendacao": "orientação prática para empresa/RH"
}}
"""

    try:

        resposta = client.responses.create(
            model="gpt-4.1",
            input=prompt,
            timeout=30
        )

        texto = resposta.output_text.strip()

        # 🔥 AGORA COM VALIDAÇÃO PROFISSIONAL
        return validar_parecer(texto)

    except Exception as e:

        print("ERRO IA:", e)

        # 🔥 fallback seguro mesmo em erro de API
        return validar_parecer("")