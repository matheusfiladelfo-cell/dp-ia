from ia_client import client
import json


def classificar_risco_ia(texto):

    prompt = f"""
Você é um especialista em direito do trabalho brasileiro.

Sua função é classificar juridicamente o risco de um caso com base na prática da Justiça do Trabalho.

-----------------------------------
EXEMPLOS (APRENDIZADO)
-----------------------------------

Caso: funcionário foi humilhado pelo gestor na frente da equipe  
Resposta:
{{"tipo_risco": "assedio_moral", "gravidade": "alta"}}

Caso: funcionário sofreu acidente durante atividade  
Resposta:
{{"tipo_risco": "acidente_trabalho", "gravidade": "alta"}}

Caso: discussão isolada sem humilhação  
Resposta:
{{"tipo_risco": "conflito_interpessoal", "gravidade": "media"}}

Caso: dúvida genérica trabalhista  
Resposta:
{{"tipo_risco": "geral", "gravidade": "baixa"}}

-----------------------------------
AGORA ANALISE ESTE CASO:
-----------------------------------

{texto}

-----------------------------------
REGRAS:
-----------------------------------

- assédio moral → sempre gravidade alta  
- acidente de trabalho → sempre gravidade alta  
- conflito leve → média  
- dúvida → baixa  

-----------------------------------
RESPONDA APENAS EM JSON:
-----------------------------------

{{
  "tipo_risco": "...",
  "gravidade": "..."
}}
"""

    try:
        resposta = client.responses.create(
            model="gpt-4.1",
            input=prompt,
            timeout=20
        )

        texto_resposta = resposta.output_text.strip()

        return json.loads(texto_resposta)

    except:
        return {
            "tipo_risco": "geral",
            "gravidade": "baixa"
        }